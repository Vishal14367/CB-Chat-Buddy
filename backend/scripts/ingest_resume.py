"""
Resume batch ingest - run only the remaining/failed courses.
"""
import sys
import os
import pandas as pd
from dotenv import load_dotenv

for env_path in ['.env', '../.env', 'backend/.env']:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"Loaded env from: {env_path}")
        break

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.ingest import (
    fetch_course_rows_from_csv,
    derive_lecture_order,
    setup_qdrant_collection,
    process_and_upsert,
    verify_ingestion,
)
from app.services.embedding import EmbeddingService

# Only these courses need to be (re-)ingested
COURSES_TO_INGEST = [
    "Math and Statistics For AI, Data Science",   # may have timed out mid-upsert
    "Personal Branding (LinkedIn & Beyond) for All Professionals",
    "Python: Beginner to Advanced For Data Professionals",
    "SQL Beginner to Advanced For Data Professionals",
]

CSV_PATH = "sql_full.csv"
COLLECTION = "course_transcripts"

# Init
model_name = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
print(f"Loading embedding model: {model_name}")
embedding_service = EmbeddingService(model_name=model_name)

from qdrant_client import QdrantClient
qdrant_url = os.getenv('QDRANT_URL', 'http://localhost:6333')
qdrant_api_key = os.getenv('QDRANT_API_KEY')
if qdrant_api_key:
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    print(f"Connected to Qdrant Cloud: {qdrant_url}\n")
else:
    client = QdrantClient(url=qdrant_url)
    print(f"Connected to Qdrant: {qdrant_url}\n")

setup_qdrant_collection(client, COLLECTION, embedding_service.vector_size)

for i, course in enumerate(COURSES_TO_INGEST, 1):
    print(f"\n{'='*70}")
    print(f"  [{i}/{len(COURSES_TO_INGEST)}] {course}")
    print(f"{'='*70}")
    rows = fetch_course_rows_from_csv(CSV_PATH, course)
    if not rows:
        print(f"  WARNING: No rows found, skipping.")
        continue
    print(f"  Lectures in CSV: {len(rows)}")
    rows = derive_lecture_order(rows)
    total_chunks, skipped, total_points = process_and_upsert(rows, embedding_service, client, COLLECTION)
    print(f"  Done: {len(rows)-skipped} lectures, {total_chunks} chunks, {total_points} points")

print("\n" + "="*70)
print("  RESUME INGESTION COMPLETE")
print("="*70)
verify_ingestion(client, COLLECTION, embedding_service)
