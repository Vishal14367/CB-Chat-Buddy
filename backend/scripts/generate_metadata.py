"""
Generate backend/data/course_metadata.json from the CSV export.

This applies chapter overrides and merges so the JSON matches
what the CSV parser would build at runtime.  The JSON is committed
to git and used as a lightweight fallback in Docker/RAG mode when
the full CSV is not present.

Usage:
    cd backend
    python -m scripts.generate_metadata
"""

import json
import os
import sys

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.utils.csv_parser import CSVDataSource

CSV_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'sql_full.csv')
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'course_metadata.json')


def main():
    if not os.path.exists(CSV_PATH):
        print(f"ERROR: CSV not found at {CSV_PATH}")
        sys.exit(1)

    data = CSVDataSource(CSV_PATH)

    metadata = {}
    for course_id, course_data in data.course_structure.items():
        metadata[course_id] = {
            'course_title': course_data['course_title'],
            'chapters': course_data['chapters'],
        }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    total_lectures = sum(
        sum(len(ch['lectures']) for ch in c['chapters'])
        for c in metadata.values()
    )
    print(f"Generated {OUTPUT_PATH}")
    print(f"  {len(metadata)} courses, {total_lectures} lectures")


if __name__ == '__main__':
    main()
