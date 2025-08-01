"""
Code Konfigurasi untuk Sistem Rekomendasi Paket Wisata dengan Path Ranking Algorithm.
"""

# Konfigurasi Neo4j
NEO4J_URI = "bolt://localhost:7687"  # Alamat URI untuk koneksi ke database Neo4j, menentukan lokasi server database.
NEO4J_USERNAME = (
    "neo4j"  # Nama pengguna untuk autentikasi saat terhubung ke database Neo4j.
)
NEO4J_PASSWORD = (
    "puan061002"  # Kata sandi untuk autentikasi saat terhubung ke database Neo4j.
)

# Konfigurasi Path Ranking Algorithm (PRA)
# Pembobotan yang sama untuk semua rating dan jumlah ulasan
PRA_WEIGHTS = {
    "path_score": 0.200,  # Bobot untuk skor jalur berdasarkan jarak antar lokasi, memengaruhi prioritas jarak dalam rekomendasi.
    "rating_tempat_wisata_1": 0.075,  # Bobot untuk rating tempat wisata pertama, menentukan pengaruh rating dalam skor.
    "rating_tempat_wisata_2": 0.075,  # Bobot untuk rating tempat wisata kedua, memiliki pengaruh yang sama dengan tempat wisata pertama.
    "rating_penginapan": 0.075,  # Bobot untuk rating penginapan, memengaruhi skor berdasarkan kualitas penginapan.
    "rating_rumah_makan": 0.075,  # Bobot untuk rating rumah makan, memengaruhi skor berdasarkan kualitas rumah makan.
    "kategori_tempat_wisata_1": 0.050,  # Bobot untuk kategori tempat wisata pertama, menentukan relevansi kategori.
    "kategori_tempat_wisata_2": 0.050,  # Bobot untuk kategori tempat wisata kedua, memiliki pengaruh yang sama dengan kategori pertama.
    "harga_penginapan": 0.100,  # Bobot untuk harga penginapan, memengaruhi skor berdasarkan keterjangkauan harga.
    "jumlah_ulasan_penginapan": 0.075,  # Bobot untuk jumlah ulasan penginapan, mencerminkan popularitas penginapan.
    "jumlah_ulasan_tempat_wisata_1": 0.075,  # Bobot untuk jumlah ulasan tempat wisata pertama, mencerminkan popularitas.
    "jumlah_ulasan_tempat_wisata_2": 0.075,  # Bobot untuk jumlah ulasan tempat wisata kedua, memiliki pengaruh yang sama.
    "jumlah_ulasan_rumah_makan": 0.075,  # Bobot untuk jumlah ulasan rumah makan, mencerminkan popularitas rumah makan.
}

# Kategori Wisata yang dapat dipilih pengguna untuk memfilter rekomendasi.
KATEGORI_WISATA = [
    "Wisata Alam",  
    "Wisata Budaya dan Sejarah",  
    "Wisata Buatan",  
]

# Kabupaten/Kota yang digunakan untuk memfilter lokasi wisata.
KABUPATEN = [
    "Kota Yogyakarta",  
    "Sleman",  
    "Bantul",  
    "Kulon Progo",  
    "Gunungkidul",  
]

# Rentang Rating (1-5)
MIN_RATING = (0)
MAX_RATING = 5  

# Rentang Harga Penginapan (dalam ribuan rupiah) yang dapat dipilih pengguna untuk memfilter rekomendasi.
HARGA_PENGINAPAN = {
    "Rp50.000 - 100.000": (50000, 100000),  
    "Rp100.000 - 200.000": (100000, 200000,),  
    "Rp200.000 - 300.000": (200000, 300000),  
    "Rp300.000 - 400.000": (300000, 400000),  
    "Rp400.000 - 500.000": (400000, 500000),  
    "Rp500.000 - 600.000": (500000, 600000),  
    "Rp600.000 - 700.000": (600000, 700000,),  
    "Rp700.000 - 800.000": (700000, 800000),  
    "Rp800.000 - 900.000": (800000, 900000,),  
    "Rp900.000 - 1.000.000": (900000, 1000000,),  
    "Rp1.000.000 - 1.500.000": (1000000, 1500000,),  
}

# Jarak maksimum dalam kilometer untuk relasi DEKAT_DENGAN
MAX_DISTANCE_KM = 6  # Jarak maksimum antar lokasi (penginapan, wisata, rumah makan) yang dianggap terhubung dalam graph Neo4j.
# Digunakan untuk membatasi ukuran matriks adjacency dalam perhitungan jalur.

# Jumlah rekomendasi paket yang akan ditampilkan
NUM_RECOMMENDATIONS = 30  # Jumlah maksimum paket wisata yang akan dihasilkan oleh sistem untuk setiap permintaan rekomendasi.

# Konstanta untuk perhitungan skor
MAX_PRICE = (1500000) # Harga maksimum penginapan untuk normalisasi harga dalam perhitungan skor.
DISTANCE_FACTOR = 0.1  # Faktor pengali jarak untuk memengaruhi bobot jarak dalam skor akhir rekomendasi.
# Memastikan jarak antar lokasi (penginapan, tempat wisata, rumah makan) memengaruhi skor secara proporsional tanpa mendominasi faktor lain seperti rating atau harga.

# Path direktori data
DATA_DIR = "C:/Users/ASUS/Desktop/Skripsi/data" 
