"""
Code untuk mengimplementasikan algoritma Path Ranking
untuk rekomendasi paket wisata berdasarkan jarak dan kriteria yang ditentukan.
"""

import logging
from neo4j import GraphDatabase
from config import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
    PRA_WEIGHTS,
    NUM_RECOMMENDATIONS,
)
import uuid
import math
from collections import defaultdict
from utils import (
    get_safe_value,
    normalize_rating,
    estimate_review_count,
    calculate_path_score,
)
from utils import generate_package_id

# Konfigurasi logging untuk debugging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Fungsi untuk menghasilkan tautan Google Maps sebagai cadangan
def generate_google_maps_link(lat, lon, name):
    """
    Menghasilkan tautan Google Maps berdasarkan koordinat dan nama lokasi.
    
    Args:
        lat (float): Latitude lokasi.
        lon (float): Longitude lokasi.
        name (str): Nama lokasi.
    
    Returns:
        str: URL Google Maps.
    """
    name_encoded = name.replace(" ", "+").strip()
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}&query_place_id={name_encoded}"

# Kelas untuk mengatur koneksi ke Neo4j dan menjalankan path ranking algorithm
class PathRankingAlgorithm:
    def __init__(self, uri, username, password):
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self.weights = PRA_WEIGHTS

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self.driver.close()

    def run_query(self, query, parameters=None):
        try:
            with self.driver.session() as session:
                result = session.run(query, parameters)
                return list(result)
        except Exception as e:
            logger.error(f"Error saat menjalankan query: {e}", exc_info=True)
            raise

    def get_recommendations(self, criteria):
        logger.info(f"Menjalankan query dengan kriteria: {criteria}")
        params = {
            "kabupaten": criteria.get("kabupaten", None),
            "kategori_wisata": criteria.get("kategori_wisata", None),
            "min_rating_tempat_wisata": criteria.get("min_rating_tempat_wisata", 0),
            "min_harga_penginapan": criteria.get("min_harga_penginapan", 0),
            "max_harga_penginapan": criteria.get("max_harga_penginapan", 1500000),
            "min_rating_penginapan": criteria.get("min_rating_penginapan", 0),
            "min_rating_rumah_makan": criteria.get("min_rating_rumah_makan", 0),
            "use_reviews": criteria.get("use_reviews", False),
            "num_desired": int(criteria.get("num_recommendations", NUM_RECOMMENDATIONS)),
            "debug_mode": criteria.get("debug_mode", False),
        }

        pra_params = {
            "weight_path": self.weights["path_score"],
            "weight_tw1": 0.0,
            "weight_tw2": 0.0,
            "weight_jumlah_ulasan_tw1": 0.0,
            "weight_jumlah_ulasan_tw2": 0.0,
            "weight_jumlah_ulasan_p": 0.0,
            "weight_jumlah_ulasan_rm": 0.0,
            "weight_kat_tw1": self.weights["kategori_tempat_wisata_1"],
            "weight_kat_tw2": self.weights["kategori_tempat_wisata_2"],
            "weight_p": 0.0,
            "weight_harga": self.weights["harga_penginapan"],
            "weight_rm": 0.0,
            "limit": params["num_desired"],
        }

        review_weight_sum = (
            self.weights["jumlah_ulasan_tempat_wisata_1"]
            + self.weights["jumlah_ulasan_tempat_wisata_2"]
            + self.weights["jumlah_ulasan_penginapan"]
            + self.weights["jumlah_ulasan_rumah_makan"]
        )
        num_rating_entities = 4
        extra_rating_weight = review_weight_sum / num_rating_entities

        if not params["use_reviews"]:
            logger.info("use_reviews tidak aktif: hanya mempertimbangkan rating, jumlah ulasan diatur ke 0")
            pra_params.update(
                {
                    "weight_jumlah_ulasan_tw1": 0.0,
                    "weight_jumlah_ulasan_tw2": 0.0,
                    "weight_jumlah_ulasan_p": 0.0,
                    "weight_jumlah_ulasan_rm": 0.0,
                    "weight_tw1": self.weights["rating_tempat_wisata_1"] + extra_rating_weight,
                    "weight_tw2": self.weights["rating_tempat_wisata_2"] + extra_rating_weight,
                    "weight_p": self.weights["rating_penginapan"] + extra_rating_weight,
                    "weight_rm": self.weights["rating_rumah_makan"] + extra_rating_weight,
                }
            )
            total_weight = (
                pra_params["weight_path"]
                + pra_params["weight_tw1"]
                + pra_params["weight_tw2"]
                + pra_params["weight_p"]
                + pra_params["weight_rm"]
                + pra_params["weight_kat_tw1"]
                + pra_params["weight_kat_tw2"]
                + pra_params["weight_harga"]
            )
            logger.info(f"Total bobot tanpa ulasan: {total_weight}")
        else:
            logger.info("use_reviews aktif: menggunakan bobot dengan ulasan dari PRA_WEIGHTS")
            pra_params.update(
                {
                    "weight_jumlah_ulasan_tw1": self.weights["jumlah_ulasan_tempat_wisata_1"],
                    "weight_jumlah_ulasan_tw2": self.weights["jumlah_ulasan_tempat_wisata_2"],
                    "weight_jumlah_ulasan_p": self.weights["jumlah_ulasan_penginapan"],
                    "weight_jumlah_ulasan_rm": self.weights["jumlah_ulasan_rumah_makan"],
                    "weight_tw1": self.weights["rating_tempat_wisata_1"],
                    "weight_tw2": self.weights["rating_tempat_wisata_2"],
                    "weight_p": self.weights["rating_penginapan"],
                    "weight_rm": self.weights["rating_rumah_makan"],
                }
            )
            total_weight = (
                pra_params["weight_path"]
                + pra_params["weight_tw1"]
                + pra_params["weight_tw2"]
                + pra_params["weight_p"]
                + pra_params["weight_rm"]
                + pra_params["weight_kat_tw1"]
                + pra_params["weight_kat_tw2"]
                + pra_params["weight_harga"]
                + pra_params["weight_jumlah_ulasan_tw1"]
                + pra_params["weight_jumlah_ulasan_tw2"]
                + pra_params["weight_jumlah_ulasan_p"]
                + pra_params["weight_jumlah_ulasan_rm"]
            )
            logger.info(f"Total bobot dengan ulasan: {total_weight}")

        if isinstance(params["kabupaten"], str):
            params["kabupaten"] = [params["kabupaten"]]

        if params["num_desired"] <= 0:
            logger.warning(f"Nilai num_desired tidak valid: {params['num_desired']}, menggunakan default {NUM_RECOMMENDATIONS}")
            params["num_desired"] = NUM_RECOMMENDATIONS
            pra_params["limit"] = NUM_RECOMMENDATIONS

        kabupaten_list = params["kabupaten"] if params["kabupaten"] else []
        recommendations = []

        if len(kabupaten_list) <= 1:
            params.update(pra_params)
            logger.info(f"Parameter query untuk satu kabupaten: {params}")
            query = self._build_cypher_query(params)
            try:
                results = self.run_query(query, params)
                logger.info(f"Jumlah hasil query: {len(results)}")
                recommendations = self._process_query_results(results, params["use_reviews"])
            except Exception as e:
                logger.error(f"Error saat menjalankan query: {e}", exc_info=True)
                return []
        else:
            results_per_kabupaten = max(1, params["num_desired"] // len(kabupaten_list))
            logger.info(f"Hasil per kabupaten: {results_per_kabupaten}")

            for kab in kabupaten_list:
                kab_params = params.copy()
                kab_params["kabupaten"] = [kab]
                kab_params["limit"] = results_per_kabupaten
                kab_params.update(pra_params)
                logger.info(f"Parameter query untuk kabupaten {kab}: {kab_params}")
                query = self._build_cypher_query(kab_params)
                try:
                    results = self.run_query(query, kab_params)
                    logger.info(f"Jumlah hasil untuk kabupaten {kab}: {len(results)}")
                    recommendations.extend(self._process_query_results(results, params["use_reviews"]))
                except Exception as e:
                    logger.error(f"Error saat menjalankan query untuk {kab}: {e}", exc_info=True)

            recommendations.sort(key=lambda x: x["total_score"], reverse=True)
            recommendations = recommendations[:params["num_desired"]]

        kabupaten_counts = defaultdict(int)
        for rec in recommendations:
            kabupaten_counts[rec["kabupaten_penginapan"]] += 1
        logger.info(f"Distribusi kabupaten dalam hasil: {dict(kabupaten_counts)}")

        if params["debug_mode"]:
            self._print_detailed_calculations(recommendations[:10])

        return recommendations

    def _build_cypher_query(self, params):
        """
        Membangun query Cypher untuk mencari jalur rekomendasi berdasarkan parameter.
        
        Args:
            params (dict): Parameter query (kriteria dan bobot).
        
        Returns:
            str: Query Cypher yang dibangun.
        """
        query = """
        MATCH (p:Penginapan)-[r1:ADA_AKSES_MENUJU]->(tw1:TempatWisata)
        MATCH (tw1)-[r2:ADA_AKSES_MENUJU]->(rm:RumahMakan)
        MATCH (p)-[r3:ADA_AKSES_MENUJU]->(tw2:TempatWisata)
        WHERE tw1 <> tw2
        AND tw1.rating >= $min_rating_tempat_wisata
        AND tw2.rating >= $min_rating_tempat_wisata
        AND p.rating >= $min_rating_penginapan
        AND p.harga >= $min_harga_penginapan
        AND p.harga <= $max_harga_penginapan
        AND rm.rating >= $min_rating_rumah_makan
        """

        if params["kategori_wisata"]:
            query += """
        AND tw1.kategori = $kategori_wisata
        AND tw2.kategori = $kategori_wisata
        """

        if params["kabupaten"]:
            query += """
        MATCH (p)-[:BERADA_DI]->(kp:Kabupaten)
        MATCH (tw1)-[:BERADA_DI]->(ktw1:Kabupaten)
        MATCH (tw2)-[:BERADA_DI]->(ktw2:Kabupaten)
        MATCH (rm)-[:BERADA_DI]->(krm:Kabupaten)
        WHERE kp.nama = ktw1.nama 
        AND kp.nama = ktw2.nama 
        AND kp.nama = krm.nama 
        AND kp.nama IN $kabupaten
        """
        else:
            query += """
        MATCH (p)-[:BERADA_DI]->(kp:Kabupaten)
        MATCH (tw1)-[:BERADA_DI]->(ktw1:Kabupaten)
        MATCH (tw2)-[:BERADA_DI]->(ktw2:Kabupaten)
        MATCH (rm)-[:BERADA_DI]->(krm:Kabupaten)
        WHERE kp.nama = ktw1.nama 
        AND kp.nama = ktw2.nama 
        AND kp.nama = krm.nama
        """

        query += """
        WITH p, tw1, tw2, rm, r1, r2, r3, 
             kp.nama AS kabupaten_p, ktw1.nama AS kabupaten_tw1, 
             ktw2.nama AS kabupaten_tw2, krm.nama AS kabupaten_rm,
            r1.jarak AS jarak_penginapan_tempatwisata, 
            r2.jarak AS jarak_tempatwisata_rumahmakan, 
            r3.jarak AS jarak_penginapan_rumahmakan, 
            1.0 / (r1.jarak + r2.jarak + r3.jarak) AS path_score,
            1.0 / r1.jarak AS weight_p_to_tw1,
            [(p)-[r:ADA_AKSES_MENUJU]->(tw:TempatWisata) | 1.0 / r.jarak] AS weights_p_to_all_tw,
            CASE WHEN size([(p)-[r:ADA_AKSES_MENUJU]->(tw:TempatWisata) | 1.0 / r.jarak]) > 0
                THEN 1.0 / r1.jarak / reduce(sum = 0.0, w IN [(p)-[r:ADA_AKSES_MENUJU]->(tw:TempatWisata) | 1.0 / r.jarak] | sum + w)
                ELSE 0.0
            END AS prob_trans_p_to_tw1,
            1.0 / r2.jarak AS weight_tw1_to_rm,
            [(tw1)-[r:ADA_AKSES_MENUJU]->(rm_neighbor:RumahMakan) | 1.0 / r.jarak] AS weights_tw1_to_all_rm,
            CASE WHEN size([(tw1)-[r:ADA_AKSES_MENUJU]->(rm_neighbor:RumahMakan) | 1.0 / r.jarak]) > 0
                THEN 1.0 / r2.jarak / reduce(sum = 0.0, w IN [(tw1)-[r:ADA_AKSES_MENUJU]->(rm_neighbor:RumahMakan) | 1.0 / r.jarak] | sum + w)
                ELSE 0.0
            END AS prob_trans_tw1_to_rm,
            1.0 / r3.jarak AS weight_p_to_tw2,
            [(p)-[r:ADA_AKSES_MENUJU]->(tw:TempatWisata) | 1.0 / r.jarak] AS weights_p_to_all_tw2,
            CASE WHEN size([(p)-[r:ADA_AKSES_MENUJU]->(tw:TempatWisata) | 1.0 / r.jarak]) > 0
                THEN 1.0 / r3.jarak / reduce(sum = 0.0, w IN [(p)-[r:ADA_AKSES_MENUJU]->(tw:TempatWisata) | 1.0 / r.jarak] | sum + w)
                ELSE 0.0
            END AS prob_trans_p_to_tw2,
            p.rating / 5.0 AS rating_p_normalized,
            tw1.rating / 5.0 AS rating_tw1_normalized,
            tw2.rating / 5.0 AS rating_tw2_normalized,
            rm.rating / 5.0 AS rating_rm_normalized,
            CASE 
                WHEN p.harga >= $min_harga_penginapan AND p.harga <= $max_harga_penginapan 
                THEN 1.0 - ((p.harga - $min_harga_penginapan) / ($max_harga_penginapan - $min_harga_penginapan + 1)) 
                ELSE 0.5 
            END AS harga_p_normalized,
            CASE WHEN tw1.jumlah_ulasan IS NULL THEN 0 ELSE log10(1 + tw1.jumlah_ulasan) / 3 END AS ulasan_tw1_normalized,
            CASE WHEN tw2.jumlah_ulasan IS NULL THEN 0 ELSE log10(1 + tw2.jumlah_ulasan) / 3 END AS ulasan_tw2_normalized,
            CASE WHEN p.jumlah_ulasan IS NULL THEN 0 ELSE log10(1 + p.jumlah_ulasan) / 3 END AS ulasan_p_normalized,
            CASE WHEN rm.jumlah_ulasan IS NULL THEN 0 ELSE log10(1 + rm.jumlah_ulasan) / 3 END AS ulasan_rm_normalized,
            CASE WHEN tw1.kategori = $kategori_wisata THEN 1.0 ELSE 0.0 END AS kategori_tw1_score,
            CASE WHEN tw2.kategori = $kategori_wisata THEN 1.0 ELSE 0.0 END AS kategori_tw2_score,
            p.id AS id_penginapan,
            p.nama AS nama_penginapan,
            p.rating AS rating_penginapan,
            p.harga AS harga_penginapan,
            COALESCE(p.google_maps_link, '') AS google_maps_link_penginapan,
            tw1.id AS id_tempat_wisata_1,
            tw1.nama AS nama_tempat_wisata_1,
            tw1.kategori AS kategori_tempat_wisata_1,
            tw1.rating AS rating_tempat_wisata_1,
            COALESCE(tw1.google_maps_link, '') AS google_maps_link_tempat_wisata_1,
            tw2.id AS id_tempat_wisata_2,
            tw2.nama AS nama_tempat_wisata_2,
            tw2.kategori AS kategori_tempat_wisata_2,
            tw2.rating AS rating_tempat_wisata_2,
            COALESCE(tw2.google_maps_link, '') AS google_maps_link_tempat_wisata_2,
            rm.id AS id_rumah_makan,
            rm.nama AS nama_rumah_makan,
            rm.rating AS rating_rumah_makan,
            COALESCE(rm.google_maps_link, '') AS google_maps_link_rumah_makan,
            p.jumlah_ulasan AS jumlah_ulasan_penginapan,
            tw1.jumlah_ulasan AS jumlah_ulasan_tempat_wisata_1,
            tw2.jumlah_ulasan AS jumlah_ulasan_tempat_wisata_2,
            rm.jumlah_ulasan AS jumlah_ulasan_rumah_makan,
            p.latitude AS latitude_penginapan,
            p.longitude AS longitude_penginapan,
            tw1.latitude AS latitude_tempat_wisata_1,
            tw1.longitude AS longitude_tempat_wisata_1,
            tw2.latitude AS latitude_tempat_wisata_2,
            tw2.longitude AS longitude_tempat_wisata_2,
            rm.latitude AS latitude_rumah_makan,
            rm.longitude AS longitude_rumah_makan

        WITH p, tw1, tw2, rm, r1, r2, r3,
            kabupaten_p, kabupaten_tw1, kabupaten_tw2, kabupaten_rm,
            jarak_penginapan_tempatwisata,
            jarak_tempatwisata_rumahmakan,
            jarak_penginapan_rumahmakan,
            (jarak_penginapan_tempatwisata + jarak_tempatwisata_rumahmakan + jarak_penginapan_rumahmakan) AS total_jarak,
            path_score,
            prob_trans_p_to_tw1,
            prob_trans_tw1_to_rm,
            prob_trans_p_to_tw2,
            rating_p_normalized,
            rating_tw1_normalized,
            rating_tw2_normalized,
            rating_rm_normalized,
            harga_p_normalized,
            ulasan_tw1_normalized,
            ulasan_tw2_normalized,
            ulasan_p_normalized,
            ulasan_rm_normalized,
            kategori_tw1_score,
            kategori_tw2_score,
            id_penginapan,
            nama_penginapan,
            rating_penginapan,
            harga_penginapan,
            google_maps_link_penginapan,
            id_tempat_wisata_1,
            nama_tempat_wisata_1,
            kategori_tempat_wisata_1,
            rating_tempat_wisata_1,
            google_maps_link_tempat_wisata_1,
            id_tempat_wisata_2,
            nama_tempat_wisata_2,
            kategori_tempat_wisata_2,
            rating_tempat_wisata_2,
            google_maps_link_tempat_wisata_2,
            id_rumah_makan,
            nama_rumah_makan,
            rating_rumah_makan,
            google_maps_link_rumah_makan,
            jumlah_ulasan_penginapan,
            jumlah_ulasan_tempat_wisata_1,
            jumlah_ulasan_tempat_wisata_2,
            jumlah_ulasan_rumah_makan,
            latitude_penginapan,
            longitude_penginapan,
            latitude_tempat_wisata_1,
            longitude_tempat_wisata_1,
            latitude_tempat_wisata_2,
            longitude_tempat_wisata_2,
            latitude_rumah_makan,
            longitude_rumah_makan

        WITH p, tw1, tw2, rm, r1, r2, r3,
            jarak_penginapan_tempatwisata,
            jarak_tempatwisata_rumahmakan,
            jarak_penginapan_rumahmakan,
            total_jarak,
            (
                path_score * $weight_path +
                rating_tw1_normalized * $weight_tw1 +
                rating_tw2_normalized * $weight_tw2 +
                kategori_tw1_score * $weight_kat_tw1 +
                kategori_tw2_score * $weight_kat_tw2 +
                rating_p_normalized * $weight_p +
                harga_p_normalized * $weight_harga +
                rating_rm_normalized * $weight_rm +
                ulasan_tw1_normalized * $weight_jumlah_ulasan_tw1 +
                ulasan_tw2_normalized * $weight_jumlah_ulasan_tw2 +
                ulasan_p_normalized * $weight_jumlah_ulasan_p +
                ulasan_rm_normalized * $weight_jumlah_ulasan_rm
            ) AS total_score,
            id_penginapan,
            nama_penginapan,
            rating_penginapan,
            harga_penginapan,
            google_maps_link_penginapan,
            id_tempat_wisata_1,
            nama_tempat_wisata_1,
            kategori_tempat_wisata_1,
            rating_tempat_wisata_1,
            google_maps_link_tempat_wisata_1,
            id_tempat_wisata_2,
            nama_tempat_wisata_2,
            kategori_tempat_wisata_2,
            rating_tempat_wisata_2,
            google_maps_link_tempat_wisata_2,
            id_rumah_makan,
            nama_rumah_makan,
            rating_rumah_makan,
            google_maps_link_rumah_makan,
            jumlah_ulasan_penginapan,
            jumlah_ulasan_tempat_wisata_1,
            jumlah_ulasan_tempat_wisata_2,
            jumlah_ulasan_rumah_makan,
            latitude_penginapan,
            longitude_penginapan,
            latitude_tempat_wisata_1,
            longitude_tempat_wisata_1,
            latitude_tempat_wisata_2,
            longitude_tempat_wisata_2,
            latitude_rumah_makan,
            longitude_rumah_makan,
            kabupaten_p,
            kabupaten_tw1,
            kabupaten_tw2,
            kabupaten_rm

        RETURN id_penginapan,
            nama_penginapan,
            rating_penginapan,
            harga_penginapan,
            google_maps_link_penginapan,
            id_tempat_wisata_1,
            nama_tempat_wisata_1,
            kategori_tempat_wisata_1,
            rating_tempat_wisata_1,
            google_maps_link_tempat_wisata_1,
            id_tempat_wisata_2,
            nama_tempat_wisata_2,
            kategori_tempat_wisata_2,
            rating_tempat_wisata_2,
            google_maps_link_tempat_wisata_2,
            id_rumah_makan,
            nama_rumah_makan,
            rating_rumah_makan,
            google_maps_link_rumah_makan,
            jumlah_ulasan_penginapan,
            jumlah_ulasan_tempat_wisata_1,
            jumlah_ulasan_tempat_wisata_2,
            jumlah_ulasan_rumah_makan,
            jarak_penginapan_tempatwisata,
            jarak_tempatwisata_rumahmakan,
            jarak_penginapan_rumahmakan,
            total_jarak,
            total_score,
            kabupaten_p AS kabupaten_penginapan,
            kabupaten_tw1 AS kabupaten_tempat_wisata_1,
            kabupaten_tw2 AS kabupaten_tempat_wisata_2,
            kabupaten_rm AS kabupaten_rumah_makan,
            latitude_penginapan,
            longitude_penginapan,
            latitude_tempat_wisata_1,
            longitude_tempat_wisata_1,
            latitude_tempat_wisata_2,
            longitude_tempat_wisata_2,
            latitude_rumah_makan,
            longitude_rumah_makan
        ORDER BY total_score DESC
        LIMIT $limit
        """
        return query

    def _process_query_results(self, results, use_reviews=False):
        seen_package_ids = set()
        recommendations = []
        for i, record in enumerate(results):
            jumlah_ulasan_p = get_safe_value(record.get("jumlah_ulasan_penginapan"))
            if jumlah_ulasan_p == 0:
                rating_p = record["rating_penginapan"]
                jumlah_ulasan_p = estimate_review_count(rating_p, "penginapan")

            jumlah_ulasan_tw1 = get_safe_value(record.get("jumlah_ulasan_tempat_wisata_1"))
            if jumlah_ulasan_tw1 == 0:
                rating_tw1 = record["rating_tempat_wisata_1"]
                jumlah_ulasan_tw1 = estimate_review_count(rating_tw1, "tempat_wisata")

            jumlah_ulasan_tw2 = get_safe_value(record.get("jumlah_ulasan_tempat_wisata_2"))
            if jumlah_ulasan_tw2 == 0:
                rating_tw2 = record["rating_tempat_wisata_2"]
                jumlah_ulasan_tw2 = estimate_review_count(rating_tw2, "tempat_wisata")

            jumlah_ulasan_rm = get_safe_value(record.get("jumlah_ulasan_rumah_makan"))
            if jumlah_ulasan_rm == 0:
                rating_rm = record["rating_rumah_makan"]
                jumlah_ulasan_rm = estimate_review_count(rating_rm, "rumah_makan")

            pid = record["id_penginapan"]
            tw1id = record["id_tempat_wisata_1"]
            tw2id = record["id_tempat_wisata_2"]
            rmid = record["id_rumah_makan"]
            package_id = generate_package_id(pid, tw1id, tw2id, rmid)
            if package_id in seen_package_ids:
                continue
            seen_package_ids.add(package_id)

            google_maps_link_penginapan = record.get("google_maps_link_penginapan", "").strip()
            if not google_maps_link_penginapan:
                google_maps_link_penginapan = generate_google_maps_link(
                    record["latitude_penginapan"],
                    record["longitude_penginapan"],
                    record["nama_penginapan"]
                )

            google_maps_link_tempat_wisata_1 = record.get("google_maps_link_tempat_wisata_1", "").strip()
            if not google_maps_link_tempat_wisata_1:
                google_maps_link_tempat_wisata_1 = generate_google_maps_link(
                    record["latitude_tempat_wisata_1"],
                    record["longitude_tempat_wisata_1"],
                    record["nama_tempat_wisata_1"]
                )

            google_maps_link_tempat_wisata_2 = record.get("google_maps_link_tempat_wisata_2", "").strip()
            if not google_maps_link_tempat_wisata_2:
                google_maps_link_tempat_wisata_2 = generate_google_maps_link(
                    record["latitude_tempat_wisata_2"],
                    record["longitude_tempat_wisata_2"],
                    record["nama_tempat_wisata_2"]
                )

            google_maps_link_rumah_makan = record.get("google_maps_link_rumah_makan", "").strip()
            if not google_maps_link_rumah_makan:
                google_maps_link_rumah_makan = generate_google_maps_link(
                    record["latitude_rumah_makan"],
                    record["longitude_rumah_makan"],
                    record["nama_rumah_makan"]
                )

            recommendation = {
                "recommendationId": package_id,
                "penginapan": {
                    "id": record["id_penginapan"],
                    "nama": record["nama_penginapan"],
                    "rating": record["rating_penginapan"],
                    "harga": record["harga_penginapan"],
                    "jumlah_ulasan": jumlah_ulasan_p,
                    "latitude": record["latitude_penginapan"],
                    "longitude": record["longitude_penginapan"],
                    "google_maps_link": google_maps_link_penginapan,
                },
                "tempat_wisata_1": {
                    "id": record["id_tempat_wisata_1"],
                    "nama": record["nama_tempat_wisata_1"],
                    "kategori": record["kategori_tempat_wisata_1"],
                    "rating": record["rating_tempat_wisata_1"],
                    "jumlah_ulasan": jumlah_ulasan_tw1,
                    "latitude": record["latitude_tempat_wisata_1"],
                    "longitude": record["longitude_tempat_wisata_1"],
                    "google_maps_link": google_maps_link_tempat_wisata_1,
                },
                "tempat_wisata_2": {
                    "id": record["id_tempat_wisata_2"],
                    "nama": record["nama_tempat_wisata_2"],
                    "kategori": record["kategori_tempat_wisata_2"],
                    "rating": record["rating_tempat_wisata_2"],
                    "jumlah_ulasan": jumlah_ulasan_tw2,
                    "latitude": record["latitude_tempat_wisata_2"],
                    "longitude": record["longitude_tempat_wisata_2"],
                    "google_maps_link": google_maps_link_tempat_wisata_2,
                },
                "rumah_makan": {
                    "id": record["id_rumah_makan"],
                    "nama": record["nama_rumah_makan"],
                    "rating": record["rating_rumah_makan"],
                    "jumlah_ulasan": jumlah_ulasan_rm,
                    "latitude": record["latitude_rumah_makan"],
                    "longitude": record["longitude_rumah_makan"],
                    "google_maps_link": google_maps_link_rumah_makan,
                },
                "kabupaten_penginapan": record.get("kabupaten_penginapan"),
                "kabupaten_tempat_wisata_1": record.get("kabupaten_tempat_wisata_1"),
                "kabupaten_tempat_wisata_2": record.get("kabupaten_tempat_wisata_2"),
                "kabupaten_rumah_makan": record.get("kabupaten_rumah_makan"),
                "path_score": record.get("path_score", 0),
                "total_score": record.get("total_score", 0),
                "jarak_penginapan_tempatwisata": record.get("jarak_penginapan_tempatwisata", 0),
                "jarak_tempatwisata_rumahmakan": record.get("jarak_tempatwisata_rumahmakan", 0),
                "jarak_penginapan_rumahmakan": record.get("jarak_penginapan_rumahmakan", 0),
                "total_jarak": record.get("total_jarak", 0),
                "position_rank": i + 1,
                "package_id": package_id,
            }

            logger.info(
                f"Rekomendasi #{i+1}: Kabupaten={recommendation['kabupaten_penginapan']}, "
                f"Penginapan={recommendation['penginapan']['nama']}, "
                f"Total Score={recommendation['total_score']:.4f}, "
                f"Google Maps Link Penginapan={recommendation['penginapan']['google_maps_link']}"
            )

            recommendations.append(recommendation)

        for rec in recommendations:
            for key in ["harga", "rating"]:
                if key in rec["penginapan"]:
                    rec["penginapan"][key] = round(float(rec["penginapan"][key]), 2)

        return recommendations

    def _print_detailed_calculations(self, recommendations):
        print("\n" + "=" * 80)
        print(" " * 20 + "DETAIL KALKULASI PATH RANKING ALGORITHM")
        print("=" * 80)

        for i, rec in enumerate(recommendations, 1):
            p_name = rec["penginapan"]["nama"]
            tw1_name = rec["tempat_wisata_1"]["nama"]
            tw2_name = rec["tempat_wisata_2"]["nama"]
            rm_name = rec["rumah_makan"]["nama"]
            kabupaten = rec["kabupaten_penginapan"]

            path_score = rec.get("path_score", 0)
            path_str = f"Jalur #{i} (Kabupaten: {kabupaten}): {p_name} → {tw1_name} → {tw2_name} → {rm_name}"

            print(f"\n{path_str}")
            print("-" * 80)
            print(f"Path Score (berdasarkan jarak): {path_score:.6f}")
            print(f"Rating Penginapan: {rec['penginapan']['rating']}/5.0 (Bobot: {self.weights['rating_penginapan']:.2f})")
            print(f"Rating Tempat Wisata 1: {rec['tempat_wisata_1']['rating']}/5.0 (Bobot: {self.weights['rating_tempat_wisata_1']:.2f})")
            print(f"Rating Tempat Wisata 2: {rec['tempat_wisata_2']['rating']}/5.0 (Bobot: {self.weights['rating_tempat_wisata_2']:.2f})")
            print(f"Rating Rumah Makan: {rec['rumah_makan']['rating']}/5.0 (Bobot: {self.weights['rating_rumah_makan']:.2f})")
            print(f"Harga Penginapan: Rp{rec['penginapan']['harga']:,} (Bobot: {self.weights['harga_penginapan']:.2f})")

            p_rating_norm = rec["penginapan"]["rating"] / 5.0
            tw1_rating_norm = rec["tempat_wisata_1"]["rating"] / 5.0
            tw2_rating_norm = rec["tempat_wisata_2"]["rating"] / 5.0
            rm_rating_norm = rec["rumah_makan"]["rating"] / 5.0

            p_rating_contrib = p_rating_norm * self.weights["rating_penginapan"]
            tw1_rating_contrib = tw1_rating_norm * self.weights["rating_tempat_wisata_1"]
            tw2_rating_contrib = tw2_rating_norm * self.weights["rating_tempat_wisata_2"]
            rm_rating_contrib = rm_rating_norm * self.weights["rating_rumah_makan"]
            path_contrib = path_score * self.weights["path_score"]

            print("\nKontribusi komponen terhadap total score:")
            print(f"  - Path Score: {path_contrib:.4f}")
            print(f"  - Rating Penginapan: {p_rating_contrib:.4f}")
            print(f"  - Rating Tempat Wisata 1: {tw1_rating_contrib:.4f}")
            print(f"  - Rating Tempat Wisata 2: {tw2_rating_contrib:.4f}")
            print(f"  - Rating Rumah Makan: {rm_rating_contrib:.4f}")

            print(f"\nTotal Score: {rec.get('total_score', 0):.4f}")

            print("\nDetail Jarak:")
            jarak_penginapan_tw1 = rec.get("jarak_penginapan_tempatwisata", 0)
            jarak_tw1_rm = rec.get("jarak_tempatwisata_rumahmakan", 0)
            jarak_penginapan_rm = rec.get("jarak_penginapan_rumahmakan", 0)
            total_jarak = jarak_penginapan_tw1 + jarak_tw1_rm + jarak_penginapan_rm

            print(f"  - Penginapan ke Tempat Wisata 1: {jarak_penginapan_tw1:.2f} km")
            print(f"  - Tempat Wisata 1 ke Rumah Makan: {jarak_tw1_rm:.2f} km")
            print(f"  - Penginapan ke Rumah Makan: {jarak_penginapan_rm:.2f} km")
            print(f"  - Total Jarak: {total_jarak:.2f} km")

def get_recommendations(criteria):
    with PathRankingAlgorithm(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD) as pra:
        return pra.get_recommendations(criteria)