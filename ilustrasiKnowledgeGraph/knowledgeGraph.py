from neo4j import GraphDatabase
import csv
import os
import math

class Neo4jConnector:
    def __init__(self, uri, username, password, database=None):
        """
        Inisialisasi koneksi ke Neo4j
        :param uri: URI server Neo4j (contoh: 'bolt://localhost:7687')
        :param username: Username untuk koneksi
        :param password: Password untuk koneksi
        :param database: Nama database yang ingin digunakan (default: None, akan menggunakan default database)
        """
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self.database = database
        
        # Tes koneksi
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("RETURN 1 AS test")
                print(f"Koneksi ke Neo4j berhasil! Database: {self.database or 'default'}")
        except Exception as e:
            print(f"Error koneksi ke Neo4j: {str(e)}")
            raise

    def close(self):
        """
        Menutup koneksi ke Neo4j
        """
        self.driver.close()

    def execute_query(self, query, parameters=None):
        """
        Menjalankan query Cypher pada Neo4j
        :param query: Query Cypher yang akan dijalankan
        :param parameters: Parameter untuk query (opsional)
        :return: Hasil dari query
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(query, parameters or {})
            return list(result)

    def clear_database(self):
        """
        Menghapus semua node dan relasi pada database
        """
        query = "MATCH (n) DETACH DELETE n"
        try:
            self.execute_query(query)
            print("Database berhasil dibersihkan")
        except Exception as e:
            print(f"Error saat membersihkan database: {str(e)}")

    def create_constraints_and_indexes(self):
        """
        Membuat constraint dan index di Neo4j
        """
        # Syntax untuk Neo4j 5.x
        queries = [
            # Constraints
            "CREATE CONSTRAINT Kabupaten_nama IF NOT EXISTS FOR (k:Kabupaten) REQUIRE k.nama IS UNIQUE;",
            "CREATE CONSTRAINT TempatWisata_id IF NOT EXISTS FOR (tw:TempatWisata) REQUIRE tw.id IS UNIQUE;",
            "CREATE CONSTRAINT Penginapan_id IF NOT EXISTS FOR (p:Penginapan) REQUIRE p.id IS UNIQUE;",
            "CREATE CONSTRAINT RumahMakan_id IF NOT EXISTS FOR (rm:RumahMakan) REQUIRE rm.id IS UNIQUE;",
            
            # Indexes
            "CREATE INDEX Kabupaten_nama_idx IF NOT EXISTS FOR (k:Kabupaten) ON (k.nama);",
            "CREATE INDEX TempatWisata_nama_idx IF NOT EXISTS FOR (tw:TempatWisata) ON (tw.nama);",
            "CREATE INDEX Penginapan_nama_idx IF NOT EXISTS FOR (p:Penginapan) ON (p.nama);",
            "CREATE INDEX RumahMakan_nama_idx IF NOT EXISTS FOR (rm:RumahMakan) ON (rm.nama);"
        ]
        
        # Syntax untuk Neo4j 4.x - akan dicoba jika 5.x gagal
        fallback_queries = [
            # Constraints
            "CREATE CONSTRAINT IF NOT EXISTS ON (k:Kabupaten) ASSERT k.nama IS UNIQUE;",
            "CREATE CONSTRAINT IF NOT EXISTS ON (tw:TempatWisata) ASSERT tw.id IS UNIQUE;",
            "CREATE CONSTRAINT IF NOT EXISTS ON (p:Penginapan) ASSERT p.id IS UNIQUE;",
            "CREATE CONSTRAINT IF NOT EXISTS ON (rm:RumahMakan) ASSERT rm.id IS UNIQUE;",
            
            # Indexes
            "CREATE INDEX IF NOT EXISTS FOR (k:Kabupaten) ON (k.nama);",
            "CREATE INDEX IF NOT EXISTS FOR (tw:TempatWisata) ON (tw.nama);",
            "CREATE INDEX IF NOT EXISTS FOR (p:Penginapan) ON (p.nama);",
            "CREATE INDEX IF NOT EXISTS FOR (rm:RumahMakan) ON (rm.nama);"
        ]
        
        # Mencoba syntax Neo4j 5.x terlebih dahulu
        success = True
        for query in queries:
            try:
                self.execute_query(query)
                print(f"Sukses: {query}")
            except Exception as e:
                success = False
                print(f"Error pada query: {query}")
                print(f"Pesan error: {str(e)}")
        
        # Jika gagal, coba syntax Neo4j 4.x
        if not success:
            print("\nMencoba format constraint/index alternatif untuk Neo4j versi lebih lama...")
            for query in fallback_queries:
                try:
                    self.execute_query(query)
                    print(f"Sukses: {query}")
                except Exception as e:
                    print(f"Error pada query: {query}")
                    print(f"Pesan error: {str(e)}")
                    
        print("\nProses pembuatan constraint dan index selesai.")

    def create_kabupaten(self, csv_file):
        """
        Membuat node Kabupaten dari file CSV
        :param csv_file: Path file CSV kabupaten
        """
        # Memastikan file ada
        if not os.path.exists(csv_file):
            print(f"File tidak ditemukan: {csv_file}")
            print(f"Current working directory: {os.getcwd()}")
            if os.path.exists('data'):
                print(f"Daftar file di direktori data: {os.listdir('data')}")
            return

        query = """
        CREATE (k:Kabupaten {
            nama: $nama,
            name: $nama,
            latitude: $latitude,
            longitude: $longitude
        })
        """
        
        try:
            with open(csv_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    params = {
                        'nama': row['kabupaten'],
                        'latitude': float(row['latitude']),
                        'longitude': float(row['longitude'])
                    }
                    
                    self.execute_query(query, params)
                    print(f"Kabupaten {row['kabupaten']} berhasil dibuat")
                
                # Verifikasi kabupaten yang dibuat
                result = self.execute_query("MATCH (k:Kabupaten) RETURN k.nama")
                kabupaten_list = [record["k.nama"] for record in result]
                print(f"Kabupaten dalam database: {', '.join(kabupaten_list)}")
                
        except Exception as e:
            print(f"Error saat membaca atau memproses file {csv_file}: {str(e)}")

    def create_tempat_wisata(self, csv_file):
        """
        Membuat node TempatWisata dan menghubungkannya dengan Kabupaten
        :param csv_file: Path file CSV tempat wisata
        """
        # Memastikan file ada
        if not os.path.exists(csv_file):
            print(f"File tidak ditemukan: {csv_file}")
            return
        
        # Daftar kabupaten yang ada di database
        kabupaten_result = self.execute_query("MATCH (k:Kabupaten) RETURN k.nama")
        kabupaten_list = [record["k.nama"] for record in kabupaten_result]
        print(f"Kabupaten tersedia untuk tempat wisata: {', '.join(kabupaten_list)}")
            
        query = """
        MATCH (k:Kabupaten {nama: $kabupaten})
        CREATE (tw:TempatWisata {
            id: $id,
            nama: $nama,
            name: $nama,
            rating: $rating,
            kategori: $kategori,
            latitude: $latitude,
            longitude: $longitude
        })
        CREATE (tw)-[:BERADA_DI]->(k)
        """
        
        count = 0
        created_count = 0
        try:
            with open(csv_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                print("\nMembaca file tempat wisata...")
                rows = list(reader)
                print(f"Total baris dalam file tempat wisata: {len(rows)}")
                
                for row in rows:
                    count += 1
                    
                    if row['kabupaten'] not in kabupaten_list:
                        print(f"SKIP: Tempat Wisata {row['nama_tempat_wisata']} - Kabupaten {row['kabupaten']} tidak ditemukan dalam database")
                        continue
                    
                    params = {
                        'id': row['id_tempat_wisata'],
                        'kabupaten': row['kabupaten'],
                        'nama': row['nama_tempat_wisata'],
                        'rating': float(row['rating']),
                        'kategori': row['kategori'],
                        'latitude': float(row['latitude']),
                        'longitude': float(row['longitude'])
                    }
                    
                    try:
                        self.execute_query(query, params)
                        created_count += 1
                        print(f"Tempat Wisata {row['nama_tempat_wisata']} berhasil dibuat (ID: {row['id_tempat_wisata']}, Kabupaten: {row['kabupaten']})")
                    except Exception as e:
                        print(f"Error saat membuat tempat wisata {row['nama_tempat_wisata']}: {str(e)}")
                
                # Verifikasi tempat wisata yang dibuat
                verify_query = """
                MATCH (tw:TempatWisata)
                RETURN tw.id, tw.nama, tw.kategori
                """
                verify_result = self.execute_query(verify_query)
                print(f"\nProses pembuatan tempat wisata selesai. Diproses: {count}, Dibuat: {created_count}")
                print(f"Tempat wisata dalam database: {len(verify_result)}")
                for i, record in enumerate(verify_result):
                    print(f"  {i+1}. {record['tw.nama']} (ID: {record['tw.id']}, Kategori: {record['tw.kategori']})")
                
        except Exception as e:
            print(f"Error saat membaca atau memproses file {csv_file}: {str(e)}")

    def create_penginapan(self, csv_file):
        """
        Membuat node Penginapan dan menghubungkannya dengan Kabupaten
        :param csv_file: Path file CSV penginapan
        """
        # Memastikan file ada
        if not os.path.exists(csv_file):
            print(f"File tidak ditemukan: {csv_file}")
            return
            
        query = """
        MATCH (k:Kabupaten {nama: $kabupaten})
        CREATE (p:Penginapan {
            id: $id,
            nama: $nama,
            name: $nama,
            rating: $rating,
            harga: $harga,
            latitude: $latitude,
            longitude: $longitude
        })
        CREATE (p)-[:BERADA_DI]->(k)
        """
        
        count = 0
        encodings = ['utf-8', 'latin-1', 'windows-1252']  # Daftar encoding yang akan dicoba
        
        for encoding in encodings:
            try:
                with open(csv_file, 'r', encoding=encoding) as file:
                    reader = csv.DictReader(file)
                    print(f"Berhasil membaca file dengan encoding: {encoding}")
                    
                    try:
                        for row in reader:
                            # Bersihkan kolom harga
                            harga_str = row['harga'].replace('Rp', '').replace('.', '').replace(',', '').replace('�', '').replace(' ', '').replace('-', '')
                            try:
                                harga = int(harga_str)
                            except ValueError:
                                print(f"Error: Tidak dapat mengonversi harga '{row['harga']}' untuk penginapan {row['nama_penginapan']} ke integer. Menggunakan 0 sebagai default.")
                                harga = 0
                            
                            params = {
                                'id': row['id_penginapan'],
                                'kabupaten': row['kabupaten'],
                                'nama': row['nama_penginapan'],
                                'rating': float(row['rating']),
                                'harga': harga,
                                'latitude': float(row['latitude']),
                                'longitude': float(row['longitude'])
                            }
                            
                            try:
                                self.execute_query(query, params)
                                count += 1
                                print(f"Penginapan {row['nama_penginapan']} berhasil dibuat")
                            except Exception as e:
                                print(f"Error saat membuat penginapan {row['nama_penginapan']}: {str(e)}")
                        print(f"Total penginapan dibuat: {count}")
                        return  # Keluar setelah berhasil memproses
                    except Exception as e:
                        print(f"Error saat memproses baris di file {csv_file}: {str(e)}")
                        return
            except UnicodeDecodeError as e:
                print(f"Gagal membaca file dengan encoding {encoding}: {str(e)}")
            except Exception as e:
                print(f"Error lain saat membaca file dengan encoding {encoding}: {str(e)}")
        
        print(f"Error: Tidak dapat membaca file {csv_file} dengan encoding yang dicoba: {', '.join(encodings)}")

    def create_rumah_makan(self, csv_file):
        """
        Membuat node RumahMakan dan menghubungkannya dengan Kabupaten
        :param csv_file: Path file CSV rumah makan
        """
        # Memastikan file ada
        if not os.path.exists(csv_file):
            print(f"File tidak ditemukan: {csv_file}")
            return
            
        query = """
        MATCH (k:Kabupaten {nama: $kabupaten})
        CREATE (rm:RumahMakan {
            id: $id,
            nama: $nama,
            name: $nama,
            rating: $rating,
            latitude: $latitude,
            longitude: $longitude
        })
        CREATE (rm)-[:BERADA_DI]->(k)
        """
        
        count = 0
        try:
            with open(csv_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    # Tambahkan latitude dan longitude jika tidak ada dalam CSV
                    try:
                        latitude = float(row.get('latitude', '0.0'))
                        longitude = float(row.get('longitude', '0.0'))
                    except ValueError:
                        print(f"Error konversi koordinat untuk {row.get('nama_rumah_makan')}")
                        latitude = 0.0
                        longitude = 0.0
                    
                    params = {
                        'id': row['id_rumah_makan'],
                        'kabupaten': row['kabupaten'],
                        'nama': row['nama_rumah_makan'],
                        'rating': float(row['rating']),
                        'latitude': latitude,
                        'longitude': longitude
                    }
                    
                    try:
                        self.execute_query(query, params)
                        count += 1
                        print(f"Rumah Makan {row['nama_rumah_makan']} berhasil dibuat")
                    except Exception as e:
                        print(f"Error saat membuat rumah makan {row['nama_rumah_makan']}: {str(e)}")
        except Exception as e:
            print(f"Error saat membaca atau memproses file {csv_file}: {str(e)}")

    def create_proximity_relationships(self, max_distance_km=10):
        """
        Membuat relasi ADA_AKSES_MENUJU antara tempat wisata, penginapan, dan rumah makan
        berdasarkan jarak geografis menggunakan Haversine distance
        :param max_distance_km: Jarak maksimal dalam kilometer
        """
        def haversine_distance(lat1, lon1, lat2, lon2):
            """
            Menghitung jarak Haversine antara dua titik koordinat dalam kilometer
            """
            R = 6371.0  # Radius bumi dalam kilometer
            lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            distance = R * c
            return distance

        # Mendapatkan data node untuk menghitung jarak
        get_data_query = """
        MATCH (n)
        WHERE n:TempatWisata OR n:Penginapan OR n:RumahMakan
        RETURN n.id AS id, labels(n)[0] AS type, n.latitude AS latitude, n.longitude AS longitude
        """
        
        try:
            nodes = self.execute_query(get_data_query)
            print(f"Mendapatkan {len(nodes)} node untuk perhitungan jarak")
            
            # Memproses node ke dalam dictionary untuk akses cepat
            node_dict = {}
            for node in nodes:
                node_dict[node['id']] = {
                    'type': node['type'],
                    'latitude': node['latitude'],
                    'longitude': node['longitude']
                }
            
            # Kombinasi tipe node untuk relasi
            type_combinations = [
                ('Penginapan', 'TempatWisata'),
                ('Penginapan', 'RumahMakan'),
                ('TempatWisata', 'RumahMakan')
            ]
            
            batch_size = 1000  # Ukuran batch untuk efisiensi
            for type1, type2 in type_combinations:
                print(f"Menghitung jarak antara {type1} dan {type2}...")
                distance_data = []
                
                # Filter node berdasarkan tipe
                type1_nodes = {id: data for id, data in node_dict.items() if data['type'] == type1}
                type2_nodes = {id: data for id, data in node_dict.items() if data['type'] == type2}
                
                # Hitung jarak antar node
                for id1, data1 in type1_nodes.items():
                    for id2, data2 in type2_nodes.items():
                        distance = haversine_distance(
                            data1['latitude'], data1['longitude'],
                            data2['latitude'], data2['longitude']
                        )
                        
                        if distance <= max_distance_km:
                            distance_data.append((id1, id2, distance))
                            
                            if len(distance_data) >= batch_size:
                                # Proses batch
                                params = {
                                    "batch": [
                                        {"id1": id1, "id2": id2, "distance": distance}
                                        for id1, id2, distance in distance_data
                                    ]
                                }
                                query = f"""
                                UNWIND $batch AS item
                                MATCH (a:{type1}), (b:{type2})
                                WHERE a.id = item.id1 AND b.id = item.id2
                                CREATE (a)-[:ADA_AKSES_MENUJU {{jarak: item.distance}}]->(b)
                                CREATE (b)-[:ADA_AKSES_MENUJU {{jarak: item.distance}}]->(a)
                                """
                                self.execute_query(query, params)
                                print(f"Berhasil membuat {len(distance_data)} relasi ADA_AKSES_MENUJU antara {type1} dan {type2}")
                                distance_data = []
                
                # Proses sisa batch
                if distance_data:
                    params = {
                        "batch": [
                            {"id1": id1, "id2": id2, "distance": distance}
                            for id1, id2, distance in distance_data
                        ]
                    }
                    query = f"""
                    UNWIND $batch AS item
                    MATCH (a:{type1}), (b:{type2})
                    WHERE a.id = item.id1 AND b.id = item.id2
                    CREATE (a)-[:ADA_AKSES_MENUJU {{jarak: item.distance}}]->(b)
                    CREATE (b)-[:ADA_AKSES_MENUJU {{jarak: item.distance}}]->(a)
                    """
                    self.execute_query(query, params)
                    print(f"Berhasil membuat {len(distance_data)} relasi ADA_AKSES_MENUJU antara {type1} dan {type2}")
                
        except Exception as e:
            print(f"Error saat membuat relasi ADA_AKSES_MENUJU: {str(e)}")

    def run_test_queries(self):
        """
        Menjalankan beberapa query pengujian untuk memverifikasi data
        """
        # Query 1: Menghitung jumlah node per label
        query1 = """
        MATCH (n)
        RETURN labels(n) AS Label, count(*) AS Count
        ORDER BY Count DESC
        """
        
        # Query 2: Menghitung jumlah relasi per tipe
        query2 = """
        MATCH ()-[r]->()
        RETURN type(r) AS Relationship, count(*) AS Count
        ORDER BY Count DESC
        """
        
        # Query 3: Memeriksa tempat wisata dengan rating tertinggi
        query3 = """
        MATCH (tw:TempatWisata)
        RETURN tw.nama AS NamaTempat, tw.rating AS Rating, tw.kategori AS Kategori
        ORDER BY tw.rating DESC
        LIMIT 3
        """
        
        # Query 4: Memeriksa penginapan dengan harga termurah
        query4 = """
        MATCH (p:Penginapan)
        RETURN p.nama AS NamaPenginapan, p.harga AS Harga, p.rating AS Rating
        ORDER BY p.harga ASC
        LIMIT 3
        """
        
        print("\n=== HASIL QUERY PENGUJIAN ===")
        
        try:
            print("\n1. Jumlah node per label:")
            result1 = self.execute_query(query1)
            for record in result1:
                print(f"  {record['Label']}: {record['Count']}")
        except Exception as e:
            print(f"Error pada query 1: {str(e)}")
        
        try:
            print("\n2. Jumlah relasi per tipe:")
            result2 = self.execute_query(query2)
            for record in result2:
                print(f"  {record['Relationship']}: {record['Count']}")
        except Exception as e:
            print(f"Error pada query 2: {str(e)}")
        
        try:
            print("\n3. Tempat wisata dengan rating tertinggi:")
            result3 = self.execute_query(query3)
            for record in result3:
                print(f"  {record['NamaTempat']} ({record['Kategori']}): {record['Rating']}")
        except Exception as e:
            print(f"Error pada query 3: {str(e)}")
        
        try:
            print("\n4. Penginapan dengan harga termurah:")
            result4 = self.execute_query(query4)
            for record in result4:
                print(f"  {record['NamaPenginapan']}: Rp {record['Harga']} (Rating: {record['Rating']})")
        except Exception as e:
            print(f"Error pada query 4: {str(e)}")

    def verify_detail(self):
        """
        Menjalankan verifikasi detail untuk menganalisis node dan relasi dalam database
        """
        print("\n=== VERIFIKASI DETAIL DATABASE ===")
        
        # 1. Verifikasi jumlah tempat wisata
        result1 = self.execute_query("MATCH (tw:TempatWisata) RETURN tw.nama, tw.id")
        print("\n1. Verifikasi Tempat Wisata:")
        tempat_wisata = list(result1)
        print(f"Jumlah tempat wisata dalam database: {len(tempat_wisata)}")
        
        for i, record in enumerate(tempat_wisata):
            print(f"  {i+1}. {record['tw.nama']} (ID: {record['tw.id']})")
        
        # 2. Verifikasi tempat wisata dan relasinya
        result2 = self.execute_query("""
        MATCH (tw:TempatWisata)-[r:BERADA_DI]->(k:Kabupaten)
        RETURN tw.nama, k.nama, type(r)
        """)
        print("\n2. Verifikasi Relasi Tempat Wisata ke Kabupaten:")
        relasi_tw_k = list(result2)
        print(f"Jumlah relasi tempat wisata ke kabupaten: {len(relasi_tw_k)}")
        
        for i, record in enumerate(relasi_tw_k):
            print(f"  {i+1}. {record['tw.nama']} -> {record['type(r)']} -> {record['k.nama']}")
        
        # 3. Periksa tempat wisata tanpa relasi ke kabupaten
        result3 = self.execute_query("""
        MATCH (tw:TempatWisata)
        WHERE NOT (tw)-[:BERADA_DI]->(:Kabupaten)
        RETURN tw.nama, tw.id
        """)
        print("\n3. Tempat Wisata Tanpa Relasi ke Kabupaten:")
        tw_tanpa_relasi = list(result3)
        print(f"Jumlah tempat wisata tanpa relasi ke kabupaten: {len(tw_tanpa_relasi)}")
        
        for i, record in enumerate(tw_tanpa_relasi):
            print(f"  {i+1}. {record['tw.nama']} (ID: {record['tw.id']})")
        
        # 4. Verifikasi kabupaten
        result4 = self.execute_query("MATCH (k:Kabupaten) RETURN k.nama")
        print("\n4. Verifikasi Kabupaten:")
        kabupaten = list(result4)
        print(f"Jumlah kabupaten dalam database: {len(kabupaten)}")
        
        for i, record in enumerate(kabupaten):
            print(f"  {i+1}. {record['k.nama']}")
        
        # 5. Verifikasi semua relasi
        result5 = self.execute_query("""
        MATCH (n1)-[r]->(n2)
        RETURN labels(n1)[0] as from_label, n1.nama as from_name,
            type(r) as relation, 
            labels(n2)[0] as to_label, n2.nama as to_name
        LIMIT 20
        """)
        print("\n5. Sampel Relasi dalam Database (max 20):")
        relasi = list(result5)
        
        for i, record in enumerate(relasi):
            print(f"  {i+1}. {record['from_label']} '{record['from_name']}' -> {record['relation']} -> {record['to_label']} '{record['to_name']}'")


def main():
    # Konfigurasi koneksi ke Neo4j
    uri = "bolt://localhost:7687"  # Sesuaikan dengan URI Neo4j server Anda
    
    # PENTING: Sesuaikan dengan username dan password Neo4j Anda
    username = "neo4j"  # Ganti dengan username Neo4j Anda yang benar
    password = "puan061002"  # Ganti dengan password Neo4j Anda yang benar
    
    # Tentukan database (opsional, kosongkan jika ingin menggunakan default)
    database = "ilustrasiknowledgegraph"  # Ganti dengan nama database yang ingin digunakan
    
    # Path file CSV
    # Tentukan path absolut untuk memastikan menemukan file
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    # Path relatif dari script ke file CSV
    kabupaten_csv = os.path.join(base_path, "data", "kabupaten.csv")
    tempat_wisata_csv = os.path.join(base_path, "data", "tourist_attraction.csv")
    penginapan_csv = os.path.join(base_path, "data", "place_to_stay.csv")
    rumah_makan_csv = os.path.join(base_path, "data", "restaurant.csv")
    
    print(f"Working directory: {base_path}")
    print(f"Mencari file di:")
    print(f"- {kabupaten_csv}")
    print(f"- {tempat_wisata_csv}")
    print(f"- {penginapan_csv}")
    print(f"- {rumah_makan_csv}")
    
    # Cek apakah file ada
    file_exists = True
    for file_path in [kabupaten_csv, tempat_wisata_csv, penginapan_csv, rumah_makan_csv]:
        exists = os.path.exists(file_path)
        print(f"File {file_path} ada: {exists}")
        if not exists:
            file_exists = False
    
    if not file_exists:
        print("PERINGATAN: Beberapa file tidak ditemukan. Periksa path file.")
        # Opsi alternative path jika path absolut tidak bekerja
        kabupaten_csv = "ilustrasiKnowledgeGraph/data/kabupaten.csv"
        tempat_wisata_csv = "ilustrasiKnowledgeGraph/data/tourist_attraction.csv"
        penginapan_csv = "ilustrasiKnowledgeGraph/data/place_to_stay.csv"
        rumah_makan_csv = "ilustrasiKnowledgeGraph/data/restaurant.csv"
        print("Mencoba menggunakan path relatif:")
        print(f"- {kabupaten_csv}")
        
    try:
        # Membuat instance Neo4jConnector
        connector = Neo4jConnector(uri, username, password, database)
        
        # Tanya pengguna apakah ingin membersihkan database terlebih dahulu
        clear_db = input("Apakah Anda ingin membersihkan database terlebih dahulu? (y/n): ").lower()
        if clear_db == 'y':
            connector.clear_database()
        
        # Membuat constraint dan index
        connector.create_constraints_and_indexes()
        
        # Membuat node Kabupaten
        connector.create_kabupaten(kabupaten_csv)
        
        # Membuat node TempatWisata
        connector.create_tempat_wisata(tempat_wisata_csv)
        
        # Membuat node Penginapan
        connector.create_penginapan(penginapan_csv)
        
        # Membuat node RumahMakan
        connector.create_rumah_makan(rumah_makan_csv)
        
        # Membuat relasi ADA_AKSES_MENUJU
        connector.create_proximity_relationships()
        
        # Menjalankan query pengujian
        connector.run_test_queries()
        
        # Menjalankan verifikasi detail
        connector.verify_detail()
        
        print("\nProses import data ke Neo4j berhasil!")
        
    except Exception as e:
        print(f"Terjadi kesalahan: {str(e)}")
    finally:
        # Menutup koneksi jika connector telah dibuat
        if 'connector' in locals():
            connector.close()

if __name__ == "__main__":
    main()