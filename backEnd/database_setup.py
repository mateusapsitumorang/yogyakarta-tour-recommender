"""
Code untuk mempersiapkan dan membangun knowledge graph pada database Neo4j
"""

import os
import csv
import math
import time
import logging
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, MAX_DISTANCE_KM, DATA_DIR
from utils import haversine_distance, validate_record

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Kelas untuk mengelola koneksi ke database Neo4j
class Neo4jConnection:
    """
    Kelas untuk mengelola koneksi ke database Neo4j

    Attributes:
        driver: Koneksi ke database Neo4j
    """

    def __init__(self, uri, username, password):
        """
        Inisialisasi koneksi ke database Neo4j

        Args:
            uri: URI untuk koneksi Neo4j
            username: Username untuk koneksi Neo4j
            password: Password untuk koneksi Neo4j
        """
        self.driver = GraphDatabase.driver(uri, auth=(username, password))

    def __enter__(self):
        """Metode untuk mendukung penggunaan with-statement"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Tutup koneksi saat keluar from with-statement"""
        self.close()

    def close(self):
        """Menutup koneksi ke database"""
        self.driver.close()

    def run_query(self, query, parameters=None):
        """
        Menjalankan query Cypher pada database Neo4j

        Args:
            query: String query Cypher
            parameters: Dictionary parameter untuk query

        Returns:
            List hasil query
        """
        try:
            with self.driver.session() as session:
                result = session.run(query, parameters)
                return list(result)
        except Exception as e:
            logger.error(f"Error saat menjalankan query: {e}", exc_info=True)
            raise


# Fungsi untuk memproses batch data jarak untuk pembuatan relasi
def process_distance_batch(conn, distance_data, type1, type2):
    """
    Memproses batch data jarak dan membuat relasi ADA_AKSES_MENUJU dalam Neo4j.
    Implementasi dari Matriks Adjacency untuk Path Ranking Algorithm.

    Args:
        conn: Koneksi Neo4j
        distance_data: List tuple (id1, id2, distance) untuk relasi
        type1: Tipe node pertama
        type2: Tipe node kedua
    """
    if not distance_data:
        return

    # Buat string parameter untuk query batch
    params = {
        "batch": [
            {"id1": id1, "id2": id2, "distance": distance}
            for id1, id2, distance in distance_data
        ]
    }

    # Query untuk membuat relasi dua arah dalam satu operasi
    query = f"""
    UNWIND $batch AS item
    MATCH (a:{type1}), (b:{type2})
    WHERE a.id = item.id1 AND b.id = item.id2
    CREATE (a)-[:ADA_AKSES_MENUJU {{jarak: item.distance}}]->(b)
    CREATE (b)-[:ADA_AKSES_MENUJU {{jarak: item.distance}}]->(a)
    """

    try:
        conn.run_query(query, params)
        logger.debug(
            f"Memproses batch {len(distance_data)} relasi antara {type1} dan {type2}"
        )
    except Exception as e:
        logger.error(f"Error saat memproses batch relasi {type1}-{type2}: {e}")


