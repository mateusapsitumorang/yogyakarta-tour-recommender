"""
Code untuk menjalankan Sistem Rekomendasi Paket Wisata pada terminal
yang telah disempurnakan untuk hasil yang lebih relevan dan beragam
dengan implementasi murni Path Ranking Algorithm dengan pemastian keberagaman penginapan.
"""
import os
import random
import csv
import argparse
import logging
from tabulate import tabulate
from config import KABUPATEN, KATEGORI_WISATA, HARGA_PENGINAPAN
from path_ranking import PathRankingAlgorithm
from config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
from utils import get_safe_value, normalize_rating, calculate_path_score

# Konfigurasi logging untuk debugging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Mendapatkan data user dari inputan user
def get_user_input():
    """Mendapatkan input kriteria dari pengguna melalui command line"""
    print("\n" + "=" * 50)
    print("SISTEM REKOMENDASI PAKET WISATA YOGYAKARTA")
    print("=" * 50)

    # Pilih Kabupaten
    print("\nKabupaten yang tersedia:")
    for i, kab in enumerate(KABUPATEN, 1):
        print(f"{i}. {kab}")

    kabupaten_choice = input("\nPilih Kabupaten (1-5, kosongkan untuk semua): ")
    kabupaten = None
    if kabupaten_choice.strip():
        kabupaten_idx = int(kabupaten_choice) - 1
        if 0 <= kabupaten_idx < len(KABUPATEN):
            kabupaten = KABUPATEN[kabupaten_idx]

    # Pilih Kategori Wisata
    print("\nKategori Wisata yang tersedia:")
    for i, kat in enumerate(KATEGORI_WISATA, 1):
        print(f"{i}. {kat}")

    kategori_choice = input("\nPilih Kategori Wisata (1-3, kosongkan untuk semua): ")
    kategori_wisata = None
    if kategori_choice.strip():
        kategori_idx = int(kategori_choice) - 1
        if 0 <= kategori_idx < len(KATEGORI_WISATA):
            kategori_wisata = KATEGORI_WISATA[kategori_idx]

    # Pilih minimum rating tempat wisata
    min_rating_tempat_wisata = input(
        "\nMinimum Rating Tempat Wisata (1-5, default: 3): "
    )
    min_rating_tempat_wisata = (
        float(min_rating_tempat_wisata) if min_rating_tempat_wisata.strip() else 3.0
    )

    # Menampilkan pilihan rentang harga penginapan
    print("\nRentang Harga Penginapan (dalam ribuan rupiah dan juta):")
    for i, (kategori, rentang) in enumerate(HARGA_PENGINAPAN.items(), 1):
        if rentang[1] >= 1000000:
            print(f"{i}. {kategori}: {rentang[0]/1000} ribu - {rentang[1]/1000000} juta")
        else:
            print(f"{i}. {kategori}: {rentang[0]/1000} ribu - {rentang[1]/1000} ribu")

    # Memilih rentang harga penginapan
    harga_choice = input(
        "\nPilih Rentang Harga (1-11, default: 11/1 juta - 1.5 juta): "
    )
    min_harga_penginapan = 0
    max_harga_penginapan = 1500000  # Default: 1 juta - 1.5 juta

    if harga_choice.strip():
        harga_idx = int(harga_choice) - 1
        if 0 <= harga_idx < len(HARGA_PENGINAPAN):
            rentang_key = list(HARGA_PENGINAPAN.keys())[harga_idx]
            min_harga_penginapan = HARGA_PENGINAPAN[rentang_key][0]
            max_harga_penginapan = HARGA_PENGINAPAN[rentang_key][1]

    # Menampilkan harga yang dipilih dengan format yang sesuai
    if max_harga_penginapan >= 1000000:
        print(
            f"\nRentang harga penginapan yang dipilih: {min_harga_penginapan/1000} ribu - {max_harga_penginapan / 1000000} juta rupiah"
        )
    else:
        print(f"\nRentang harga penginapan yang dipilih: {min_harga_penginapan/1000} - {max_harga_penginapan/1000} ribu rupiah")

    # Pilih minimum rating penginapan
    min_rating_penginapan = input("\nMinimum Rating Penginapan (1-5, default: 3): ")
    min_rating_penginapan = (
        float(min_rating_penginapan) if min_rating_penginapan.strip() else 3.0
    )

    # Pilih minimum rating rumah makan
    min_rating_rumah_makan = input("\nMinimum Rating Rumah Makan (1-5, default: 3): ")
    min_rating_rumah_makan = (
        float(min_rating_rumah_makan) if min_rating_rumah_makan.strip() else 3.0
    )

    # Pilih berdasarkan rating saja atau rating + jumlah ulasan
    print("\nPilih apakah ingin menggunakan rating saja atau rating + jumlah ulasan:")
    print("1. Berdasarkan Rating Saja")
    print("2. Berdasarkan Rating dan Jumlah Ulasan")
    pilihan = input("Masukkan pilihan Anda (1 atau 2): ")

    # Tentukan apakah menggunakan jumlah ulasan atau tidak
    use_reviews = True if pilihan == "2" else False
    
    # Pilih jumlah rekomendasi yang diinginkan
    num_recommendations = input("\nJumlah rekomendasi yang ingin ditampilkan (1-5, default: 3): ")
    num_recommendations = int(num_recommendations) if num_recommendations.strip() and 1 <= int(num_recommendations) <= 20 else 3

    criteria = {
        "kabupaten": kabupaten,
        "kategori_wisata": kategori_wisata,
        "min_rating_tempat_wisata": min_rating_tempat_wisata,
        "min_harga_penginapan": min_harga_penginapan,
        "max_harga_penginapan": max_harga_penginapan,
        "min_rating_penginapan": min_rating_penginapan,
        "min_rating_rumah_makan": min_rating_rumah_makan,
        "use_reviews": use_reviews,
        "num_recommendations": num_recommendations,
    }
    
    return criteria

