import sys
from app.db.session import SessionLocal
from app.pipeline.ingest import ingest_and_fuse_data

def main():
    print("Initializing real catalog ingestion...")
    db = SessionLocal()
    try:
        # Run pipeline for 15 records to get real API values and uncertainties
        result = ingest_and_fuse_data(db, limit=15)
        print("Ingestion results:", result)
    except Exception as e:
        print("Error during ingestion:", e)
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
