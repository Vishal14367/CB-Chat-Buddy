"""
Re-ingest all courses currently in Qdrant with corrected lecture ordering.
Uses module_id for ordering instead of id.

Usage: python scripts/reingest_all.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
from qdrant_client import QdrantClient

from scripts.ingest import (
    get_db_connection,
    fetch_course_rows_from_db,
    derive_lecture_order,
    process_and_upsert,
    setup_qdrant_collection,
)
from app.services.embedding import EmbeddingService


def get_qdrant_courses(client, collection_name):
    """Get all unique course titles from Qdrant."""
    courses = set()
    offset = None
    while True:
        results, offset = client.scroll(
            collection_name=collection_name,
            limit=250,
            offset=offset,
            with_payload=["course_title"]
        )
        if not results:
            break
        for p in results:
            courses.add(p.payload.get("course_title", ""))
        if offset is None:
            break
    return sorted(courses)


def main():
    # Load env
    for env_path in ['.env', '../.env', 'backend/.env']:
        if os.path.exists(env_path):
            load_dotenv(env_path)
            break

    print("=" * 70)
    print("  RE-INGESTION: Fix lecture ordering using module_id")
    print("=" * 70)

    # Setup Qdrant client
    qdrant_url = os.getenv('QDRANT_URL')
    qdrant_api_key = os.getenv('QDRANT_API_KEY')
    collection_name = 'course_transcripts'

    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key) if qdrant_api_key else QdrantClient(url=qdrant_url)

    # Get courses currently in Qdrant
    courses = get_qdrant_courses(client, collection_name)
    print(f"\nFound {len(courses)} courses in Qdrant to re-ingest\n")

    # Setup embedding model
    model_name = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
    embedding_service = EmbeddingService(model_name=model_name)
    setup_qdrant_collection(client, collection_name, embedding_service.vector_size)

    # Connect to DB
    conn = get_db_connection()

    total_courses = 0
    total_chunks_all = 0

    try:
        for i, course_title in enumerate(courses, 1):
            print(f"\n--- [{i}/{len(courses)}] {course_title} ---")
            rows = fetch_course_rows_from_db(conn, course_title)

            if not rows:
                print("  SKIP: No rows found in DB")
                continue

            rows = derive_lecture_order(rows)
            total_chunks, skipped, total_points = process_and_upsert(
                rows, embedding_service, client, collection_name
            )
            total_courses += 1
            total_chunks_all += total_chunks
            print(f"  Done: {total_chunks} chunks, {skipped} skipped")
    finally:
        conn.close()

    print(f"\n{'=' * 70}")
    print(f"  RE-INGESTION COMPLETE")
    print(f"  Courses: {total_courses}, Total chunks: {total_chunks_all}")
    print(f"{'=' * 70}")


if __name__ == '__main__':
    main()
