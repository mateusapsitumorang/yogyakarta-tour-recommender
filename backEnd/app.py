"""
Code Flask untuk sistem rekomendasi paket wisata di Yogyakarta.
"""
import os, tempfile, csv, re, json, uuid, traceback
from datetime import datetime
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    redirect,
    url_for,
    flash,
    session,
    current_app,
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import pytz
from flask import request, send_file, jsonify
from map_setup import NEO4J_URI, NEO4J_AUTH, get_coordinates_from_neo4j
from config import KABUPATEN, KATEGORI_WISATA, HARGA_PENGINAPAN
from path_ranking import get_recommendations
from utils import get_safe_value, generate_package_id
from models import db, User, UserCriteria, Recommendation, UserRecommendationFeedback
from evaluate_system import (
    evaluate_user_satisfaction,
    export_all_evaluations_to_csv,
    format_evaluation_results_html,
)
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly

# Setup Flask
basedir = os.path.abspath(os.path.dirname(__file__))
instance = os.path.join(basedir, "instance")
os.makedirs(instance, exist_ok=True)

template_dir = os.path.join(os.path.dirname(basedir), "frontEnd")
static_dir = os.path.join(os.path.dirname(basedir), "static")

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.secret_key = "your_secret_key_here"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(instance, "app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
migrate = Migrate(app, db)

# Helper
def is_logged_in():
    # Memeriksa apakah pengguna sudah login dengan memeriksa keberadaan 'user_id' di sesi.
    return "user_id" in session

MONTHS_ID = {
    1: "Januari",
    2: "Februari",
    3: "Maret",
    4: "April",
    5: "Mei",
    6: "Juni",
    7: "Juli",
    8: "Agustus",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Desember",
}

@app.template_filter("format_indonesia")
def format_indonesia(dt: datetime) -> str:
    # Mengonversi objek datetime ke format tanggal dan waktu dalam bahasa Indonesia.
    # Jika datetime tidak valid, mengembalikan tanda '-'.
    if not dt:
        return "-"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    dj = dt.astimezone(pytz.timezone("Asia/Jakarta"))
    return f"{dj.day} {MONTHS_ID[dj.month]} {dj.year} pukul {dj.hour}.{dj.minute:02d}"

with app.app_context():
    db.create_all()

# ——— ROUTES —————————————————————————————————

@app.route("/")
def index():
    # Menampilkan halaman utama aplikasi dengan opsi pemilihan kabupaten, kategori wisata,
    # dan harga penginapan. Memeriksa status login pengguna.
    return render_template(
        "index.html",
        kabupaten=KABUPATEN,
        kategori_wisata=KATEGORI_WISATA,
        harga_penginapan=HARGA_PENGINAPAN,
        is_logged_in=is_logged_in(),
    )

@app.route("/admin")
def index_admin():
    # Menampilkan halaman admin hanya jika pengguna sudah login dan memiliki hak akses admin.
    # Jika tidak, pengguna dialihkan ke halaman utama dengan pesan peringatan.
    if not is_logged_in() or not session.get("is_admin"):
        flash("Akses ditolak", "danger")
        return redirect(url_for("index"))
    return render_template(
        "index_admin.html",
        is_logged_in=is_logged_in(),
        is_admin=session.get("is_admin", False),
    )

@app.route("/check_login")
def check_login():
    # Mengembalikan status login pengguna dalam format JSON untuk keperluan frontend.
    return jsonify({"is_logged_in": is_logged_in()})

@app.route("/destination")
def destination():
    # Menampilkan halaman destinasi wisata, dengan informasi status login pengguna.
    return render_template("destination.html", is_logged_in=is_logged_in())

@app.route("/recommendation")
def recommendation():
    # Menampilkan halaman rekomendasi wisata untuk pengguna yang sudah login.
    # Jika belum login, pengguna dialihkan ke halaman login dengan pesan peringatan.
    if not is_logged_in():
        flash("Anda harus login terlebih dahulu", "warning")
        return redirect(url_for("login"))
    return render_template(
        "recommendation.html",
        kabupaten=KABUPATEN,
        kategori_wisata=KATEGORI_WISATA,
        harga_penginapan=HARGA_PENGINAPAN,
        is_logged_in=is_logged_in(),
        is_admin=session.get("is_admin", False),
    )

@app.route("/about")
def about():
    # Menampilkan halaman tentang aplikasi, dengan informasi status login pengguna.
    return render_template("about.html", is_logged_in=is_logged_in())

@app.route("/get_route_coordinates", methods=["POST"])
def get_route_coordinates():
    # Mengambil koordinat lokasi (penginapan, tempat wisata, rumah makan) dari database Neo4j
    # berdasarkan ID yang diberikan dalam permintaan JSON.
    data = request.json
    try:
        from neo4j import GraphDatabase
        with GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH) as driver:
            with driver.session() as s:
                coords = {
                    "penginapan": s.read_transaction(
                        get_coordinates_from_neo4j, "Penginapan", data["penginapan_id"]
                    ),
                    "wisata1": s.read_transaction(
                        get_coordinates_from_neo4j, "TempatWisata", data["wisata1_id"]
                    ),
                    "wisata2": s.read_transaction(
                        get_coordinates_from_neo4j, "TempatWisata", data["wisata2_id"]
                    ),
                    "rumahmakan1": s.read_transaction(
                        get_coordinates_from_neo4j, "RumahMakan", data["rumahmakan_id"]
                    ),
                }
        return jsonify(success=True, coordinates=coords)
    except Exception as e:
        return jsonify(success=False, error=str(e))

@app.route("/get_location_data", methods=["POST"])
def get_location_data():
    # Mengambil data koordinat lokasi berdasarkan ID penginapan, tempat wisata, dan rumah makan
    # dari database Neo4j menggunakan fungsi get_coordinates_from_neo4j.
    try:
        data = request.json
        coords = get_coordinates_from_neo4j(
            data["id_penginapan"],
            data["id_tempat_wisata_1"],
            data["id_tempat_wisata_2"],
            data["id_rumah_makan"],
        )
        return jsonify(coords), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/recommendations", methods=["POST"])
