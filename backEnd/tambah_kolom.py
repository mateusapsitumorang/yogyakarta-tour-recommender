from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        # Gunakan text() untuk kueri SQL
        db.session.execute(text('''
        ALTER TABLE user_recommendation_feedback 
        ADD COLUMN rating_penginapan FLOAT;
        '''))
        
        db.session.execute(text('''
        ALTER TABLE user_recommendation_feedback 
        ADD COLUMN harga_penginapan INTEGER;
        '''))
        
        db.session.execute(text('''
        ALTER TABLE user_recommendation_feedback 
        ADD COLUMN rating_wisata_1 FLOAT;
        '''))
        
        db.session.execute(text('''
        ALTER TABLE user_recommendation_feedback 
        ADD COLUMN rating_wisata_2 FLOAT;
        '''))
        
        db.session.execute(text('''
        ALTER TABLE user_recommendation_feedback 
        ADD COLUMN rating_rumah_makan FLOAT;
        '''))
        
        db.session.commit()
        print("Kolom berhasil ditambahkan!")
    except Exception as e:
        db.session.rollback()
        print(f"Kesalahan saat menambahkan kolom: {e}")

    # Verifikasi kolom
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    columns = inspector.get_columns('user_recommendation_feedback')
    print("\nKolom yang ada:")
    for column in columns:
        print(column['name'])