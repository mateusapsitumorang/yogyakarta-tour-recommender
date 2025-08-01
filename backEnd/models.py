"""
Modul untuk mendefinisikan model basis data dan fungsi pendukung untuk sistem rekomendasi.
Modul ini mencakup definisi model untuk pengguna, kriteria pengguna, rekomendasi, dan feedback,
serta fungsi untuk menghasilkan ID paket unik berdasarkan kombinasi entitas wisata.
"""
import uuid
import time
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, PrimaryKeyConstraint, ForeignKeyConstraint
)
from sqlalchemy.dialects.sqlite import JSON
import hashlib
from sqlalchemy import UniqueConstraint

# Inisialisasi objek SQLAlchemy untuk interaksi dengan basis data
db = SQLAlchemy()

class User(db.Model):
    """
    Model untuk menyimpan data pengguna dalam sistem.

    Atribut:
        id (int): Identifikasi unik pengguna (primary key).
        username (str): Nama pengguna (unik, maksimum 80 karakter).
        email (str): Alamat email pengguna (unik, maksimum 120 karakter).
        password (str): Kata sandi pengguna (maksimum 255 karakter).
        is_admin (bool): Status admin pengguna (default: False).
        created_at (datetime): Waktu pembuatan akun pengguna.
        criteria (relasi): Relasi ke model UserCriteria.
        recs (relasi): Relasi ke model Recommendation.
        feedbacks (relasi): Relasi ke model UserRecommendationFeedback.
    """
    __tablename__ = 'user'
    id         = Column(Integer, primary_key=True)
    username   = Column(String(80), unique=True, nullable=False)
    email      = Column(String(120), unique=True, nullable=False)
    password   = Column(String(255), nullable=False)
    is_admin   = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relasi ke model lain dengan cascade untuk menghapus data terkait
    criteria   = db.relationship('UserCriteria', backref='user', lazy=True, cascade='all, delete-orphan')
    recs       = db.relationship('Recommendation', backref='user', lazy=True, cascade='all, delete-orphan')
    feedbacks  = db.relationship('UserRecommendationFeedback', backref='user', lazy=True, cascade='all, delete-orphan')

def generate_package_id(penginapan_id=None, wisata1_id=None, wisata2_id=None, rumah_makan_id=None):
    """
    Menghasilkan ID unik untuk paket rekomendasi berdasarkan kombinasi ID penginapan, wisata, dan rumah makan.

    Fungsi ini menggunakan hash MD5 dari kombinasi ID dan memastikan ID unik dengan memeriksa basis data.
    Jika terjadi duplikasi, ID baru dihasilkan dengan menambahkan UUID.

    Args:
        penginapan_id (str, optional): ID penginapan.
        wisata1_id (str, optional): ID tempat wisata pertama.
        wisata2_id (str, optional): ID tempat wisata kedua.
        rumah_makan_id (str, optional): ID rumah makan.

    Returns:
        str: ID paket unik (12 karakter, huruf besar).
    """
    base = f"{penginapan_id or 'NA'}-{wisata1_id or 'NA'}-{wisata2_id or 'NA'}-{rumah_makan_id or 'NA'}"
    pid = hashlib.md5(base.encode()).hexdigest()[:12].upper()
    # cek DB
    while Recommendation.query.filter_by(package_id=pid).first():
        pid = hashlib.md5((base + str(uuid.uuid4())).encode()).hexdigest()[:12].upper()
    return pid