def get_recommendation_results():
    # Menghasilkan rekomendasi paket wisata berdasarkan kriteria pengguna yang dikirim melalui JSON.
    # Menyimpan rekomendasi ke database dan mengembalikan hasil dalam format JSON.
    if "user_id" not in session:
        return jsonify(success=False, error="Login diperlukan"), 401

    data = request.get_json() or {}
    jumlah = int(data.get("jumlah_rekomendasi", 3))
    min_harga_penginapan = float(data.get("min_harga_penginapan", 0))
    max_harga_penginapan = float(data.get("max_harga_penginapan", 1500000))

    criteria = {
        "kabupaten": data.get("kabupaten", []),
        "kategori_wisata": data.get("kategori_wisata", None),
        "min_rating_tempat_wisata": float(data.get("min_rating_tempat_wisata", 3.0)),
        "min_rating_penginapan": float(data.get("min_rating_penginapan", 3.0)),
        "min_rating_rumah_makan": float(data.get("min_rating_rumah_makan", 3.0)),
        "min_harga_penginapan": min_harga_penginapan,
        "max_harga_penginapan": max_harga_penginapan,
        "use_reviews": data.get("use_reviews", False),
        "num_recommendations": jumlah,
    }

    if criteria["kategori_wisata"] == "all":
        criteria["kategori_wisata"] = None

    try:
        recs = get_recommendations(criteria)

        filtered_recs = [
            rec
            for rec in recs
            if min_harga_penginapan
            <= rec["penginapan"]["harga"]
            <= max_harga_penginapan
        ]
        if not filtered_recs:
            filtered_recs = [
                rec
                for rec in recs
                if (rec["penginapan"]["harga"] >= min_harga_penginapan * 0.8)
                and (rec["penginapan"]["harga"] <= max_harga_penginapan * 1.2)
            ]
        recs = filtered_recs[:jumlah]

        last_crit = (
            UserCriteria.query.filter_by(id_user=session["user_id"])
            .order_by(UserCriteria.created_at.desc())
            .first()
        )

        if not last_crit:
            return jsonify(success=False, error="Kriteria user belum disimpan"), 400

        out = []
        saved_count = 0
        with db.session.no_autoflush:
            for r in recs:
                if saved_count >= jumlah:
                    break

                package_id = r["package_id"]

                if Recommendation.query.filter_by(
                    package_id=package_id,
                    user_id=session["user_id"],
                    criteria_id=last_crit.id_kriteria,
                ).first():
                    continue

                harga = r["penginapan"].get("harga")
                harga_penginapan = (
                    int(float(harga))
                    if harga and isinstance(harga, str) and "e" in harga.lower()
                    else harga
                )

                rec = Recommendation(
                    criteria_id=last_crit.id_kriteria,
                    package_id=package_id,
                    user_id=session["user_id"],
                    skor=r.get("total_score", 0.0),
                    kabupaten_penginapan=r.get("kabupaten_penginapan"),
                    nama_penginapan=r["penginapan"]["nama"],
                    rating_penginapan=r["penginapan"].get("rating"),
                    harga_penginapan=harga_penginapan,
                    nama_wisata_1=r["tempat_wisata_1"]["nama"],
                    kategori_wisata_1=r["tempat_wisata_1"].get("kategori"),
                    rating_wisata_1=r["tempat_wisata_1"].get("rating"),
                    nama_wisata_2=r["tempat_wisata_2"]["nama"],
                    kategori_wisata_2=r["tempat_wisata_2"].get("kategori"),
                    rating_wisata_2=r["tempat_wisata_2"].get("rating"),
                    nama_rumah_makan=r["rumah_makan"]["nama"],
                    rating_rumah_makan=r["rumah_makan"].get("rating"),
                    recommendation_json=json.dumps(r),
                    created_at=datetime.utcnow(),
                )
                db.session.add(rec)
                saved_count += 1

                # Sertakan google_maps_link dalam output JSON
                out.append({
                    **r,
                    "recommendationId": package_id,
                    "penginapan": {
                        **r["penginapan"],
                        "google_maps_link": r["penginapan"].get("google_maps_link", "")
                    },
                    "tempat_wisata_1": {
                        **r["tempat_wisata_1"],
                        "google_maps_link": r["tempat_wisata_1"].get("google_maps_link", "")
                    },
                    "tempat_wisata_2": {
                        **r["tempat_wisata_2"],
                        "google_maps_link": r["tempat_wisata_2"].get("google_maps_link", "")
                    },
                    "rumah_makan": {
                        **r["rumah_makan"],
                        "google_maps_link": r["rumah_makan"].get("google_maps_link", "")
                    }
                })

        db.session.commit()
        current_app.logger.info(
            f"Berhasil menyimpan {saved_count} rekomendasi untuk user_id={session['user_id']}"
        )
        return jsonify(success=True, recommendations=out)

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Kesalahan saat menyimpan rekomendasi: {str(e)}")
        return jsonify(success=False, error=str(e)), 500

@app.route("/save_user_criteria", methods=["POST"])
def save_user_criteria():
    # Menyimpan kriteria preferensi wisata pengguna ke database berdasarkan data JSON yang diterima.
    # Mengembalikan ID kriteria yang disimpan jika berhasil.
    if "user_id" not in session:
        return jsonify(success=False, error="Login diperlukan"), 401

    data = request.get_json() or {}
    kabupaten = data.get("kabupaten")
    if isinstance(kabupaten, list):
        kabupaten = ", ".join(kabupaten)

    try:
        uc = UserCriteria(
            id_user=session["user_id"],
            username=session["username"],
            email=session["email"],
            kabupaten=kabupaten,
            rating_tempat_wisata=float(data.get("min_rating_tempat_wisata", 0)),
            rating_penginapan=float(data.get("min_rating_penginapan", 0)),
            rating_rumah_makan=float(data.get("min_rating_rumah_makan", 0)),
            kategori_wisata=data.get("kategori_wisata"),
            min_harga_penginapan=float(data.get("min_harga_penginapan", 0)),
            max_harga_penginapan=float(data.get("max_harga_penginapan", 1500000)),
            metode_pencarian=(
                "Rating dan Ulasan" if data.get("use_reviews", False) else "Rating Saja"
            ),
            jumlah_rekomendasi=int(data.get("jumlah_rekomendasi", 3)),
            created_at=datetime.utcnow(),
        )
        db.session.add(uc)
        db.session.commit()
        current_app.logger.info(
            f"Kriteria disimpan dengan id_kriteria={uc.id_kriteria}"
        )
        return jsonify(success=True, criteria_id=uc.id_kriteria)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Kesalahan saat menyimpan kriteria: {str(e)}")
        return jsonify(success=False, error=str(e)), 500

