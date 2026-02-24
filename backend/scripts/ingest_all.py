"""
Batch ingest ALL courses from sql_full.csv into Qdrant.
Run from the repo root:
    python backend/scripts/ingest_all.py --from-csv sql_full.csv
"""
import sys
import os
import argparse
import pandas as pd
from dotenv import load_dotenv

# Load .env
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

def main():
    parser = argparse.ArgumentParser(description="Ingest ALL courses from CSV into Qdrant")
    parser.add_argument('--from-csv', required=True, help='Path to CSV file')
    parser.add_argument('--collection', default='course_transcripts', help='Qdrant collection name')
    args = parser.parse_args()

    # Read course list
    df = pd.read_csv(args.from_csv, encoding='utf-8-sig')
    all_courses = sorted(df['course_title'].unique().tolist())

    print("=" * 70)
    print("  CODEBASICS BATCH COURSE INGESTION")
    print("=" * 70)
    print(f"\n  Total courses to ingest: {len(all_courses)}")
    print(f"  Collection: {args.collection}")
    print(f"  CSV: {args.from_csv}\n")

    # Init embedding model
    model_name = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
    print(f"Loading embedding model: {model_name}")
    embedding_service = EmbeddingService(model_name=model_name)

    # Connect to Qdrant
    from qdrant_client import QdrantClient
    qdrant_url = os.getenv('QDRANT_URL', 'http://localhost:6333')
    qdrant_api_key = os.getenv('QDRANT_API_KEY')
    if qdrant_api_key:
        client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        print(f"Connected to Qdrant Cloud: {qdrant_url}\n")
    else:
        client = QdrantClient(url=qdrant_url)
        print(f"Connected to Qdrant: {qdrant_url}\n")

    # Setup collection once
    setup_qdrant_collection(client, args.collection, embedding_service.vector_size)

    # Ingest each course
    grand_total_chunks = 0
    grand_total_points = 0
    grand_skipped = 0

    for i, course in enumerate(all_courses, 1):
        print(f"\n{'=' * 70}")
        print(f"  [{i}/{len(all_courses)}] {course}")
        print(f"{'=' * 70}")

        rows = fetch_course_rows_from_csv(args.from_csv, course)
        if not rows:
            print(f"  WARNING: No rows found, skipping.")
            continue

        print(f"  Lectures in CSV: {len(rows)}")
        rows = derive_lecture_order(rows)

        total_chunks, skipped, total_points = process_and_upsert(
            rows, embedding_service, client, args.collection
        )
        grand_total_chunks += total_chunks
        grand_total_points += total_points
        grand_skipped += skipped

        print(f"  Done: {len(rows) - skipped} lectures, {total_chunks} chunks, {total_points} points")

    # Final summary
    print(f"\n{'=' * 70}")
    print(f"  BATCH INGESTION COMPLETE")
    print(f"{'=' * 70}")
    print(f"  Courses ingested : {len(all_courses)}")
    print(f"  Total chunks     : {grand_total_chunks}")
    print(f"  Total points     : {grand_total_points}")
    print(f"  Lectures skipped : {grand_skipped} (no transcript)")
    print(f"{'=' * 70}\n")

    # Quick sanity verification
    print("Running verification search...")
    verify_ingestion(client, args.collection, embedding_service)

if __name__ == '__main__':
    main()
