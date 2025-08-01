import os
import folium
from neo4j import GraphDatabase
from typing import Dict, Any

# Konfigurasi Neo4j
NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "puan061002")

def get_coordinates_from_neo4j(tx, node_type, node_id):
    """
    Ambil koordinat dari node Neo4j berdasarkan tipe dan ID
    
    Args:
        tx: Transaksi Neo4j
        node_type (str): Tipe node (Penginapan, TempatWisata, RumahMakan)
        node_id (str): ID node yang dicari
    
    Returns:
        dict: Koordinat dengan latitude dan longitude
    """
    query = f"""
    MATCH (n:{node_type} {{id: $node_id}})
    RETURN 
        CASE 
            WHEN exists(n.latitude) AND exists(n.longitude) 
            THEN {{latitude: n.latitude, longitude: n.longitude}}
            ELSE NULL 
        END AS koordinat
    """
    
    result = tx.run(query, node_id=node_id)
    record = result.single()
    
    if record and record['koordinat']:
        return record['koordinat']
    else:
        # Log untuk debugging
        print(f"Koordinat tidak ditemukan untuk {node_type} dengan ID {node_id}")
        return None

def create_map(coordinates: Dict[str, Dict[str, float]]) -> folium.Map:
    """
    Fungsi untuk membuat peta dengan koordinat yang diberikan
    """
    # Ambil koordinat penginapan sebagai pusat peta
    center_lat = coordinates.get('penginapan', {}).get('lat', -7.8)
    center_lng = coordinates.get('penginapan', {}).get('lng', 110.4)

    # Log koordinat penginapan
    print(f"Koordinat Penginapan: Lat: {center_lat}, Lon: {center_lng}")
    
    # Buat peta
    map_obj = folium.Map(location=[center_lat, center_lng], zoom_start=13)
    
    # Daftar lokasi untuk ditambahkan ke peta
    locations = {
        'Penginapan': coordinates.get('penginapan', {}),
        'Tempat Wisata 1': coordinates.get('wisata1', {}),
        'Tempat Wisata 2': coordinates.get('wisata2', {}),
        'Rumah Makan': coordinates.get('rumah_makan', {})
    }
    
    for name, location in locations.items():
        if location and 'lat' in location and 'lng' in location:
            # Log koordinat tempat wisata
            print(f"Koordinat {name}: Lat: {location['lat']}, Lon: {location['lng']}")
            folium.Marker(
                location=[location['lat'], location['lng']], 
                popup=name
            ).add_to(map_obj)
    
    return map_obj

# Contoh penggunaan (opsional)
def main():
    # Contoh ID (sesuaikan dengan data Anda)
    # ID-nya disesuaikan dengan data yang Anda miliki
    coordinates = {
        'penginapan': {'lat': -7.7956, 'lng': 110.3695},
        'wisata1': {'lat': -7.7812, 'lng': 110.3664},
        'wisata2': {'lat': -7.7817, 'lng': 110.3656},
        'rumah_makan': {'lat': -7.7921, 'lng': 110.3710}
    }

    if coordinates:
        map_obj = create_map(coordinates)
        map_obj.save("peta.html")
        print("Peta berhasil dibuat!")
    else:
        print("Gagal mendapatkan koordinat")

if __name__ == "__main__":
    main()