@app.route("/save_like_dislike", methods=["POST"])
def save_like_dislike():
    # Menyimpan umpan balik pengguna (like, dislike, atau reset) untuk rekomendasi tertentu.
    # Memastikan rekomendasi valid dan menyimpan data ke database.
    if "user_id" not in session:
        return jsonify(success=False, error="Login diperlukan"), 401

    d = request.get_json() or {}
    crit_id = d.get("id_criteria") or d.get("criteriaId")
    pkg_id = d.get("packageId")
    action = d.get("action")

    if not crit_id or not pkg_id or action not in ("like", "dislike", "reset"):
        return jsonify(success=False, error="Payload tidak lengkap"), 400

    rec = Recommendation.query.filter_by(
        criteria_id=crit_id, package_id=pkg_id, user_id=session["user_id"]
    ).first()
    if not rec:
        return jsonify(success=False, error="Rekomendasi tidak ditemukan"), 404

    try:
        fb = UserRecommendationFeedback(
            recommendation_id=rec.id,
            user_id=session["user_id"],
            user_name=session["username"],
            feedback_type=action,
            score=d.get("recommendation", {}).get("total_score", 0.0),
        )
        db.session.add(fb)
        db.session.commit()
        return jsonify(success=True, feedback_id=fb.id)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)), 500

@app.route("/get_user_criteria", methods=["GET"])
def get_user_criteria():
    # Mengambil semua kriteria wisata yang dimiliki pengguna berdasarkan ID pengguna.
    # Mengembalikan daftar kriteria dalam format JSON.
    if not is_logged_in():
        return jsonify(success=False, error="Login diperlukan"), 401
    crits = UserCriteria.query.filter_by(user_id=session["user_id"]).all()
    return jsonify(success=True, criteria=[c.to_dict() for c in crits])

@app.route("/feedback-list")
def feedback_list():
    # Menampilkan halaman daftar umpan balik untuk admin, termasuk data pengguna, kriteria,
    # rekomendasi, dan hasil evaluasi. Hanya dapat diakses oleh admin.
    if not is_logged_in() or not session.get("is_admin"):
        flash("Akses ditolak", "danger")
        return redirect(url_for("index"))

    users = User.query.all()
    user_criteria = UserCriteria.query.order_by(UserCriteria.created_at.desc()).all()
    feedbacks = UserRecommendationFeedback.query.order_by(
        UserRecommendationFeedback.created_at.desc()
    ).all()
    recommendations = Recommendation.query.order_by(
        Recommendation.created_at.desc()
    ).all()
    eval_results = None
    eval_ks = [3, 5, 7]

    return render_template(
        "feedback_list.html",
        users=users,
        user_criteria=user_criteria,
        feedbacks=feedbacks,
        recommendations=recommendations,
        eval_results=eval_results,
        eval_ks=eval_ks,
        format_evaluation_results=format_evaluation_results_html,
    )

@app.route("/api/evaluate_by_type", methods=["POST"])
def api_evaluate_by_type():
    # Mengevaluasi performa sistem rekomendasi berdasarkan mode (per pengguna atau keseluruhan),
    # dengan mempertimbangkan umpan balik pengguna dan nilai K. Mengembalikan hasil evaluasi dalam format JSON.
    if not is_logged_in() or not session.get("is_admin"):
        return jsonify(success=False, error="Akses ditolak"), 403

    data = request.get_json() or {}
    user_id = data.get("user_id")
    criteria_id = data.get("criteria_id")
    feedback_mode = data.get("feedback_mode", "all")
    k_values = data.get("k_values", [3, 5, 7])
    evaluation_mode = data.get("evaluation_mode", "per_user")

    current_app.logger.info(
        f"Processing /api/evaluate_by_type with user_id={user_id}, criteria_id={criteria_id}, evaluation_mode={evaluation_mode}, k_values={k_values}"
    )

    if not isinstance(k_values, list) or not all(
        isinstance(k, int) and k > 0 for k in k_values
    ):
        return (
            jsonify(
                success=False,
                error="Nilai K harus berupa daftar bilangan bulat positif",
            ),
            400,
        )

    if not user_id or not criteria_id or not feedback_mode:
        return (
            jsonify(
                success=False, error="User ID, Criteria ID, dan mode masukan diperlukan"
            ),
            400,
        )

    try:
        if evaluation_mode == "overall":
            users = User.query.filter_by(is_admin=False).all()
            user_ids = [u.id for u in users]
            all_user_criteria = (
                UserCriteria.query.join(User).filter(User.is_admin == False).all()
            )
            all_recommendations = (
                Recommendation.query.join(User).filter(User.is_admin == False).all()
            )
            all_feedback_list = (
                UserRecommendationFeedback.query.join(User)
                .filter(User.is_admin == False)
                .all()
            )
            for fb in all_feedback_list:
                fb.criteria_id = fb.recommendation.criteria_id
                fb.package_id = fb.recommendation.package_id

            if (
                not all_user_criteria
                or not all_recommendations
                or not all_feedback_list
            ):
                return (
                    jsonify(
                        success=False,
                        error="Tidak ada data kriteria, rekomendasi, atau masukan untuk evaluasi keseluruhan",
                    ),
                    400,
                )

            current_app.logger.info(
                f"Evaluating overall mode: {len(all_user_criteria)} criteria, {len(all_recommendations)} recommendations, {len(all_feedback_list)} feedback"
            )
            result = evaluate_user_satisfaction(
                all_user_criteria,
                all_recommendations,
                all_feedback_list,
                k_values,
                feedback_mode,
                logger=current_app.logger,
            )

            html = "<h4>Tabel Hasil Evaluasi Keseluruhan</h4>"
            html += format_evaluation_results_html(result, k_values=k_values)

            chart_data = {
                "precision": result["summary"].get("precision", 0),
                "recall": result["summary"].get("recall", 0),
                "ndcg": result["summary"].get("ndcg", 0),
                "hit_rate": result["summary"].get("hit_rate", 0),
                "processed_users": result["summary"].get("processed_users", 0),
                "total_criteria": result["summary"].get("processed_criteria", 0),
                "total_feedback": result["summary"].get("total_feedback", 0),
            }

            return jsonify(
                success=True, data=chart_data, results=[result], html_formatted=html
            )
        else:
            if user_id == "all":
                users = User.query.filter_by(is_admin=False).all()
                user_ids = [u.id for u in users]
            else:
                user_ids = [int(user_id)]

            results = []
            for uid in user_ids:
                if criteria_id == "all":
                    user_criteria = UserCriteria.query.filter_by(id_user=uid).all()
                else:
                    user_criteria = UserCriteria.query.filter_by(
                        id_user=uid, id_kriteria=int(criteria_id)
                    ).all()
                if not user_criteria:
                    current_app.logger.warning(
                        f"Pengguna {uid} tidak memiliki kriteria {criteria_id}"
                    )
                    continue

                crit_ids = [c.id_kriteria for c in user_criteria]
                recommendations = Recommendation.query.filter(
                    Recommendation.user_id == uid,
                    Recommendation.criteria_id.in_(crit_ids),
                ).all()
                if not recommendations:
                    current_app.logger.warning(
                        f"Pengguna {uid}: tidak ada rekomendasi untuk kriteria {crit_ids}"
                    )
                    continue

                rec_ids = [r.id for r in recommendations]
                feedback_list = UserRecommendationFeedback.query.filter(
                    UserRecommendationFeedback.user_id == uid,
                    UserRecommendationFeedback.recommendation_id.in_(rec_ids),
                ).all()
                for fb in feedback_list:
                    fb.criteria_id = fb.recommendation.criteria_id
                    fb.package_id = fb.recommendation.package_id

                current_app.logger.info(
                    f"Evaluating user {uid}: {len(user_criteria)} criteria, {len(recommendations)} recommendations, {len(feedback_list)} feedback"
                )
                res = evaluate_user_satisfaction(
                    user_criteria,
                    recommendations,
                    feedback_list,
                    k_values,
                    feedback_mode,
                    logger=current_app.logger,
                )
                results.append(
                    {
                        "user_id": uid,
                        "criteria_ids": crit_ids,
                        "feedback_mode": feedback_mode,
                        "results": res.get("results", {}),
                        "summary": res.get("summary", {}),
                    }
                )

            if not results:
                return (
                    jsonify(success=False, error="Tidak ada data untuk evaluasi"),
                    400,
                )

            html = "<h4>Tabel Hasil Evaluasi</h4>"
            for r in results:
                html += (
                    f"<h5>Pengguna {r['user_id']}, Kriteria {r['criteria_ids']}</h5>"
                )
                html += format_evaluation_results_html(r, k_values=k_values)

            first = results[0]["summary"]
            chart_data = {
                "precision": first.get("precision", 0),
                "recall": first.get("recall", 0),
                "ndcg": first.get("ndcg", 0),
                "hit_rate": first.get("hit_rate", 0),
                "processed_users": first.get("processed_users", 0),
                "total_criteria": first.get("total_criteria", 0),
                "total_feedback": first.get("total_feedback", 0),
            }

            return jsonify(
                success=True, data=chart_data, results=results, html_formatted=html
            )

    except Exception as e:
        tb = traceback.format_exc()
        current_app.logger.error(f"Kesalahan evaluate_by_type:\n{tb}")
        return jsonify(success=False, error=str(e)), 500