# Tampilan hasil rekomendasi dengan format yang diperbaiki
def display_recommendations(recommendations, criteria):
    """Menampilkan rekomendasi paket wisata dalam bentuk tabel"""
    if not recommendations:
        print("\nTidak ada rekomendasi yang sesuai dengan kriteria yang dipilih.")
        print("\nSaran: Coba longgarkan kriteria pencarian, misalnya:")
        print("- Menurunkan minimum rating")
        print("- Memperluas rentang harga")
        print("- Tidak memilih kabupaten atau kategori wisata spesifik")
        return
    
    # Cek apakah pengguna memilih untuk menampilkan jumlah ulasan
    show_reviews = criteria.get("use_reviews", False)

    print("\n" + "=" * 80)
    print(" " * 25 + "REKOMENDASI PAKET WISATA")
    print("=" * 80)

    # Batasi jumlah rekomendasi yang ditampilkan sesuai permintaan pengguna
    num_to_display = min(criteria.get("num_recommendations", 3), len(recommendations))
    recommendations_to_display = recommendations[:num_to_display]

    # PERBAIKAN: Validasi rekomendasi sebelum ditampilkan
    valid_recommendations = []
    for rec in recommendations_to_display:
        # Pastikan semua komponen utama ada dan valid
        if (not is_valid_entity(rec.get("penginapan")) or
            not is_valid_entity(rec.get("tempat_wisata_1")) or
            not is_valid_entity(rec.get("tempat_wisata_2")) or
            not is_valid_entity(rec.get("rumah_makan"))):
            logger.warning(f"Melewati rekomendasi tidak valid: {rec.get('penginapan', {}).get('nama', 'Unknown')}")
            continue
        valid_recommendations.append(rec)
    
    if not valid_recommendations:
        print("\nTidak ada rekomendasi valid yang tersedia.")
        return
    
    for i, rec in enumerate(valid_recommendations, 1):
        # Kalkulasi skor jika total_score adalah 0 atau None
        total_score = rec.get('total_score', 0)
        if total_score is None or total_score == 0:
            total_score = calculate_path_score(rec)
            rec["total_score"] = total_score
            
        print(f"\nRekomendasi #{i} (Skor: {total_score:.4f})")
        print("-" * 80)

        # Penginapan
        penginapan = rec["penginapan"]
        print(f"PENGINAPAN: {penginapan['nama']}")
        print(f"Rating: {penginapan['rating']}/5.0")
        
        # Menampilkan jumlah ulasan penginapan hanya jika use_reviews=True
        if show_reviews:
            print(f"Jumlah Ulasan: {penginapan.get('jumlah_ulasan', 0)}")
            
        # Format harga dengan pemisah ribuan
        print(f"Harga: Rp{penginapan['harga']:,}")

        # Tempat Wisata 1
        tw1 = rec["tempat_wisata_1"]
        print(f"\nTEMPAT WISATA 1: {tw1['nama']}")
        print(f"Kategori: {tw1['kategori']}")
        print(f"Rating: {tw1['rating']}/5.0")
        
        # Menampilkan jumlah ulasan tempat wisata 1 hanya jika use_reviews=True
        if show_reviews:
            print(f"Jumlah Ulasan: {tw1.get('jumlah_ulasan', 0)}")

        # Tempat Wisata 2
        tw2 = rec["tempat_wisata_2"]
        print(f"\nTEMPAT WISATA 2: {tw2['nama']}")
        print(f"Kategori: {tw2['kategori']}")
        print(f"Rating: {tw2['rating']}/5.0")
        
        # Menampilkan jumlah ulasan tempat wisata 2 hanya jika use_reviews=True
        if show_reviews:
            print(f"Jumlah Ulasan: {tw2.get('jumlah_ulasan', 0)}")

        # Rumah Makan
        rm = rec["rumah_makan"]
        print(f"\nRUMAH MAKAN: {rm['nama']}")
        print(f"Rating: {rm['rating']}/5.0")
        
        # Menampilkan jumlah ulasan rumah makan hanya jika use_reviews=True
        if show_reviews:
            print(f"Jumlah Ulasan: {rm.get('jumlah_ulasan', 0)}")

        # Jarak antara tempat-tempat - menggunakan fungsi utilitas untuk menghindari redundansi
        jarak_penginapan_tempatwisata = get_safe_value(rec.get("jarak_penginapan_tempatwisata"), 0)
        jarak_tempatwisata_rumahmakan = get_safe_value(rec.get("jarak_tempatwisata_rumahmakan"), 0)
        jarak_penginapan_rumahmakan = get_safe_value(rec.get("jarak_penginapan_rumahmakan"), 0)

        # Menampilkan nama tempat beserta jarak
        print(f"\nJarak Penginapan {rec['penginapan']['nama']} ke Tempat Wisata 1 ({rec['tempat_wisata_1']['nama']}): {jarak_penginapan_tempatwisata:.2f} km")
        print(f"Jarak Tempat Wisata 1 ({rec['tempat_wisata_1']['nama']}) ke Rumah Makan ({rec['rumah_makan']['nama']}): {jarak_tempatwisata_rumahmakan:.2f} km")
        print(f"Jarak Penginapan {rec['penginapan']['nama']} ke Rumah Makan ({rec['rumah_makan']['nama']}): {jarak_penginapan_rumahmakan:.2f} km")

        # Total Jarak - mengambil langsung dari objek rekomendasi atau menghitung jika tidak ada
        total_jarak = rec.get("total_jarak")
        if total_jarak is None:
            total_jarak = jarak_penginapan_tempatwisata + jarak_tempatwisata_rumahmakan + jarak_penginapan_rumahmakan
            
        print(f"\nTotal Jarak yang akan Ditempuh: {total_jarak:.2f} km")
        
        # Tambahkan informasi kabupaten
        print("\nInformasi Kabupaten:")
        print(f"- Penginapan: {rec.get('kabupaten_penginapan', 'Tidak diketahui')}")
        print(f"- Tempat Wisata 1: {rec.get('kabupaten_tempat_wisata_1', 'Tidak diketahui')}")
        print(f"- Tempat Wisata 2: {rec.get('kabupaten_tempat_wisata_2', 'Tidak diketahui')}")
        print(f"- Rumah Makan: {rec.get('kabupaten_rumah_makan', 'Tidak diketahui')}")
                
        print("-" * 80)

