"""
Delete and recreate the Qdrant collection, then ingest ALL courses from scratch.
This is a clean slate re-ingest to remove orphaned old data.
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
from qdrant_client import QdrantClient

CSV_PATH = "sql_full.csv"
COLLECTION = "course_transcripts"

# Connect
model_name = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
print(f"\nLoading embedding model: {model_name}")
embedding_service = EmbeddingService(model_name=model_name)

qdrant_url = os.getenv('QDRANT_URL', 'http://localhost:6333')
qdrant_api_key = os.getenv('QDRANT_API_KEY')
if qdrant_api_key:
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    print(f"Connected to Qdrant Cloud: {qdrant_url}")
else:
    client = QdrantClient(url=qdrant_url)
    print(f"Connected to Qdrant: {qdrant_url}")

# Step 1: DELETE the existing collection for a clean slate
print(f"\n>>> DELETING collection '{COLLECTION}' to remove stale data...")
try:
    client.delete_collection(COLLECTION)
    print(f"    Collection deleted.")
except Exception as e:
    print(f"    Could not delete (may not exist): {e}")

# Step 2: Recreate
print(f"\n>>> Recreating collection '{COLLECTION}'...")
setup_qdrant_collection(client, COLLECTION, embedding_service.vector_size)

# Step 3: Read all courses
df = pd.read_csv(CSV_PATH, encoding='utf-8-sig')
all_courses = sorted(df['course_title'].unique().tolist())
print(f"\n>>> Ingesting {len(all_courses)} courses...\n")

grand_chunks = grand_points = grand_skipped = 0

for i, course in enumerate(all_courses, 1):
    print(f"{'='*70}")
    print(f"  [{i}/{len(all_courses)}] {course}")
    print(f"{'='*70}")
    rows = fetch_course_rows_from_csv(CSV_PATH, course)
    if not rows:
        print("  WARNING: No rows found, skipping.")
        continue
    print(f"  Lectures in CSV: {len(rows)}")
    rows = derive_lecture_order(rows)
    total_chunks, skipped, total_points = process_and_upsert(rows, embedding_service, client, COLLECTION)
    grand_chunks += total_chunks
    grand_points += total_points
    grand_skipped += skipped
    print(f"  Done: {len(rows)-skipped} lectures, {total_chunks} chunks, {total_points} points\n")

print(f"\n{'='*70}")
print(f"  CLEAN INGEST COMPLETE")
print(f"{'='*70}")
print(f"  Courses  : {len(all_courses)}")
print(f"  Chunks   : {grand_chunks}")
print(f"  Points   : {grand_points}")
print(f"  Skipped  : {grand_skipped}")
print(f"{'='*70}\n")

verify_ingestion(client, COLLECTION, embedding_service)