# Mempersiapkan dan mengonfigurasi database Neo4j
def build_knowledge_graph():
    """
    Mempersiapkan database dan memuat data untuk knowledge graph
    Implementasi dasar untuk Path Ranking Algorithm
    """
    try:
        with Neo4jConnection(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD) as conn:
            logger.info("Menghubungkan ke database Neo4j...")

            # Menghapus data yang ada
            logger.info("Menghapus data yang ada...")
            conn.run_query("MATCH (n) DETACH DELETE n")

            # Membuat constraint/pembatas dan index untuk atribut yang sering dipakai
            logger.info("Membuat constraint dan index...")

            # Constraint untuk memastikan uniqueness
            constraints = [
                "CREATE CONSTRAINT IF NOT EXISTS FOR (k:Kabupaten) REQUIRE k.nama IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Penginapan) REQUIRE p.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (t:TempatWisata) REQUIRE t.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (r:RumahMakan) REQUIRE r.id IS UNIQUE",
            ]
            # Index yang akan dibuat untuk mengoptimalkan pencarian pada atribut tertentu
            indexes = [
                "CREATE INDEX IF NOT EXISTS FOR (p:Penginapan) ON (p.rating)",
                "CREATE INDEX IF NOT EXISTS FOR (p:Penginapan) ON (p.harga)",
                "CREATE INDEX IF NOT EXISTS FOR (t:TempatWisata) ON (t.kategori)",
                "CREATE INDEX IF NOT EXISTS FOR (t:TempatWisata) ON (t.rating)",
                "CREATE INDEX IF NOT EXISTS FOR (r:RumahMakan) ON (r.rating)",
                "CREATE INDEX IF NOT EXISTS FOR (p:Penginapan) ON (p.nama)",
                "CREATE INDEX IF NOT EXISTS FOR (t:TempatWisata) ON (t.nama)",
                "CREATE INDEX IF NOT EXISTS FOR (r:RumahMakan) ON (r.nama)",
                "CREATE INDEX IF NOT EXISTS FOR (p:Penginapan) ON (p.latitude, p.longitude)",
                "CREATE INDEX IF NOT EXISTS FOR (t:TempatWisata) ON (t.latitude, t.longitude)",
                "CREATE INDEX IF NOT EXISTS FOR (r:RumahMakan) ON (r.latitude, r.longitude)",
            ]

            # Eksekusi semua constraint dan index
            for query in constraints + indexes:
                try:
                    conn.run_query(query)
                except Exception as e:
                    logger.error(f"Error saat membuat constraint/index: {query} - {e}")

            # Memuat semua data
            load_kabupaten_data(conn)
            load_wisata_data(conn)
            load_penginapan_data(conn)
            load_rumah_makan_data(conn)

            # Menghitung jarak dan membuat relasi
            create_distance_relationships(conn)

            logger.info("\nKnowledge graph berhasil dibuat!")
    except Exception as e:
        logger.error(f"Error saat membangun knowledge graph: {e}", exc_info=True)
        raise


