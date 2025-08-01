"""
Modul utilitas untuk fungsi-fungsi umum yang digunakan di berbagai bagian
sistem rekomendasi paket wisata untuk mengurangi redundansi kode.
Modul ini menyediakan fungsi untuk normalisasi data, perhitungan jarak,
validasi record, dan pembuatan ID paket.
"""
import uuid
import time
import math
import logging
import random

# Inisialisasi logger untuk debugging
logger = logging.getLogger(__name__)

def get_safe_value(value, default=0):
    """
    Mengembalikan nilai default jika value adalah None atau 0.

    Fungsi ini memastikan bahwa nilai yang diberikan aman untuk digunakan dalam perhitungan,
    dengan mengganti None atau 0 dengan nilai default.

    Args:
        value: Nilai yang akan diperiksa.
        default: Nilai default yang dikembalikan jika value adalah None atau 0 (default: 0).

    Returns:
        Nilai yang aman (nilai asli atau default).
    """
    if value is None or value == 0:
        return default
    return value

def normalize_rating(rating, max_rating=5.0):
    """
    Menormalisasi rating ke skala 0-1.

    Fungsi ini mengkonversi rating mentah ke skala normalisasi untuk konsistensi
    dalam perhitungan skor rekomendasi.

    Args:
        rating: Nilai rating yang akan dinormalisasi.
        max_rating: Nilai maksimum rating (default: 5.0).

    Returns:
        float: Rating yang dinormalisasi (antara 0 dan 1).
    """
    safe_rating = get_safe_value(rating, 3.0)
    return safe_rating / max_rating

