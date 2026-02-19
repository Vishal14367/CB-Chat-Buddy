"""
Data Ingestion Script: MySQL -> Parse WEBVTT -> Chunk -> Embed -> Qdrant

Usage:
    python scripts/ingest.py --course "Excel: Mother of Business Intelligence"
    python scripts/ingest.py --from-csv ../sql.csv --course "Excel: Mother of Business Intelligence"

Environment variables (or .env file):
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
    QDRANT_URL, QDRANT_API_KEY
    EMBEDDING_MODEL (default: all-MiniLM-L6-v2)
"""

import argparse
import hashlib
import os
import sys
from collections import defaultdict

import numpy as np
from dotenv import load_dotenv

# Add parent dir to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.utils.webvtt_parser import parse_and_chunk_transcript
from app.services.embedding import EmbeddingService


def get_db_connection():
    """Connect to MySQL using environment variables."""
    import pymysql

    conn = pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', '3306')),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', ''),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    return conn


def fetch_course_rows_from_db(conn, course_title: str) -> list:
    """Fetch all lecture rows for a course from MySQL."""
    with conn.cursor() as cursor:
        # First, check what columns exist
        cursor.execute("SHOW COLUMNS FROM video_data")
        columns = [row['Field'] for row in cursor.fetchall()]
        print(f"  Available columns: {', '.join(columns)}")

        # Check for explicit ordering columns
        has_chapter_order = 'chapter_order' in columns
        has_lecture_order = 'lecture_order' in columns or 'lecture_order_in_chapter' in columns

        if has_chapter_order and has_lecture_order:
            order_col = 'lecture_order' if 'lecture_order' in columns else 'lecture_order_in_chapter'
            print(f"  Found explicit ordering: chapter_order, {order_col}")
        else:
            print("  WARNING: No explicit ordering columns found. Deriving order from 'id' column.")
            print("  Please verify the derived lecture order is correct!")

        # Build SELECT query
        select_cols = ', '.join(columns)
        cursor.execute(
            f"SELECT {select_cols} FROM video_data WHERE course_title = %s ORDER BY id ASC",
            (course_title,)
        )
        rows = cursor.fetchall()

    return rows


def fetch_course_rows_from_csv(csv_path: str, course_title: str) -> list:
    """Fetch all lecture rows from the CSV file (dev/fallback mode)."""
    import pandas as pd

    df = pd.read_csv(csv_path, encoding='utf-8-sig')

    # Filter by course
    if course_title:
        df = df[df['course_title'] == course_title]

    rows = df.to_dict('records')
    return rows


def derive_lecture_order(rows: list) -> list:
    """Add sequential lecture_order based on best available ordering.

    Priority:
    1. Explicit chapter_order + lecture_order columns (if both exist)
    2. module_id column (platform's sequential ordering)
    3. id column (database insertion order — last resort)
    """
    if not rows:
        return rows

    sample = rows[0]

    # Priority 1: Explicit chapter_order + lecture_order columns
    has_chapter_order = 'chapter_order' in sample and sample['chapter_order'] is not None
    has_lecture_order = (
        ('lecture_order' in sample and sample['lecture_order'] is not None) or
        ('lecture_order_in_chapter' in sample and sample['lecture_order_in_chapter'] is not None)
    )

    if has_chapter_order and has_lecture_order:
        lec_order_key = 'lecture_order' if 'lecture_order' in sample else 'lecture_order_in_chapter'
        sorted_rows = sorted(rows, key=lambda r: (
            r.get('chapter_order', 0),
            r.get(lec_order_key, 0)
        ))
        for seq, row in enumerate(sorted_rows, start=1):
            row['_lecture_order'] = seq
        print("  Ordering: using explicit chapter_order + lecture_order")
        return sorted_rows

    # Priority 2: module_id (platform's sequential ordering)
    has_module_id = 'module_id' in sample and sample['module_id'] is not None
    if has_module_id:
        sorted_rows = sorted(rows, key=lambda r: int(r.get('module_id', 0)))
        for seq, row in enumerate(sorted_rows, start=1):
            row['_lecture_order'] = seq
        print("  Ordering: using module_id")
        return sorted_rows

    # Priority 3: Derive from id/position — rows already ordered by id ASC
    print("  Ordering: using id (fallback)")
    for seq, row in enumerate(rows, start=1):
        row['_lecture_order'] = seq

    return rows