@app.route("/api/users", methods=["GET"])
def api_users():
    # Mengambil daftar semua pengguna non-admin untuk ditampilkan di dashboard admin.
    # Mengembalikan data pengguna dalam format JSON.
    if not is_logged_in() or not session.get("is_admin"):
        return jsonify(success=False, error="Access denied"), 403

    users = User.query.filter_by(is_admin=False).all()
    return jsonify(
        success=True,
        data=[
            {"id": u.id, "email": u.email, "created_at": u.created_at.isoformat()}
            for u in users
        ],
    )

@app.route("/api/feedback_list", methods=["GET"])
def api_feedback_list():
    # Mengambil daftar semua umpan balik pengguna untuk ditampilkan di dashboard admin.
    # Mengembalikan data umpan balik dalam format JSON.
    if not is_logged_in() or not session.get("is_admin"):
        return jsonify(success=False, error="Access denied"), 403

    feedback = UserRecommendationFeedback.query.join(
        User, UserRecommendationFeedback.user_id == User.id
    ).all()
    return jsonify(
        success=True,
        data=[
            {
                "user_email": f.user.email,
                "criteria_id": f.criteria_id,
                "package_id": f.package_id,
                "feedback_type": f.feedback_type,
                "timestamp": f.timestamp.isoformat(),
            }
            for f in feedback
        ],
    )

@app.route("/api/criteria_by_user", methods=["POST"])
def api_criteria_by_user():
    # Mengambil daftar kriteria wisata berdasarkan ID pengguna atau semua pengguna non-admin.
    # Mengembalikan data kriteria dalam format JSON.
    if not is_logged_in() or not session.get("is_admin"):
        return jsonify(success=False, error="Access denied"), 403

    data = request.get_json() or {}
    user_id = data.get("user_id")

    try:
        if user_id == "all":
            criteria = (
                UserCriteria.query.join(User).filter(User.is_admin == False).all()
            )
        else:
            criteria = UserCriteria.query.filter_by(id_user=user_id).all()

        return jsonify(
            {
                "success": True,
                "results": [
                    {
                        "id_kriteria": c.id_kriteria,
                        "username": c.username,
                        "kabupaten": c.kabupaten,
                        "min_harga_penginapan": c.min_harga_penginapan,
                        "max_harga_penginapan": c.max_harga_penginapan,
                        "metode_pencarian": c.metode_pencarian,
                        "jumlah_rekomendasi": c.jumlah_rekomendasi,
                    }
                    for c in criteria
                ],
            }
        )
    except Exception as e:
        current_app.logger.error(f"Error fetching criteria: {str(e)}", exc_info=True)
        return jsonify(success=False, error=str(e)), 500