def load_kabupaten_data(conn):
    """
    Memuat data Kabupaten ke dalam database

    Args:
        conn: Koneksi Neo4j
    """
    logger.info("Memuat data Kabupaten...")
    kabupaten_file = os.path.join(DATA_DIR, "kabupaten.csv")
    kabupaten_data = []
    try:
        with open(kabupaten_file, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if validate_record(
                    row,
                    ["kabupaten", "latitude", "longitude"],
                    ["latitude", "longitude"],
                ):
                    kabupaten_data.append(row)
                else:
                    logger.warning(f"Melewati record kabupaten yang tidak valid: {row}")
    except Exception as e:
        logger.error(f"Error saat membaca file kabupaten: {e}")

    for kabupaten in kabupaten_data:
        query = """
        CREATE (k:Kabupaten {
            nama: $nama,
            name: $nama,
            latitude: $latitude,
            longitude: $longitude
        })
        """
        try:
            conn.run_query(
                query,
                {
                    "nama": kabupaten["kabupaten"],
                    "latitude": float(kabupaten["latitude"]),
                    "longitude": float(kabupaten["longitude"]),
                },
            )
        except Exception as e:
            logger.error(
                f"Error saat memasukkan data kabupaten: {kabupaten['kabupaten']} - {e}"
            )


def load_wisata_data(conn):
    """
    Memuat data Tempat Wisata ke dalam database

    Args:
        conn: Koneksi Neo4j
    """
    logger.info("Memuat data Tempat Wisata...")
    wisata_file = os.path.join(DATA_DIR, "tourist_attraction.csv")
    wisata_data = []
    try:
        with open(wisata_file, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                required_fields = [
                    "id_tempat_wisata",
                    "nama_tempat_wisata",
                    "rating",
                    "kategori",
                    "latitude",
                    "longitude",
                    "kabupaten",
                ]
                numeric_fields = ["rating", "latitude", "longitude", "jumlah_ulasan"]

                if validate_record(row, required_fields, numeric_fields):
                    wisata_data.append(row)
                else:
                    logger.warning(
                        f"Melewati record tempat wisata yang tidak valid: {row}"
                    )
    except Exception as e:
        logger.error(f"Error saat membaca file tempat wisata: {e}")

    for wisata in wisata_data:
        jumlah_ulasan = wisata.get("jumlah_ulasan", "0")
        if (
            jumlah_ulasan == ""
            or jumlah_ulasan.lower() == "none"
            or not jumlah_ulasan.isdigit()
        ):
            jumlah_ulasan = 0
        else:
            jumlah_ulasan = int(jumlah_ulasan)

        google_maps_link = wisata.get("google_maps_link", "").strip()  

        query = """
        MATCH (k:Kabupaten {nama: $kabupaten})
        CREATE (t:TempatWisata {
            id: $id,
            nama: $nama,
            name: $nama,
            rating: $rating,
            kategori: $kategori,
            latitude: $latitude,
            longitude: $longitude,
            jumlah_ulasan: $jumlah_ulasan,
            google_maps_link: $google_maps_link  
        })
        CREATE (t)-[:BERADA_DI]->(k)
        """
        try:
            conn.run_query(
                query,
                {
                    "id": wisata["id_tempat_wisata"],
                    "nama": wisata["nama_tempat_wisata"],
                    "rating": float(wisata["rating"]),
                    "kategori": wisata["kategori"],
                    "latitude": float(wisata["latitude"]),
                    "longitude": float(wisata["longitude"]),
                    "kabupaten": wisata["kabupaten"],
                    "jumlah_ulasan": jumlah_ulasan,
                    "google_maps_link": google_maps_link  
                },
            )
        except Exception as e:
            logger.error(
                f"Error saat memasukkan data tempat wisata: {wisata['nama_tempat_wisata']} - {e}"
            )

def load_penginapan_data(conn):
    """
    Memuat data Penginapan ke dalam database

    Args:
        conn: Koneksi Neo4j
    """
    logger.info("Memuat data Penginapan...")
    penginapan_file = os.path.join(DATA_DIR, "place_to_stay.csv")
    penginapan_data = []
    try:
        with open(penginapan_file, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                required_fields = [
                    "id_penginapan",
                    "nama_penginapan",
                    "rating",
                    "harga",
                    "latitude",
                    "longitude",
                    "kabupaten",
                ]
                numeric_fields = [
                    "rating",
                    "harga",
                    "latitude",
                    "longitude",
                    "jumlah_ulasan",
                ]

                if validate_record(row, required_fields, numeric_fields):
                    penginapan_data.append(row)
                else:
                    logger.warning(
                        f"Melewati record penginapan yang tidak valid: {row}"
                    )
    except Exception as e:
        logger.error(f"Error saat membaca file penginapan: {e}")

    for penginapan in penginapan_data:
        jumlah_ulasan = penginapan.get("jumlah_ulasan", "0")
        if (
            jumlah_ulasan == ""
            or jumlah_ulasan.lower() == "none"
            or not jumlah_ulasan.isdigit()
        ):
            jumlah_ulasan = 0
        else:
            jumlah_ulasan = int(jumlah_ulasan)

        google_maps_link = penginapan.get("google_maps_link", "").strip()  

        query = """
        MATCH (k:Kabupaten {nama: $kabupaten})
        CREATE (p:Penginapan {
            id: $id,
            nama: $nama,
            name: $nama,
            rating: $rating,
            harga: $harga,
            latitude: $latitude,
            longitude: $longitude,
            jumlah_ulasan: $jumlah_ulasan,
            google_maps_link: $google_maps_link  
        })
        CREATE (p)-[:BERADA_DI]->(k)
        """
        try:
            conn.run_query(
                query,
                {
                    "id": penginapan["id_penginapan"],
                    "nama": penginapan["nama_penginapan"],
                    "rating": float(penginapan["rating"]),
                    "harga": int(penginapan["harga"]),
                    "latitude": float(penginapan["latitude"]),
                    "longitude": float(penginapan["longitude"]),
                    "kabupaten": penginapan["kabupaten"],
                    "jumlah_ulasan": jumlah_ulasan,
                    "google_maps_link": google_maps_link  
                },
            )
        except Exception as e:
            logger.error(
                f"Error saat memasukkan data penginapan: {penginapan['nama_penginapan']} - {e}"
            )

def load_rumah_makan_data(conn):
    """
    Memuat data Rumah Makan ke dalam database

    Args:
        conn: Koneksi Neo4j
    """
    logger.info("Memuat data Rumah Makan...")
    rumah_makan_file = os.path.join(DATA_DIR, "restaurant.csv")
    rumah_makan_data = []
    try:
        with open(rumah_makan_file, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                required_fields = [
                    "id_rumah_makan",
                    "nama_rumah_makan",
                    "rating",
                    "latitude",
                    "longitude",
                    "kabupaten",
                ]
                numeric_fields = ["rating", "latitude", "longitude", "jumlah_ulasan"]

                if validate_record(row, required_fields, numeric_fields):
                    rumah_makan_data.append(row)
                else:
                    logger.warning(
                        f"Melewati record rumah makan yang tidak valid: {row}"
                    )
    except Exception as e:
        logger.error(f"Error saat membaca file rumah makan: {e}")

    for rumah_makan in rumah_makan_data:
        jumlah_ulasan = rumah_makan.get("jumlah_ulasan", "0")
        if (
            jumlah_ulasan == ""
            or jumlah_ulasan.lower() == "none"
            or not jumlah_ulasan.isdigit()
        ):
            jumlah_ulasan = 0
        else:
            jumlah_ulasan = int(jumlah_ulasan)

        google_maps_link = rumah_makan.get("google_maps_link", "").strip()  

        query = """
        MATCH (k:Kabupaten {nama: $kabupaten})
        CREATE (r:RumahMakan {
            id: $id,
            nama: $nama,
            name: $nama,
            rating: $rating,
            latitude: $latitude,
            longitude: $longitude,
            jumlah_ulasan: $jumlah_ulasan,
            google_maps_link: $google_maps_link  
        })
        CREATE (r)-[:BERADA_DI]->(k)
        """
        try:
            conn.run_query(
                query,
                {
                    "id": rumah_makan["id_rumah_makan"],
                    "nama": rumah_makan["nama_rumah_makan"],
                    "rating": float(rumah_makan["rating"]),
                    "latitude": float(rumah_makan["latitude"]),
                    "longitude": float(rumah_makan["longitude"]),
                    "kabupaten": rumah_makan["kabupaten"],
                    "jumlah_ulasan": jumlah_ulasan,
                    "google_maps_link": google_maps_link  
                },
            )
        except Exception as e:
            logger.error(
                f"Error saat memasukkan data rumah makan: {rumah_makan['nama_rumah_makan']} - {e}"
            )



def create_distance_relationships(conn):
    """
    Membuat relasi berdasarkan jarak antar node
    Implementasi dari Menghitung Jarak dan Membangun Matriks Adjacency untuk Path Ranking Algorithm

    Args:
        conn: Koneksi Neo4j
    """
    # Mendapatkan data dari database untuk menghitung jarak
    get_data_query = """
    MATCH (n) 
    WHERE n:Penginapan OR n:TempatWisata OR n:RumahMakan
    RETURN n.id AS id, labels(n)[0] AS type, n.latitude AS latitude, n.longitude AS longitude
    """

    try:
        nodes = conn.run_query(get_data_query)
        logger.info(f"Mendapatkan {len(nodes)} node untuk perhitungan jarak")

        # Memproses node ke dalam dictionary untuk pengaksesan yang lebih cepat
        node_dict = {}
        for node in nodes:
            node_dict[node["id"]] = {
                "type": node["type"],
                "latitude": node["latitude"],
                "longitude": node["longitude"],
            }

        # Membuat relasi berdasarkan jarak
        logger.info("Membuat relasi berdasarkan jarak...")

        # Pembuatan relasi dengan batch processing
        batch_size = 1000  # Ukuran batch
        type_combinations = [
            ("Penginapan", "TempatWisata"),
            ("Penginapan", "RumahMakan"),
            ("TempatWisata", "RumahMakan"),
        ]

        for type1, type2 in type_combinations:
            logger.info(f"Menghitung jarak antara {type1} dan {type2}...")
            distance_data = []

            # Filter node berdasarkan tipe
            type1_nodes = {
                id: data for id, data in node_dict.items() if data["type"] == type1
            }
            type2_nodes = {
                id: data for id, data in node_dict.items() if data["type"] == type2
            }

            # Hitung jarak antar node dan buat relasi jika dalam threshold
            for id1, data1 in type1_nodes.items():
                for id2, data2 in type2_nodes.items():
                    # Langkah 1: Menghitung Jarak - Haversine distance
                    distance = haversine_distance(
                        data1["latitude"],
                        data1["longitude"],
                        data2["latitude"],
                        data2["longitude"],
                    )

                    # Jika jarak dalam threshold, tambahkan ke data batch
                    if distance <= MAX_DISTANCE_KM:
                        distance_data.append((id1, id2, distance))

                        # Jika batch sudah penuh, proses dengan query batch
                        if len(distance_data) >= batch_size:
                            process_distance_batch(conn, distance_data, type1, type2)
                            distance_data = []  # Reset data batch

            # Proses sisa batch yang belum diproses
            if distance_data:
                process_distance_batch(conn, distance_data, type1, type2)

    except Exception as e:
        logger.error(f"Error saat membuat relasi jarak: {e}", exc_info=True)


if __name__ == "__main__":
    start_time = time.time()
    build_knowledge_graph()
    end_time = time.time()
    logger.info(f"Database setup completed in {end_time - start_time:.2f} seconds")