def generate_point_id(lecture_id, chunk_index: int) -> int:
    """Generate deterministic Qdrant point ID from lecture_id + chunk_index."""
    key = f"{lecture_id}_{chunk_index}"
    hash_hex = hashlib.sha256(key.encode()).hexdigest()[:16]
    return int(hash_hex, 16)


def setup_qdrant_collection(client, collection_name: str, vector_size: int = 384):
    """Create Qdrant collection if it doesn't exist. Create payload indexes."""
    from qdrant_client.models import Distance, VectorParams, PayloadSchemaType

    collections = [c.name for c in client.get_collections().collections]

    if collection_name in collections:
        print(f"  Collection '{collection_name}' already exists")
    else:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE
            )
        )
        print(f"  Created collection '{collection_name}' ({vector_size} dims, cosine)")

    # Create payload indexes for fast filtering
    for field, schema_type in [
        ("course_title", PayloadSchemaType.KEYWORD),
        ("chapter_title", PayloadSchemaType.KEYWORD),
        ("lecture_order", PayloadSchemaType.INTEGER),
        ("lecture_id", PayloadSchemaType.KEYWORD),
    ]:
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field,
                field_schema=schema_type
            )
            print(f"  Created index on '{field}' ({schema_type})")
        except Exception:
            # Index may already exist
            pass


def process_and_upsert(
    rows: list,
    embedding_service: EmbeddingService,
    qdrant_client,
    collection_name: str,
    batch_size: int = 64
):
    """Process all rows: parse VTT, chunk, embed, upsert to Qdrant."""
    from qdrant_client.models import PointStruct

    total_chunks = 0
    skipped_lectures = 0
    all_points = []

    for row in rows:
        lecture_id = row.get('id', row.get('lecture_id', ''))
        lecture_title = row.get('lecture_title', 'Unknown')
        course_title = row.get('course_title', '')
        chapter_title = row.get('chapter_title', '')
        lecture_order = row.get('_lecture_order', 0)
        player_embed_url = row.get('player_embed_url', '')
        transcript = row.get('transcript', '')

        if not transcript or (hasattr(transcript, '__class__') and str(transcript) == 'nan'):
            skipped_lectures += 1
            continue

        # Parse VTT and chunk by time windows
        chunks = parse_and_chunk_transcript(str(transcript), window_seconds=50)

        if not chunks:
            skipped_lectures += 1
            continue

        # Prepare texts for batch embedding
        chunk_texts = [chunk.text for chunk in chunks]

        # Generate embeddings for all chunks in this lecture
        embeddings = embedding_service.encode(chunk_texts)
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)

        # Build Qdrant points
        for chunk, embedding in zip(chunks, embeddings):
            point_id = generate_point_id(lecture_id, chunk.chunk_index)
            point = PointStruct(
                id=point_id,
                vector=embedding.tolist(),
                payload={
                    "course_title": course_title,
                    "chapter_title": chapter_title,
                    "lecture_title": lecture_title,
                    "lecture_order": lecture_order,
                    "lecture_id": str(lecture_id),
                    "chunk_index": chunk.chunk_index,
                    "timestamp_start": chunk.timestamp_start,
                    "timestamp_end": chunk.timestamp_end,
                    "duration_seconds": chunk.duration_seconds,
                    "player_embed_url": player_embed_url,
                    "text": chunk.text
                }
            )
            all_points.append(point)

        total_chunks += len(chunks)
        print(f"  [{lecture_order:3d}] {lecture_title[:60]:<60} -> {len(chunks)} chunks")

    # Upsert in batches
    print(f"\nUpserting {len(all_points)} points to Qdrant...")
    for i in range(0, len(all_points), batch_size):
        batch = all_points[i:i + batch_size]
        qdrant_client.upsert(
            collection_name=collection_name,
            points=batch
        )
        print(f"  Upserted batch {i // batch_size + 1}/{(len(all_points) + batch_size - 1) // batch_size}")

    return total_chunks, skipped_lectures, len(all_points)