@app.route("/api/feedback_summary", methods=["POST"])
def api_feedback_summary():
    # Menghasilkan ringkasan umpan balik (like/dislike) dalam bentuk pie chart menggunakan Plotly.
    # Mengembalikan data persentase dan div Plotly untuk ditampilkan di frontend.
    if not is_logged_in() or not session.get("is_admin"):
        return jsonify(success=False, error="Akses ditolak"), 403

    data = request.get_json() or {}
    user_id = data.get("user_id", "all")

    try:
        if user_id == "all":
            feedbacks = (
                UserRecommendationFeedback.query.join(
                    User, UserRecommendationFeedback.user_id == User.id
                )
                .filter(User.is_admin == False)
                .all()
            )
        else:
            feedbacks = UserRecommendationFeedback.query.filter_by(
                user_id=int(user_id)
            ).all()

        if not feedbacks:
            return jsonify(success=True, data={"like": 0, "dislike": 0})

        feedback_counts = {"like": 0, "dislike": 0}
        for fb in feedbacks:
            if fb.feedback_type in feedback_counts:
                feedback_counts[fb.feedback_type] += 1

        total = sum(feedback_counts.values())
        feedback_percentages = {
            "like": (feedback_counts["like"] / total * 100) if total > 0 else 0,
            "dislike": (feedback_counts["dislike"] / total * 100) if total > 0 else 0,
        }

        fig = go.Figure(
            data=[
                go.Pie(
                    labels=["Like", "Dislike"],
                    values=[feedback_counts["like"], feedback_counts["dislike"]],
                    marker_colors=["#F56960", "#6c757d"],
                    textinfo="percent+label",
                    hoverinfo="label+percent+value",
                )
            ]
        )
        fig.update_layout(
            title="Distribusi Feedback (Like/Dislike)",
            template="plotly_white",
            height=300,
        )

        plotly_div = plotly.io.to_html(fig, full_html=False, include_plotlyjs=False)
        return jsonify(
            {"success": True, "data": feedback_percentages, "plotly_div": plotly_div}
        )

    except Exception as e:
        current_app.logger.error(f"Error feedback_summary: {str(e)}", exc_info=True)
        return jsonify(success=False, error=str(e)), 500

@app.route("/api/recommendation_summary", methods=["POST"])
def api_recommendation_summary():
    # Menghasilkan ringkasan jumlah rekomendasi per kriteria dalam bentuk grafik kolom menggunakan Plotly.
    # Mengembalikan data jumlah dan div Plotly untuk ditampilkan di frontend.
    if not is_logged_in() or not session.get("is_admin"):
        return jsonify(success=False, error="Akses ditolak"), 403

    data = request.get_json() or {}
    user_id = data.get("user_id", "all")

    try:
        if user_id == "all":
            recommendations = (
                Recommendation.query.join(User, Recommendation.user_id == User.id)
                .filter(User.is_admin == False)
                .all()
            )
        else:
            recommendations = Recommendation.query.filter_by(user_id=int(user_id)).all()

        if not recommendations:
            return jsonify(success=True, data={})

        recommendation_counts = {}
        for rec in recommendations:
            crit_id = str(rec.criteria_id)
            recommendation_counts[crit_id] = recommendation_counts.get(crit_id, 0) + 1

        labels = [f"Kriteria {cid}" for cid in recommendation_counts.keys()]
        values = list(recommendation_counts.values())

        fig = go.Figure(
            data=[
                go.Bar(
                    x=labels,
                    y=values,
                    marker_color="#F56960",
                    textposition="auto",
                    hoverinfo="x+y",
                )
            ]
        )
        fig.update_layout(
            title="Jumlah Rekomendasi per Kriteria",
            template="plotly_white",
            height=300,
            xaxis_title="Kriteria",
            yaxis_title="Jumlah Rekomendasi",
            yaxis=dict(tickformat="d"),
        )

        plotly_div = plotly.io.to_html(fig, full_html=False, include_plotlyjs=False)
        return jsonify(
            {"success": True, "data": recommendation_counts, "plotly_div": plotly_div}
        )

    except Exception as e:
        current_app.logger.error(
            f"Error recommendation_summary: {str(e)}", exc_info=True
        )
        return jsonify(success=False, error=str(e)), 500