# PERBAIKAN: Tambahkan fungsi validasi entitas
def is_valid_entity(entity):
    """
    Memeriksa apakah entitas memiliki semua properti yang diperlukan
    
    Args:
        entity: Dictionary yang berisi data entitas
        
    Returns:
        Boolean yang menunjukkan apakah entitas valid
    """
    if not entity or not isinstance(entity, dict):
        return False
    
    # Properti minimum yang harus dimiliki oleh semua entitas
    required_props = ["nama", "rating"]
    
    # Tambahan untuk tempat wisata
    if "kategori" in entity and not entity.get("kategori"):
        return False
    
    # Cek semua properti yang diperlukan
    for prop in required_props:
        if prop not in entity or entity[prop] is None:
            return False
    
    return True

# Mengexport hasil rekomendasi ke csv dengan format yang diperbaiki
def export_recommendations(recommendations, filename="rekomendasi_paket_wisata.csv", criteria=None):
    """Ekspor rekomendasi paket wisata ke format CSV"""
    if not recommendations:
        print("Tidak ada rekomendasi untuk diekspor.")
        return
    
    # PERBAIKAN: Validasi rekomendasi sebelum diekspor
    valid_recommendations = []
    for rec in recommendations:
        # Pastikan semua komponen utama ada dan valid
        if (not is_valid_entity(rec.get("penginapan")) or
            not is_valid_entity(rec.get("tempat_wisata_1")) or
            not is_valid_entity(rec.get("tempat_wisata_2")) or
            not is_valid_entity(rec.get("rumah_makan"))):
            logger.warning(f"Melewati rekomendasi tidak valid untuk ekspor: {rec.get('penginapan', {}).get('nama', 'Unknown')}")
            continue
        valid_recommendations.append(rec)
    
    if not valid_recommendations:
        print("Tidak ada rekomendasi valid untuk diekspor.")
        return
    
    # Cek apakah pengguna memilih untuk menyertakan jumlah ulasan
    show_reviews = criteria.get("use_reviews", False) if criteria else False
    
    # Tentukan fieldnames berdasarkan pilihan pengguna
    if show_reviews:
        fieldnames = [
            "no",
            "skor",
            "nama_penginapan",
            "rating_penginapan",
            "jumlah_ulasan_penginapan",
            "harga_penginapan",
            "nama_tempat_wisata_1",
            "kategori_tempat_wisata_1",
            "rating_tempat_wisata_1",
            "jumlah_ulasan_tempat_wisata_1",
            "nama_tempat_wisata_2",
            "kategori_tempat_wisata_2",
            "rating_tempat_wisata_2",
            "jumlah_ulasan_tempat_wisata_2",
            "nama_rumah_makan",
            "rating_rumah_makan",
            "jumlah_ulasan_rumah_makan",
            "jarak_penginapan_tempatwisata",
            "jarak_tempatwisata_rumahmakan", 
            "jarak_penginapan_rumahmakan",
            "total_jarak",
            "kabupaten_penginapan",
            "kabupaten_tempat_wisata_1",
            "kabupaten_tempat_wisata_2",
            "kabupaten_rumah_makan"
        ]
    else:
        fieldnames = [
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
            "kabupaten_penginapan",
            "kabupaten_tempat_wisata_1",
            "kabupaten_tempat_wisata_2",
            "kabupaten_rumah_makan"
        ]

    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for i, rec in enumerate(valid_recommendations, 1):
            # Menggunakan fungsi utilitas untuk menghindari redundansi
            jarak_penginapan_tempatwisata = get_safe_value(rec.get("jarak_penginapan_tempatwisata"), 0)
            jarak_tempatwisata_rumahmakan = get_safe_value(rec.get("jarak_tempatwisata_rumahmakan"), 0)
            jarak_penginapan_rumahmakan = get_safe_value(rec.get("jarak_penginapan_rumahmakan"), 0)
            
            total_jarak = get_safe_value(rec.get("total_jarak"), 
                                       jarak_penginapan_tempatwisata + jarak_tempatwisata_rumahmakan + jarak_penginapan_rumahmakan)
            
            # Menggunakan skor yang sudah dihitung
            total_score = get_safe_value(rec.get('total_score'), 0)
                
            # Membuat dictionary dasar yang selalu ada
            row_data = {
                "no": i,
                "skor": round(total_score, 4),
                "nama_penginapan": rec["penginapan"]["nama"],
                "rating_penginapan": rec["penginapan"]["rating"],
                "harga_penginapan": rec["penginapan"]["harga"],
                "nama_tempat_wisata_1": rec["tempat_wisata_1"]["nama"],
                "kategori_tempat_wisata_1": rec["tempat_wisata_1"]["kategori"],
                "rating_tempat_wisata_1": rec["tempat_wisata_1"]["rating"],
                "nama_tempat_wisata_2": rec["tempat_wisata_2"]["nama"],
                "kategori_tempat_wisata_2": rec["tempat_wisata_2"]["kategori"],
                "rating_tempat_wisata_2": rec["tempat_wisata_2"]["rating"],
                "nama_rumah_makan": rec["rumah_makan"]["nama"],
                "rating_rumah_makan": rec["rumah_makan"]["rating"],
                "jarak_penginapan_tempatwisata": round(jarak_penginapan_tempatwisata, 2),
                "jarak_tempatwisata_rumahmakan": round(jarak_tempatwisata_rumahmakan, 2),
                "jarak_penginapan_rumahmakan": round(jarak_penginapan_rumahmakan, 2),
                "total_jarak": round(total_jarak, 2),
                "kabupaten_penginapan": rec.get("kabupaten_penginapan", ""),
                "kabupaten_tempat_wisata_1": rec.get("kabupaten_tempat_wisata_1", ""),
                "kabupaten_tempat_wisata_2": rec.get("kabupaten_tempat_wisata_2", ""),
                "kabupaten_rumah_makan": rec.get("kabupaten_rumah_makan", "")
            }
            
            # Tambahkan kolom jumlah ulasan jika diperlukan
            if show_reviews:
                row_data.update({
                    "jumlah_ulasan_penginapan": rec["penginapan"].get("jumlah_ulasan", 0),
                    "jumlah_ulasan_tempat_wisata_1": rec["tempat_wisata_1"].get("jumlah_ulasan", 0),
                    "jumlah_ulasan_tempat_wisata_2": rec["tempat_wisata_2"].get("jumlah_ulasan", 0),
                    "jumlah_ulasan_rumah_makan": rec["rumah_makan"].get("jumlah_ulasan", 0)
                })
            
            writer.writerow(row_data)

    print(f"\nRekomendasi telah diekspor ke file: {filename}")