def verify_ingestion(qdrant_client, collection_name: str, embedding_service: EmbeddingService):
    """Run a quick test search to verify data was ingested correctly."""
    from qdrant_client.models import Filter, FieldCondition, Range

    # Get collection info
    info = qdrant_client.get_collection(collection_name)
    print(f"\n  Collection points: {info.points_count}")
    print(f"  Vector size: {info.config.params.vectors.size}")

    # Test search with filter
    test_query = "What is Excel?"
    query_vector = embedding_service.encode(test_query).tolist()

    try:
        results = qdrant_client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=3,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="lecture_order",
                        range=Range(lte=10)
                    )
                ]
            )
        ).points

        print(f"\n  Test search: '{test_query}' (lecture_order <= 10)")
        for r in results:
            print(f"    Score: {r.score:.4f} | "
                  f"Lecture: {r.payload['lecture_title'][:40]} | "
                  f"Time: {r.payload['timestamp_start']}-{r.payload['timestamp_end']}")
    except Exception as e:
        print(f"\n  Search verification failed: {str(e)}")
        print("  Checking if 'search' method exists as fallback...")
        try:
            results = qdrant_client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=3,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="lecture_order",
                            range=Range(lte=10)
                        )
                    ]
                )
            )
            for r in results:
                print(f"    Score: {r.score:.4f} | "
                      f"Lecture: {r.payload['lecture_title'][:40]} | "
                      f"Time: {r.payload['timestamp_start']}-{r.payload['timestamp_end']}")
        except Exception as e2:
            print(f"  Fallback search also failed: {str(e2)}")


def main():
    parser = argparse.ArgumentParser(description="Ingest course data into Qdrant")
    parser.add_argument(
        '--course',
        default='Excel: Mother of Business Intelligence',
        help='Course title to ingest (default: Excel course)'
    )
    parser.add_argument(
        '--from-csv',
        default=None,
        help='Path to CSV file (dev mode, skips MySQL)'
    )
    parser.add_argument(
        '--collection',
        default='course_transcripts',
        help='Qdrant collection name (default: course_transcripts)'
    )
    parser.add_argument(
        '--env-file',
        default=None,
        help='Path to .env file (default: auto-detect)'
    )
    args = parser.parse_args()

    # Load environment
    if args.env_file:
        load_dotenv(args.env_file)
    else:
        # Try multiple locations
        for env_path in ['.env', '../.env', 'backend/.env']:
            if os.path.exists(env_path):
                load_dotenv(env_path)
                break

    print("=" * 70)
    print("  CODEBASICS COURSE DATA INGESTION")
    print("=" * 70)
    print(f"\n  Course: {args.course}")
    print(f"  Collection: {args.collection}")

    # Step 1: Fetch data
    print("\n--- Step 1: Fetching course data ---")
    if args.from_csv:
        print(f"  Source: CSV file ({args.from_csv})")
        rows = fetch_course_rows_from_csv(args.from_csv, args.course)
    else:
        print("  Source: MySQL database")
        conn = get_db_connection()
        try:
            rows = fetch_course_rows_from_db(conn, args.course)
        finally:
            conn.close()

    print(f"  Found {len(rows)} lectures")

    if not rows:
        print("  ERROR: No lectures found for this course!")
        sys.exit(1)

    # Step 2: Derive lecture ordering
    print("\n--- Step 2: Deriving lecture order ---")
    rows = derive_lecture_order(rows)

    # Step 3: Initialize embedding model
    print("\n--- Step 3: Loading embedding model ---")
    model_name = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
    embedding_service = EmbeddingService(model_name=model_name)

    # Step 4: Setup Qdrant
    print("\n--- Step 4: Setting up Qdrant ---")
    from qdrant_client import QdrantClient

    qdrant_url = os.getenv('QDRANT_URL', 'http://localhost:6333')
    qdrant_api_key = os.getenv('QDRANT_API_KEY')

    if qdrant_api_key:
        client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        print(f"  Connected to Qdrant Cloud: {qdrant_url}")
    else:
        client = QdrantClient(url=qdrant_url)
        print(f"  Connected to Qdrant: {qdrant_url}")

    setup_qdrant_collection(client, args.collection, embedding_service.vector_size)

    # Step 5: Process and upsert
    print("\n--- Step 5: Processing transcripts ---")
    total_chunks, skipped, total_points = process_and_upsert(
        rows, embedding_service, client, args.collection
    )

    print(f"\n--- Results ---")
    print(f"  Lectures processed: {len(rows) - skipped}")
    print(f"  Lectures skipped (no transcript): {skipped}")
    print(f"  Total chunks created: {total_chunks}")
    print(f"  Total points upserted: {total_points}")

    # Step 6: Verify
    print("\n--- Step 6: Verification ---")
    verify_ingestion(client, args.collection, embedding_service)

    print("\n" + "=" * 70)
    print("  INGESTION COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    main()