@app.route("/api/generate_evaluation_chart", methods=["POST"])
def generate_evaluation_chart():
    # Menghasilkan grafik evaluasi performa sistem (precision, recall, ndcg, hit_rate) dalam bentuk
    # grafik garis dan kolom menggunakan Plotly. Mengembalikan div Plotly dan hasil evaluasi dalam format HTML.
    if not is_logged_in() or not session.get("is_admin"):
        return jsonify(success=False, error="Akses ditolak"), 403

    data = request.get_json() or {}
    user_id = data.get("user_id")
    criteria_id = data.get("criteria_id")
    feedback_mode = data.get("feedback_mode", "all")
    k_values = data.get("k_values", [3, 5, 7])
    evaluation_mode = data.get("evaluation_mode", "per_user")

    current_app.logger.info(
        f"Processing /api/generate_evaluation_chart with user_id={user_id}, criteria_id={criteria_id}, evaluation_mode={evaluation_mode}, k_values={k_values}"
    )

    if not isinstance(k_values, list) or not all(
        isinstance(k, int) and k > 0 for k in k_values
    ):
        return (
            jsonify(
                success=False,
                error="Nilai K harus berupa daftar bilangan bulat positif",
            ),
            400,
        )

    if not user_id or not criteria_id:
        return jsonify(success=False, error="User ID dan Criteria ID diperlukan"), 400

    try:
        if evaluation_mode == "overall":
            users = User.query.filter_by(is_admin=False).all()
            user_ids = [u.id for u in users]
            all_user_criteria = (
                UserCriteria.query.join(User).filter(User.is_admin == False).all()
            )
            all_recommendations = (
                Recommendation.query.join(User).filter(User.is_admin == False).all()
            )
            all_feedback_list = (
                UserRecommendationFeedback.query.join(User)
                .filter(User.is_admin == False)
                .all()
            )
            for fb in all_feedback_list:
                fb.criteria_id = fb.recommendation.criteria_id
                fb.package_id = fb.recommendation.package_id

            if (
                not all_user_criteria
                or not all_recommendations
                or not all_feedback_list
            ):
                return (
                    jsonify(
                        success=False,
                        error="Tidak ada data kriteria, rekomendasi, atau masukan untuk evaluasi keseluruhan",
                    ),
                    400,
                )

            current_app.logger.info(
                f"Evaluating overall mode: {len(all_user_criteria)} criteria, {len(all_recommendations)} recommendations, {len(all_feedback_list)} feedback"
            )
            result = evaluate_user_satisfaction(
                all_user_criteria,
                all_recommendations,
                all_feedback_list,
                k_values,
                feedback_mode,
                logger=current_app.logger,
            )

            if not result.get("results"):
                return (
                    jsonify(
                        success=False,
                        error="Tidak ada hasil evaluasi yang valid. Pastikan terdapat setidaknya 2 masukan (like/dislike) yang cocok dengan rekomendasi.",
                    ),
                    400,
                )
        else:
            if user_id == "all":
                users = User.query.filter_by(is_admin=False).all()
                user_ids = [u.id for u in users]
            else:
                user_ids = [int(user_id)]

            results = []
            for uid in user_ids:
                if criteria_id == "all":
                    user_criteria = UserCriteria.query.filter_by(id_user=uid).all()
                else:
                    user_criteria = UserCriteria.query.filter_by(
                        id_user=uid, id_kriteria=int(criteria_id)
                    ).all()

                if not user_criteria:
                    current_app.logger.warning(
                        f"Pengguna {uid} tidak memiliki kriteria {criteria_id}"
                    )
                    continue

                crit_ids = [c.id_kriteria for c in user_criteria]
                recommendations = Recommendation.query.filter(
                    Recommendation.user_id == uid,
                    Recommendation.criteria_id.in_(crit_ids),
                ).all()
                if not recommendations:
                    current_app.logger.warning(
                        f"Pengguna {uid}: tidak ada rekomendasi untuk kriteria {crit_ids}"
                    )
                    continue

                rec_ids = [r.id for r in recommendations]
                feedback_list = UserRecommendationFeedback.query.filter(
                    UserRecommendationFeedback.user_id == uid,
                    UserRecommendationFeedback.recommendation_id.in_(rec_ids),
                ).all()
                for fb in feedback_list:
                    fb.criteria_id = fb.recommendation.criteria_id
                    fb.package_id = fb.recommendation.package_id

                current_app.logger.info(
                    f"Evaluating user {uid}: {len(user_criteria)} criteria, {len(recommendations)} recommendations, {len(feedback_list)} feedback"
                )
                res = evaluate_user_satisfaction(
                    user_criteria,
                    recommendations,
                    feedback_list,
                    k_values,
                    feedback_mode,
                    logger=current_app.logger,
                )
                if not res.get("results"):
                    current_app.logger.warning(
                        f"Pengguna {uid}: tidak ada hasil evaluasi"
                    )
                    continue

                results.append(
                    {
                        "user_id": uid,
                        "criteria_ids": crit_ids,
                        "feedback_mode": feedback_mode,
                        "results": res.get("results", {}),
                        "summary": res.get("summary", {}),
                    }
                )

            if not results:
                return (
                    jsonify(
                        success=False,
                        error="Tidak ada data evaluasi yang tersedia untuk pengguna dan kriteria yang dipilih",
                    ),
                    400,
                )

            result = results[0]

        fig = make_subplots(
            rows=2,
            cols=1,
            subplot_titles=["Metrik Evaluasi (Garis)", "Metrik Evaluasi (Kolom)"],
            vertical_spacing=0.15,
        )

        colors = px.colors.qualitative.Plotly[:4]
        metrics = ["precision", "recall", "ndcg", "hit_rate"]
        metric_names = ["Precision@k", "Recall@k", "NDCG@k", "Hit Rate@k"]
        valid_traces = 0

        for idx, metric in enumerate(metrics):
            y_values = [
                result["results"].get(str(k), {}).get(metric, {}).get("mean", 0)
                for k in k_values
            ]
            if any(y > 0 for y in y_values):
                fig.add_trace(
                    go.Scatter(
                        x=k_values,
                        y=y_values,
                        mode="lines+markers",
                        name=metric_names[idx],
                        line=dict(color=colors[idx]),
                        marker=dict(size=8),
                    ),
                    row=1,
                    col=1,
                )
                valid_traces += 1

        for idx, k in enumerate(k_values):
            metrics_values = [
                result["results"].get(str(k), {}).get(metric, {}).get("mean", 0)
                for metric in metrics
            ]
            if any(m > 0 for m in metrics_values):
                fig.add_trace(
                    go.Bar(
                        x=metric_names,
                        y=metrics_values,
                        name=f"K={k}",
                        marker_color=colors[idx % len(colors)],
                    ),
                    row=2,
                    col=1,
                )
                valid_traces += 1

        if valid_traces == 0:
            fig.add_annotation(
                text="Tidak ada data metrik yang valid untuk dirender.<br>Pastikan masukan 'like' cocok dengan rekomendasi dan jumlah rekomendasi cukup untuk nilai K.",
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=14),
                align="center",
            )
            fig.update_layout(
                height=800,
                showlegend=False,
                template="plotly_white",
                title=(
                    "Evaluasi Sistem Rekomendasi (Keseluruhan)"
                    if evaluation_mode == "overall"
                    else "Evaluasi Sistem Rekomendasi (Per Pengguna)"
                ),
            )
        else:
            fig.update_layout(
                height=800,
                showlegend=True,
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5
                ),
                template="plotly_white",
                title=(
                    "Evaluasi Sistem Rekomendasi (Keseluruhan)"
                    if evaluation_mode == "overall"
                    else "Evaluasi Sistem Rekomendasi (Per Pengguna)"
                ),
            )
            fig.update_yaxes(title_text="Skor", row=1, col=1, range=[0, 1])
            fig.update_yaxes(title_text="Skor", row=2, col=1, range=[0, 1])
            fig.update_xaxes(title_text="Nilai K", row=1, col=1)
            fig.update_xaxes(title_text="Metrik", row=2, col=1)

        plotly_div = plotly.io.to_html(fig, full_html=False, include_plotlyjs=False)
        current_app.logger.info(
            f"Plotly div dihasilkan, panjang: {len(plotly_div)} karakter"
        )

        html = "<h4>Hasil Evaluasi</h4>"
        if evaluation_mode == "overall":
            html += "<h5>Evaluasi Keseluruhan (Semua Pengguna dan Kriteria)</h5>"
            html += format_evaluation_results_html(result, k_values=k_values)
        else:
            for r in results:
                html += (
                    f"<h5>Pengguna {r['user_id']}, Kriteria {r['criteria_ids']}</h5>"
                )
                html += format_evaluation_results_html(r, k_values=k_values)

        return jsonify(
            {
                "success": True,
                "plotly_div": plotly_div,
                "html_formatted": html,
                "results": [result] if evaluation_mode == "overall" else results,
            }
        )

    except Exception as e:
        tb = traceback.format_exc()
        current_app.logger.error(f"Kesalahan generate_evaluation_chart:\n{tb}")
        return jsonify(success=False, error=str(e)), 500