def estimate_review_count(rating, entity_type):
    """
    Memberikan estimasi jumlah ulasan berdasarkan rating.

    Fungsi ini menghasilkan estimasi jumlah ulasan untuk entitas tertentu dengan mempertimbangkan
    rating dan tipe entitas, ditambah faktor acak untuk variasi.

    Args:
        rating: Nilai rating entitas (penginapan, tempat wisata, atau rumah makan).
        entity_type: Tipe entitas ('penginapan', 'tempat_wisata', 'rumah_makan').

    Returns:
        int: Estimasi jumlah ulasan.
    """
    # Faktor pengali untuk masing-masing entitas
    multipliers = {
        "penginapan": 25,
        "tempat_wisata": 20,
        "rumah_makan": 30
    }
    
    # Gunakan pengali default jika tipe entitas tidak dikenali
    multiplier = multipliers.get(entity_type, 20)
    
    # Tambahkan faktor acak kecil untuk variasi (antara 0.8 dan 1.2)
    random_factor = max(0.8, min(1.2, (hash(str(rating)) % 40 + 80) / 100))
    
    return int(rating * multiplier * random_factor)

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Menghitung jarak garis besar (great circle distance) antara dua titik
    di bumi (dalam derajat desimal) menggunakan rumus Haversine.

    Implementasi Langkah 1 dari Path Ranking Algorithm untuk menghitung jarak antar lokasi.

    Args:
        lat1 (float): Latitude titik pertama (dalam derajat).
        lon1 (float): Longitude titik pertama (dalam derajat).
        lat2 (float): Latitude titik kedua (dalam derajat).
        lon2 (float): Longitude titik kedua (dalam derajat).

    Returns:
        float: Jarak dalam kilometer. Mengembalikan 999.0 jika terjadi error.
    """
    try:
        # Konversi ke radian
        lat1, lon1, lat2, lon2 = map(
            math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)]
        )
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        # Rumus Haversine
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        r = 6371  # Jari-jari bumi dalam kilometer
        return c * r
    except (ValueError, TypeError) as e:
        logger.error(f"Error saat menghitung jarak Haversine: {e}")
        return 999.0  # Nilai fallback untuk menangani error

def validate_record(record, required_fields, numeric_fields=None):
    """
    Memvalidasi record data, memastikan field yang diperlukan ada
    dan field numerik dapat dikonversi ke tipe data yang tepat.

    Fungsi ini digunakan untuk memastikan integritas data sebelum diproses lebih lanjut.

    Args:
        record (dict): Dictionary data record yang akan divalidasi.
        required_fields (list): Daftar field yang wajib ada.
        numeric_fields (list, optional): Daftar field yang harus berupa numerik.

    Returns:
        bool: True jika record valid, False jika tidak.
    """
    # Validasi field yang diperlukan
    for field in required_fields:
        if field not in record or record[field] == "" or record[field].lower() == "none":
            return False
    
    # Validasi field numerik
    if numeric_fields:
        for field in numeric_fields:
            if field in record and record[field] and record[field].lower() != "none":
                try:
                    if field in ["latitude", "longitude", "rating"]:
                        float(record[field]) # Pastikan dapat dikonversi ke float
                    elif field in ["harga", "jumlah_ulasan"]:
                        int(record[field]) # Pastikan dapat dikonversi ke int
                except (ValueError, TypeError):
                    return False
    
    return True

def calculate_path_score(rec):
    """
    Menghitung skor untuk jalur berdasarkan formula Path Ranking Algorithm.

    Fungsi ini menghitung skor total berdasarkan rating, jarak, dan harga,
    dengan bobot tertentu untuk setiap komponen dan faktor acak untuk variasi.

    Args:
        rec (dict): Record rekomendasi dengan data komponen dan jarak.

    Returns:
        float: Skor numerik untuk jalur.
    """
    # Ambil nilai rating dengan pengecekan terhadap None
    p_rating = get_safe_value(rec["penginapan"]["rating"], 3.0)
    tw1_rating = get_safe_value(rec["tempat_wisata_1"]["rating"], 3.0)
    tw2_rating = get_safe_value(rec["tempat_wisata_2"]["rating"], 3.0)
    rm_rating = get_safe_value(rec["rumah_makan"]["rating"], 3.0)
    
    # Normalisasi rating ke skala 0-1
    p_rating_norm = normalize_rating(p_rating)
    tw1_rating_norm = normalize_rating(tw1_rating)
    tw2_rating_norm = normalize_rating(tw2_rating)
    rm_rating_norm = normalize_rating(rm_rating)
    
    # Ambil nilai jarak dengan pengecekan terhadap None
    jarak_penginapan_tempatwisata = get_safe_value(rec.get("jarak_penginapan_tempatwisata"), 0.1)
    jarak_tempatwisata_rumahmakan = get_safe_value(rec.get("jarak_tempatwisata_rumahmakan"), 0.1)  
    jarak_penginapan_rumahmakan = get_safe_value(rec.get("jarak_penginapan_rumahmakan"), 0.1)
    # Hitung total jarak
    total_jarak = jarak_penginapan_tempatwisata + jarak_tempatwisata_rumahmakan + jarak_penginapan_rumahmakan
    
    # Path Score: Normalisasi jarak (lebih kecil lebih baik)
    jarak_score = 1.0 / (1.0 + 0.1 * total_jarak)
    
    # Skor harga - lebih rendah lebih baik dalam rentang yang dipilih
    harga = get_safe_value(rec["penginapan"]["harga"], 500000)
    min_harga = rec.get("min_harga_penginapan", 0)
    max_harga = rec.get("max_harga_penginapan", 1500000)

    # Jika harga dalam rentang yang dipilih
    if min_harga <= harga <= max_harga:
        # Normalisasi dalam rentang (harga lebih rendah dalam rentang mendapat skor lebih tinggi)
        harga_norm = (max_harga - harga) / (max_harga - min_harga) if max_harga > min_harga else 0.5
    else:
        # Harga di luar rentang (seharusnya tidak terjadi dengan filter SQL)
        harga_norm = 0.5  # Nilai netral jika di luar rentang
    
    # Faktor acak untuk variasi hasil
    random_factor = random.uniform(0, 0.1)
    
    # Total Score: Implementasi pembobotan tanpa keberagaman
    total_score = (
        p_rating_norm * 0.20 + 
        tw1_rating_norm * 0.08 + 
        tw2_rating_norm * 0.08 + 
        rm_rating_norm * 0.10 + 
        jarak_score * 0.40 +
        harga_norm * 0.18 + 
        random_factor
    )
    
    return total_score

def convert_scientific(val):
    """
    Mengkonversi notasi ilmiah ke format desimal dengan dua angka di belakang koma.

    Fungsi ini digunakan untuk memastikan nilai numerik ditampilkan dengan format yang mudah dibaca.

    Args:
        val: Nilai yang akan dikonversi (bisa berupa string atau numerik).

    Returns:
        Nilai dalam format desimal (string) atau nilai asli jika bukan notasi ilmiah.
    """
    if isinstance(val, str) and 'e' in val.lower():
        try:
            return format(float(val), '.2f')
        except:
            return val
    return val

def generate_package_id(penginapan_id=None, wisata1_id=None, wisata2_id=None, rumah_makan_id=None):
    """
    Menghasilkan ID unik untuk paket rekomendasi berdasarkan ID entitas.

    Jika ID entitas tidak lengkap, fungsi ini menghasilkan ID berbasis UUID.

    Args:
        penginapan_id: ID penginapan (opsional).
        wisata1_id: ID tempat wisata pertama (opsional).
        wisata2_id: ID tempat wisata kedua (opsional).
        rumah_makan_id: ID rumah makan (opsional).

    Returns:
        str: ID paket unik dalam format string.
    """
    # Jika tidak ada ID spesifik, gunakan UUID
    if not all([penginapan_id, wisata1_id, wisata2_id, rumah_makan_id]):
        return f"PKG-{uuid.uuid4().hex[:4].upper()}"
    
    # Gunakan ID entitas untuk membuat package_id
    return f"PKG-{penginapan_id}-{wisata1_id}-{wisata2_id}-{rumah_makan_id}"