class UserCriteria(db.Model):
    """
    Model untuk menyimpan kriteria pencarian pengguna untuk rekomendasi.

    Atribut:
        id_kriteria (int): Identifikasi unik kriteria (primary key).
        id_user (int): ID pengguna terkait (foreign key ke tabel user).
        username (str): Nama pengguna (maksimum 255 karakter).
        email (str): Email pengguna (maksimum 255 karakter).
        kabupaten (str): Nama kabupaten untuk pencarian (maksimum 255 karakter).
        rating_tempat_wisata (float): Rating minimum tempat wisata.
        rating_penginapan (float): Rating minimum penginapan.
        rating_rumah_makan (float): Rating minimum rumah makan.
        kategori_wisata (str): Kategori wisata yang diinginkan (maksimum 255 karakter).
        min_harga_penginapan (float): Harga minimum penginapan.
        max_harga_penginapan (float): Harga maksimum penginapan.
        metode_pencarian (str): Metode pencarian yang digunakan (maksimum 255 karakter).
        jumlah_rekomendasi (int): Jumlah rekomendasi yang diinginkan.
        created_at (datetime): Waktu pembuatan kriteria.
    """
    __tablename__ = 'user_criteria'
    
    id_kriteria = db.Column(db.Integer, primary_key=True)
    id_user = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    username = db.Column(db.String(255))
    email = db.Column(db.String(255))
    kabupaten = db.Column(db.String(255))
    rating_tempat_wisata = db.Column(db.Float)
    rating_penginapan = db.Column(db.Float)
    rating_rumah_makan = db.Column(db.Float)
    kategori_wisata = db.Column(db.String(255))
    min_harga_penginapan = db.Column(db.Float)
    max_harga_penginapan = db.Column(db.Float)
    metode_pencarian = db.Column(db.String(255))
    jumlah_rekomendasi = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        """
        Mengkonversi objek UserCriteria menjadi dictionary.

        Returns:
            dict: Representasi dictionary dari atribut objek.
        """
        return {
            'id_kriteria': self.id_kriteria,
            'id_user': self.id_user,
            'username': self.username,
            'email': self.email,
            'kabupaten': self.kabupaten,
            'rating_tempat_wisata': self.rating_tempat_wisata,
            'rating_penginapan': self.rating_penginapan,
            'rating_rumah_makan': self.rating_rumah_makan,
            'kategori_wisata': self.kategori_wisata,
            'min_harga_penginapan': self.min_harga_penginapan,
            'max_harga_penginapan': self.max_harga_penginapan,
            'metode_pencarian': self.metode_pencarian,
            'jumlah_rekomendasi': self.jumlah_rekomendasi,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Recommendation(db.Model):
    """
    Model untuk menyimpan data rekomendasi yang dihasilkan untuk pengguna.

    Atribut:
        id (int): Identifikasi unik rekomendasi (primary key).
        criteria_id (int): ID kriteria terkait (foreign key ke tabel user_criteria).
        package_id (str): ID unik paket rekomendasi (maksimum 50 karakter).
        user_id (int): ID pengguna terkait (foreign key ke tabel user).
        skor (float): Skor rekomendasi.
        kabupaten_penginapan (str): Nama kabupaten penginapan (maksimum 100 karakter).
        nama_penginapan (str): Nama penginapan (maksimum 255 karakter).
        rating_penginapan (float): Rating penginapan.
        harga_penginapan (int): Harga penginapan.
        nama_wisata_1 (str): Nama tempat wisata pertama (maksimum 255 karakter).
        kategori_wisata_1 (str): Kategori tempat wisata pertama (maksimum 255 karakter).
        rating_wisata_1 (float): Rating tempat wisata pertama.
        nama_wisata_2 (str): Nama tempat wisata kedua (maksimum 255 karakter).
        kategori_wisata_2 (str): Kategori tempat wisata kedua (maksimum 255 karakter).
        rating_wisata_2 (float): Rating tempat wisata kedua.
        nama_rumah_makan (str): Nama rumah makan (maksimum 255 karakter).
        rating_rumah_makan (float): Rating rumah makan.
        recommendation_json (text): Data rekomendasi dalam format JSON.
        created_at (datetime): Waktu pembuatan rekomendasi.
        feedbacks (relasi): Relasi ke model UserRecommendationFeedback.
    """
    __tablename__ = 'recommendation'
    id = db.Column(db.Integer, primary_key=True)
    criteria_id = db.Column(db.Integer, db.ForeignKey('user_criteria.id_kriteria', ondelete='CASCADE'), nullable=False)
    package_id  = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    skor = db.Column(db.Float)
    kabupaten_penginapan = db.Column(db.String(100))
    nama_penginapan = db.Column(db.String(255))
    rating_penginapan = db.Column(db.Float, nullable=True)
    harga_penginapan = db.Column(db.Integer, nullable=True)
    nama_wisata_1 = db.Column(db.String(255))
    kategori_wisata_1 = db.Column(db.String(255), nullable=True)
    rating_wisata_1 = db.Column(db.Float, nullable=True)
    nama_wisata_2 = db.Column(db.String(255))
    kategori_wisata_2 = db.Column(db.String(255), nullable=True)
    rating_wisata_2 = db.Column(db.Float, nullable=True)
    nama_rumah_makan = db.Column(db.String(255))
    rating_rumah_makan = db.Column(db.Float, nullable=True)
    recommendation_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('criteria_id','package_id', name='uq_crit_pkg'),
        db.Index('idx_recommendation_user_id', 'user_id'),
    )

    feedbacks = db.relationship(
        'UserRecommendationFeedback',
        back_populates='recommendation',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

class UserRecommendationFeedback(db.Model):
    """
    Model untuk menyimpan feedback pengguna terhadap rekomendasi.

    Atribut:
        id (int): Identifikasi unik feedback (primary key).
        recommendation_id (int): ID rekomendasi terkait (foreign key ke tabel recommendation).
        user_id (int): ID pengguna terkait (foreign key ke tabel user).
        user_name (str): Nama pengguna yang memberikan feedback (maksimum 80 karakter).
        feedback_type (str): Jenis feedback, misalnya 'like' atau 'dislike' (maksimum 20 karakter).
        score (float): Skor feedback (opsional).
        created_at (datetime): Waktu pembuatan feedback.
        recommendation (relasi): Relasi ke model Recommendation.
    """
    __tablename__ = 'user_recommendation_feedback'
    id = db.Column(db.Integer, primary_key=True)
    recommendation_id = db.Column(db.Integer, db.ForeignKey('recommendation.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    user_name = db.Column(db.String(80), nullable=False)
    feedback_type = db.Column(db.String(20), nullable=False)
    score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    recommendation = db.relationship(
        'Recommendation',
        back_populates='feedbacks',
        lazy='joined'
    )