@app.route("/export_all_evaluations", methods=["POST"])
def export_all_evaluations_route():
    # Mengekspor hasil evaluasi performa sistem ke file CSV berdasarkan mode evaluasi
    # (per pengguna atau keseluruhan). Mengembalikan file CSV sebagai lampiran.
    data = request.get_json() or {}
    user_id = data.get("user_id")
    criteria_id = data.get("criteria_id")
    feedback_mode = data.get("feedback_mode", "all")
    k_values = data.get("k_values", [3, 5, 7])
    evaluation_mode = data.get("evaluation_mode", "per_user")

    if not user_id:
        return jsonify(success=False, error="user_id diperlukan"), 400

    try:
        if evaluation_mode == "overall":
            file_path, error = export_all_evaluations_to_csv(
                user_id=user_id,
                criteria_id=None,
                k_values=k_values,
                feedback_mode=feedback_mode,
                overall_mode=True,
            )
        else:
            file_path, error = export_all_evaluations_to_csv(
                user_id=int(user_id),
                criteria_id=(
                    (None if criteria_id == "all" else int(criteria_id))
                    if criteria_id
                    else None
                ),
                k_values=k_values,
                feedback_mode=feedback_mode,
            )

        if error:
            return jsonify(success=False, error=error), 400

        return send_file(
            file_path,
            mimetype="text/csv",
            as_attachment=True,
            download_name=f'evaluation_{"overall" if evaluation_mode == "overall" else f"user_{user_id}"}.csv',
        )

    except Exception as e:
        current_app.logger.error(f"Error export_all_evaluations: {e}", exc_info=True)
        return jsonify(success=False, error=str(e)), 500

