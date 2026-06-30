# Sistem Rekomendasi Paket Wisata Yogyakarta Berbasis Knowledge Graph dengan Path Ranking Algorithm

Repository ini merupakan implementasi **Tugas Akhir (Skripsi)** berjudul **"Sistem Rekomendasi Paket Wisata Berbasis Knowledge Graph dengan Path Ranking Algorithm"**, studi kasus wilayah **Daerah Istimewa Yogyakarta**.

Sistem ini memodelkan entitas pariwisata (tempat wisata, penginapan, dan rumah makan) beserta relasi geografis/jaraknya sebagai sebuah **knowledge graph** di Neo4j, kemudian menggunakan **Path Ranking Algorithm (PRA)** untuk menyusun dan meranking kombinasi paket wisata (tempat wisata + penginapan + rumah makan) yang paling relevan dengan preferensi pengguna.

## Latar Belakang & Tujuan

Pemilihan paket wisata (destinasi, penginapan, dan kuliner) yang saling berdekatan dan sesuai preferensi pengguna seringkali dilakukan secara manual dan memakan waktu. Penelitian ini mengusulkan pendekatan berbasis graph untuk merepresentasikan keterhubungan antar entitas pariwisata, lalu menerapkan Path Ranking Algorithm untuk menghitung skor relevansi jalur (path) antar entitas berdasarkan kombinasi faktor jarak, rating, harga, kategori, dan jumlah ulasan sehingga sistem dapat merekomendasikan paket wisata secara otomatis dan terukur.

## Metodologi Singkat

1. **Pembangunan Knowledge Graph** — Data tempat wisata, penginapan, dan rumah makan se-DIY (lima kabupaten/kota: Kota Yogyakarta, Sleman, Bantul, Kulon Progo, Gunungkidul) dimodelkan sebagai node dalam graph Neo4j, dengan relasi antar entitas berdasarkan jarak geografis (`ADA_AKSES_MENUJU`) dan lokasi administratif (`BERADA_DI`).
2. **Path Ranking Algorithm (PRA)** — Menghitung skor setiap kemungkinan jalur (path) yang menghubungkan satu tempat wisata, satu penginapan, dan satu rumah makan, berdasarkan kombinasi bobot: skor jarak antar lokasi, rating, harga, kategori wisata, dan jumlah ulasan masing-masing entitas.
3. **Penyusunan & Ranking Paket Wisata** — Hasil perhitungan skor PRA digunakan untuk mengurutkan kombinasi paket wisata terbaik sesuai kriteria/filter yang dipilih pengguna (kabupaten, kategori wisata, rentang rating, rentang harga penginapan).
4. **Evaluasi Sistem** — Sistem dilengkapi modul evaluasi berbasis feedback pengguna (like/dislike) untuk menghitung metrik **Precision, Recall, NDCG, dan Hit Rate** pada beberapa nilai *k* (top-3, top-5, top-7), guna mengukur kualitas rekomendasi yang dihasilkan.

## Skema Knowledge Graph

**Node (entitas):**
- `Kabupaten` — wilayah administratif (Kota Yogyakarta, Sleman, Bantul, Kulon Progo, Gunungkidul)
- `TempatWisata` — destinasi wisata, dengan atribut nama, kategori, rating, jumlah ulasan, koordinat
- `Penginapan` — akomodasi, dengan atribut nama, harga, rating, jumlah ulasan, koordinat
- `RumahMakan` — tempat makan, dengan atribut nama, rating, jumlah ulasan, koordinat

**Relasi (edge):**
- `(:TempatWisata)-[:BERADA_DI]->(:Kabupaten)`, `(:Penginapan)-[:BERADA_DI]->(:Kabupaten)`, `(:RumahMakan)-[:BERADA_DI]->(:Kabupaten)`
- `(:Entitas)-[:ADA_AKSES_MENUJU {jarak}]->(:Entitas)` — relasi dua arah antar entitas yang berjarak ≤ `MAX_DISTANCE_KM` (default 6 km), dengan properti `jarak` (km)

