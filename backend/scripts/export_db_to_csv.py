"""
Export all Excel course data from MySQL to CSV
"""
import os
import sys
import pymysql
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def export_course_to_csv(course_title: str, output_csv: str):
    """Export course data from MySQL to CSV."""
    
    # Connect to MySQL
    conn = pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', '3306')),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', ''),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    
    print(f"Connected to database: {os.getenv('DB_NAME')}")
    
    with conn.cursor() as cursor:
        # Fetch all lectures for the course
        cursor.execute(
            "SELECT * FROM video_data WHERE course_title = %s ORDER BY id ASC",
            (course_title,)
        )
        rows = cursor.fetchall()
    
    conn.close()
    
    if not rows:
        print(f"ERROR: No data found for course '{course_title}'")
        return
    
    print(f"Found {len(rows)} lectures for '{course_title}'")
    
    # Convert to DataFrame and save
    df = pd.DataFrame(rows)
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    
    print(f"✅ Exported {len(rows)} lectures to: {output_csv}")
    print(f"\nColumns: {', '.join(df.columns.tolist())}")
    print(f"\nChapters:")
    for chapter in df['chapter_title'].unique():
        count = len(df[df['chapter_title'] == chapter])
        print(f"  - {chapter}: {count} lectures")

if __name__ == "__main__":
    course_title = "Excel: Mother of Business Intelligence"
    output_csv = "../sql_full.csv"
    
    export_course_to_csv(course_title, output_csv)