@app.route("/admin/delete_user/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    # Menghapus pengguna beserta data terkait dari database. Hanya dapat dilakukan oleh admin.
    if not is_logged_in() or not session.get("is_admin"):
        return (
            jsonify(
                success=False,
                error="Akses ditolak: Hanya admin yang dapat menghapus pengguna",
            ),
            403,
        )

    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify(success=False, error="Pengguna tidak ditemukan"), 404

        db.session.delete(user)
        db.session.commit()

        current_app.logger.info(
            f"Pengguna {user_id} ({user.username}) berhasil dihapus oleh admin {session['user_id']}"
        )
        return jsonify(success=True, message=f"Pengguna {user.username} telah dihapus")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Gagal menghapus pengguna {user_id}: {str(e)}")
        return jsonify(success=False, error=str(e)), 500

@app.route("/admin/delete_criteria/<int:criteria_id>", methods=["POST"])
def delete_criteria(criteria_id):
    # Menghapus kriteria wisata dari database. Hanya dapat dilakukan oleh admin.
    if not is_logged_in() or not session.get("is_admin"):
        return jsonify(success=False, error="Akses ditolak: Hanya admin yang dapat menghapus kriteria"), 403
    try:
        criteria = UserCriteria.query.get(criteria_id)
        if not criteria:
            return jsonify(success=False, error="Kriteria tidak ditemukan"), 404
        db.session.delete(criteria)
        db.session.commit()
        current_app.logger.info(
            f"Kriteria {criteria_id} untuk pengguna {criteria.id_user} berhasil dihapus oleh admin {session['user_id']}"
        )
        return jsonify(success=True, message=f"Kriteria {criteria_id} telah dihapus")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Gagal menghapus kriteria {criteria_id}: {str(e)}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/admin/delete_recommendation/<int:rec_id>', methods=['POST'])
def delete_recommendation(rec_id):
    # Menghapus rekomendasi wisata dari database. Hanya dapat dilakukan oleh admin.
    rec = Recommendation.query.get(rec_id)
    if not rec:
        return jsonify(success=False,
        error=f"Rekomendasi dengan ID {rec_id} tidak ditemukan"), 404

    db.session.delete(rec)
    db.session.commit()
    return jsonify(success=True,
    message=f"Rekomendasi (ID {rec_id}) berhasil dihapus")

@app.route("/admin/delete_feedback/<int:feedback_id>", methods=["POST"])
def delete_feedback(feedback_id):
    # Menghapus umpan balik pengguna dari database. Hanya dapat dilakukan oleh admin.
    if not is_logged_in() or not session.get("is_admin"):
        return jsonify(success=False, error="Akses ditolak: Hanya admin yang dapat menghapus feedback"), 403
    try:
        feedback = UserRecommendationFeedback.query.get(feedback_id)
        if not feedback:
            return jsonify(success=False, error="Feedback tidak ditemukan"), 404
        db.session.delete(feedback)
        db.session.commit()
        current_app.logger.info(
            f"Feedback {feedback_id} untuk pengguna {feedback.user_id} berhasil dihapus oleh admin {session['user_id']}"
        )
        return jsonify(success=True, message=f"Feedback {feedback_id} telah dihapus")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Gagal menghapus feedback {feedback_id}: {str(e)}")
        return jsonify(success=False, error=str(e)), 500

@app.route("/export", methods=["POST"])
def export_to_csv():
    # Mengekspor daftar rekomendasi wisata ke file CSV berdasarkan data yang diterima.
    # File CSV mencakup detail seperti nama, rating, harga, dan jarak.
    data = request.json
    recs = data.get("recommendations", [])
    use_rev = data.get("use_reviews", False)
    if not recs:
        return jsonify(success=False, error="Tidak ada rekomendasi")

    fnames = [
        "no",
        "skor",
        "nama_penginapan",
        "rating_penginapan",
        "harga_penginapan",
        "nama_tempat_wisata_1",
        "kategori_tempat_wisata_1",
        "rating_tempat_wisata_1",
        "nama_tempat_wisata_2",
        "kategori_tempat_wisata_2",
        "rating_tempat_wisata_2",
        "nama_rumah_makan",
        "rating_rumah_makan",
        "jarak_penginapan_tempatwisata",
        "jarak_tempatwisata_rumahmakan",
        "jarak_penginapan_rumahmakan",
        "total_jarak",
    ]
    if use_rev:
        extras = [
            "jumlah_ulasan_penginapan",
            "jumlah_ulasan_tempat_wisata_1",
            "jumlah_ulasan_tempat_wisata_2",
            "jumlah_ulasan_rumah_makan",
        ]
        for fld in extras:
            idx = fnames.index(fld.replace("jumlah_ulasan_", "rating_")) + 1
            fnames.insert(idx, fld)

    tf = tempfile.NamedTemporaryFile(
        delete=False, mode="w", newline="", encoding="utf-8"
    )
    w = csv.DictWriter(tf, fieldnames=fnames)
    w.writeheader()

    for i, r in enumerate(recs, 1):
        jp = get_safe_value(r.get("jarak_penginapan_tempatwisata"), 0)
        jw = get_safe_value(r.get("jarak_tempatwisata_rumahmakan"), 0)
        jm = get_safe_value(r.get("jarak_penginapan_rumahmakan"), 0)
        tot = get_safe_value(r.get("total_jarak"), jp + jw + jm)
        row = {
            "no": i,
            "skor": round(get_safe_value(r.get("total_score"), 0), 4),
            "nama_penginapan": r["penginapan"]["nama"],
            "rating_penginapan": r["penginapan"]["rating"],
            "harga_penginapan": r["penginapan"]["harga"],
            "nama_tempat_wisata_1": r["tempat_wisata_1"]["nama"],
            "kategori_tempat_wisata_1": r["tempat_wisata_1"]["kategori"],
            "rating_tempat_wisata_1": r["tempat_wisata_1"]["rating"],
            "nama_tempat_wisata_2": r["tempat_wisata_2"]["nama"],
            "kategori_tempat_wisata_2": r["tempat_wisata_2"]["kategori"],
            "rating_tempat_wisata_2": r["tempat_wisata_2"]["rating"],
            "nama_rumah_makan": r["rumah_makan"]["nama"],
            "rating_rumah_makan": r["rumah_makan"]["rating"],
            "jarak_penginapan_tempatwisata": round(jp, 2),
            "jarak_tempatwisata_rumahmakan": round(jw, 2),
            "jarak_penginapan_rumahmakan": round(jm, 2),
            "total_jarak": round(tot, 2),
        }
        if use_rev:
            row.update(
                {
                    "jumlah_ulasan_penginapan": r["penginapan"].get("jumlah_ulasan", 0),
                    "jumlah_ulasan_tempat_wisata_1": r["tempat_wisata_1"].get(
                        "jumlah_ulasan", 0
                    ),
                    "jumlah_ulasan_tempat_wisata_2": r["tempat_wisata_2"].get(
                        "jumlah_ulasan", 0
                    ),
                    "jumlah_ulasan_rumah_makan": r["rumah_makan"].get(
                        "jumlah_ulasan", 0
                    ),
                }
            )
        w.writerow(row)

    tf.close()
    return send_file(
        tf.name,
        as_attachment=True,
        download_name="rekomendasi_paket_wisata.csv",
        mimetype="text/csv",
    )

@app.route("/get_data")
def get_tourist_attractions():
    # Mengambil data tempat wisata dari file CSV dan mengembalikannya dalam format JSON.
    # Data mencakup informasi seperti nama, rating, jumlah ulasan, latitude, dan longitude.
    path = r"C:\Users\ASUS\Desktop\Skripsi\data\tourist_attraction.csv"
    try:
        arr = []
        with open(path, "r", encoding="utf-8") as f:
            rd = csv.DictReader(f)
            for r in rd:
                r["rating"] = float(r["rating"])
                r["jumlah_ulasan"] = int(r["jumlah_ulasan"])
                r["latitude"] = float(r["latitude"])
                r["longitude"] = float(r["longitude"])
                arr.append(r)
        return jsonify(arr)
    except FileNotFoundError:
        return jsonify(error="File tidak ditemukan"), 404
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route("/login", methods=["GET", "POST"])
def login():
    # Menangani proses login pengguna. Jika metode POST, memeriksa email dan kata sandi.
    # Jika berhasil, menyimpan informasi sesi dan mengarahkan ke halaman rekomendasi atau admin.
    if request.method == "POST":
        email = request.form.get("email")
        pwd = request.form.get("password")
        if not email or not pwd:
            flash("Harap masukkan email dan password", "danger")
            return render_template("login_register.html")
        u = User.query.filter_by(email=email).first()
        if u and check_password_hash(u.password, pwd):
            session["user_id"] = u.id
            session["username"] = u.username
            session["email"] = u.email
            session["is_admin"] = u.is_admin
            flash(
                f"Halo, {u.username}! Sudah siap memilih petualangan seru di Yogyakarta? Yuk, mulai perjalananmu!",
                "success",
            )
            if u.is_admin:
                return redirect(url_for("index_admin"))
            return redirect(url_for("recommendation"))
        flash("Email/password salah", "danger")
    return render_template("login_register.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    # Menangani proses pendaftaran pengguna baru. Memeriksa validitas input dan menyimpan
    # pengguna ke database dengan kata sandi yang di-hash.
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        pwd = request.form.get("password")
        if not username or not email or not pwd:
            flash("Harap lengkapi field", "danger")
            return render_template("login_register.html")
        if len(pwd) < 6:
            flash("Password minimal 6 karakter", "danger")
            return render_template("login_register.html")
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash("Email tidak valid", "danger")
            return render_template("login_register.html")
        ex = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        if ex:
            flash("Username/email sudah ada", "danger")
            return render_template("login_register.html")
        try:
            u = User(
                username=username, email=email, password=generate_password_hash(pwd)
            )
            db.session.add(u)
            db.session.commit()
            flash(
                f"Pendaftaran berhasil, {username}! Siap mulai petualanganmu di Yogyakarta?",
                "success",
            )
            return redirect(url_for("login"))
        except Exception as e:
            db.session.rollback()
            app.logger.error("Reg error", exc_info=True)
            flash("Terjadi kesalahan", "danger")
    return render_template("login_register.html")

@app.route("/logout")
def logout():
    # Menangani proses logout pengguna, menghapus data sesi, dan mengarahkan ke halaman utama.
    user = session.pop("username", "Pengguna")
    session.pop("user_id", None)
    session.pop("email", None)
    session.pop("is_admin", None)
    flash(
        f"Daaaah, {user}! Jangan lupa kembali lagi ya, Yogyakarta selalu siap menyambut petualangan baru!",
        "info",
    )
    return redirect(url_for("index"))

print(app.url_map)

if __name__ == "__main__":
    # Menjalankan aplikasi Flask dalam mode debug pada port 8080.
    app.run(debug=True, port=8080)