## Fitur Aplikasi

- Form pencarian rekomendasi dengan filter: kabupaten/kota, kategori wisata, rentang rating, dan rentang harga penginapan
- Mesin rekomendasi berbasis Path Ranking Algorithm yang mengembalikan daftar paket wisata terurut berdasarkan skor
- Visualisasi rute/lokasi paket wisata pada peta (integrasi koordinat & Google Maps)
- Sistem feedback pengguna (like/dislike) terhadap rekomendasi yang diberikan
- Autentikasi pengguna (login/register) serta panel admin
- Dashboard evaluasi sistem (precision, recall, NDCG, hit rate) dengan visualisasi grafik (Plotly) dan ekspor hasil evaluasi (CSV)
- Manajemen data (CRUD) oleh admin: pengguna, kriteria, rekomendasi, dan feedback
- Skrip ilustrasi/visualisasi knowledge graph (`ilustrasiKnowledgeGraph/`)

## Tech Stack

| Layer                  | Teknologi                                  |
|--------------------------|-----------------------------------------------|
| Bahasa                  | Python 3                                       |
| Web Framework           | Flask                                          |
| Knowledge Graph DB      | Neo4j (Cypher query, driver `neo4j`)           |
| Relational DB           | SQLite (via Flask-SQLAlchemy + Flask-Migrate)  |
| Algoritma Rekomendasi   | Path Ranking Algorithm (custom implementation) |
| Visualisasi Evaluasi    | Plotly                                          |
| Frontend                | HTML, CSS/SASS, JavaScript                      |

## Struktur Proyek

```
yogyakarta-tour-recommender/
├── backEnd/
│   ├── app.py                 # Aplikasi utama Flask (routes, API, autentikasi, admin)
│   ├── app_gui.py             # Antarmuka GUI tambahan (opsional)
│   ├── config.py              # Konfigurasi Neo4j, bobot PRA, kategori, kabupaten, dsb.
│   ├── database_setup.py      # Skrip pembangunan knowledge graph di Neo4j dari data CSV
│   ├── path_ranking.py        # Implementasi inti Path Ranking Algorithm
│   ├── path_rankingv1.py      # Versi awal/alternatif algoritma PRA
│   ├── evaluate_system.py     # Perhitungan metrik evaluasi (precision, recall, NDCG, hit rate)
│   ├── models.py              # Model database (User, UserCriteria, Recommendation, Feedback)
│   ├── map_setup.py           # Helper koordinat & integrasi peta
│   ├── utils.py                # Fungsi bantu (normalisasi skor, generate ID paket, dsb.)
│   ├── migrations/             # Migrasi database (Flask-Migrate)
│   └── test_evaluate.py        # Unit test modul evaluasi
├── data/
│   ├── tourist_attraction.csv  # Data tempat wisata
│   ├── place_to_stay.csv       # Data penginapan
│   ├── restaurant.csv          # Data rumah makan
│   └── kabupaten.csv           # Data wilayah kabupaten/kota
├── ilustrasiKnowledgeGraph/
│   └── knowledgeGraph.py       # Skrip ilustrasi/visualisasi struktur knowledge graph
├── frontEnd/                    # Template halaman (index, recommendation, destination, admin, dll.)
├── static/                      # Aset CSS/SASS, JS, gambar, library vendor
└── instance/                    # Database SQLite (users.db, dsb.)
```

## Instalasi & Menjalankan Secara Lokal

### Prasyarat

- Python 3.11 (sesuai compiled cache proyek)
- Neo4j (Desktop/Server) yang sudah berjalan, lengkap dengan plugin APOC bila diperlukan oleh query Cypher
- pip / virtualenv

### Langkah-langkah

1. Clone repository:
   ```bash
   git clone https://github.com/mateusapsitumorang/yogyakarta-tour-recommender.git
   cd yogyakarta-tour-recommender
   ```