# Fungsi utama yang menjalankan sistem rekomendasi paket wisata
def main():
    parser = argparse.ArgumentParser(
        description="Sistem Rekomendasi Paket Wisata Yogyakarta"
    )
    parser.add_argument(
        "--export", action="store_true", help="Ekspor hasil rekomendasi ke CSV"
    )
    parser.add_argument(
        "--output", default="rekomendasi_paket_wisata.csv", help="Nama file output CSV"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Mengaktifkan mode debug untuk logging"
    )
    parser.add_argument(
        "--detail", action="store_true", help="Menampilkan detail kalkulasi Path Ranking Algorithm"
    )
    args = parser.parse_args()
    
    # Atur level logging berdasarkan argumen debug
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Dapatkan input dari pengguna
    criteria = get_user_input()  # Mendapatkan input kriteria dari pengguna
    
    # Tambahkan flag debug mode jika diperlukan
    if args.detail:
        criteria["debug_mode"] = False

    print("\nMencari rekomendasi paket wisata...")

    # Membuat instance dari PathRankingAlgorithm dan menggunakan with-statement untuk penanganan resource
    try:
        with PathRankingAlgorithm(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD) as pra:
            # Memastikan kita memanggil get_recommendations dengan parameter yang benar
            recommendations = pra.get_recommendations(criteria)
            
            # Jika tidak ada rekomendasi yang ditemukan
            if not recommendations:
                print("\nTidak ada rekomendasi yang sesuai dengan kriteria yang dipilih.")
                print("\nSaran: Coba longgarkan kriteria pencarian, misalnya:")
                print("- Menurunkan minimum rating")
                print("- Memperluas rentang harga")
                print("- Tidak memilih kabupaten atau kategori wisata spesifik")
                return
            
            # Tampilkan rekomendasi - teruskan juga criteria
            display_recommendations(recommendations, criteria)

            # Ekspor ke CSV jika diminta - teruskan juga criteria
            if args.export:
                export_recommendations(recommendations, args.output, criteria)
            else:
                export_choice = input(
                    "\nApakah Anda ingin mengekspor hasil rekomendasi ke CSV? (y/n): "
                )
                if export_choice.lower() == "y":
                    export_recommendations(recommendations, args.output, criteria)
    except Exception as e:
        logger.error(f"Error saat mencari atau menampilkan rekomendasi: {e}", exc_info=True)


if __name__ == "__main__":
    main()