2. Buat dan aktifkan virtual environment, lalu install dependensi:
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate

   pip install flask flask_sqlalchemy flask_migrate neo4j plotly werkzeug pytz
   ```
   > Proyek belum menyertakan `requirements.txt`; sesuaikan daftar paket di atas dengan import yang digunakan pada `backEnd/app.py`, `path_ranking.py`, dan `evaluate_system.py`.

3. Siapkan database Neo4j, lalu sesuaikan kredensial koneksi pada `backEnd/config.py`:
   ```python
   NEO4J_URI = "bolt://localhost:7687"
   NEO4J_USERNAME = "neo4j"
   NEO4J_PASSWORD = "<password_anda>"
   ```
   Sesuaikan juga `DATA_DIR` pada `config.py` agar mengarah ke folder `data/` pada environment Anda.

4. Bangun knowledge graph dari data CSV ke Neo4j:
   ```bash
   cd backEnd
   python database_setup.py
   ```

5. Jalankan migrasi database relasional (SQLite, untuk user/feedback):
   ```bash
   flask db upgrade
   ```

6. Jalankan aplikasi:
   ```bash
   python app.py
   ```
   Aplikasi akan berjalan di `http://localhost:5000` (default Flask).

## Konfigurasi Path Ranking Algorithm

Bobot kriteria PRA dapat disesuaikan pada `backEnd/config.py` melalui variabel `PRA_WEIGHTS`, mencakup: skor jalur (jarak), rating tempat wisata, rating penginapan, rating rumah makan, kategori wisata, harga penginapan, serta jumlah ulasan masing-masing entitas. Parameter lain seperti `MAX_DISTANCE_KM` (radius keterhubungan antar entitas) dan `NUM_RECOMMENDATIONS` (jumlah paket yang ditampilkan) juga dapat diatur pada file yang sama.

## Evaluasi Sistem

Modul `backEnd/evaluate_system.py` menghitung metrik evaluasi rekomendasi berdasarkan feedback pengguna (like/dislike) pada beberapa nilai *k* (top-3, top-5, top-7):

- **Precision** — proporsi rekomendasi relevan dari seluruh rekomendasi yang ditampilkan
- **Recall** — proporsi rekomendasi relevan yang berhasil ditampilkan dari seluruh item relevan
- **NDCG (Normalized Discounted Cumulative Gain)** — mengukur kualitas urutan/ranking rekomendasi
- **Hit Rate** — proporsi pengguna yang mendapatkan minimal satu rekomendasi relevan

Hasil evaluasi dapat dilihat melalui dashboard admin (`/api/generate_evaluation_chart`) dengan visualisasi grafik (Plotly) dan dapat diekspor ke CSV (`/export_all_evaluations`).

## Sumber Data

Data tempat wisata, penginapan, dan rumah makan se-DIY (`data/*.csv`) mencakup atribut nama, kabupaten, kategori, rating, jumlah ulasan, serta koordinat (latitude/longitude) dan tautan Google Maps masing-masing lokasi.

## Catatan Akademik

Repository ini disusun sebagai bagian dari penelitian Tugas Akhir (Skripsi). Beberapa nilai konfigurasi (mis. kredensial Neo4j, path direktori absolut pada `config.py`) merupakan pengaturan lokal milik penulis pada saat pengerjaan skripsi dan **perlu disesuaikan** sebelum dijalankan pada environment lain.

## Lisensi

Copyright © 2026 Mateus Appuwan Situmorang.

Repository ini disusun sebagai bagian dari Tugas Akhir (Skripsi) dan disediakan untuk keperluan pembelajaran, penelitian, serta portofolio.

Kode sumber pada repository ini dapat digunakan sebagai referensi akademik dengan tetap mencantumkan atribusi kepada penulis. Penggunaan, modifikasi, distribusi, atau publikasi ulang untuk tujuan komersial maupun nonakademik tanpa izin tertulis dari penulis tidak diperkenankan.

Apabila ingin menggunakan sebagian atau seluruh isi repository ini di luar konteks pembelajaran atau penelitian, silakan menghubungi penulis untuk memperoleh izin.
