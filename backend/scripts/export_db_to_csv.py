"""
Export course data from MySQL video_data table to CSV.

Usage:
    # Export all configured courses:
    python scripts/export_db_to_csv.py

    # Export a single course:
    python scripts/export_db_to_csv.py --course "Excel: Mother of Business Intelligence"
"""
import os
import sys
import argparse
import pymysql
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# All courses to export (exact titles from the platform)
ALL_COURSES = [
    "Excel: Mother of Business Intelligence",
    "Welcome to The Bootcamp Experience",
    "Python: Beginner to Advanced For Data Professionals",
    "Get Job Ready: Power BI Data Analytics for All Levels 3.0",
    "SQL Beginner to Advanced For Data Professionals",
    "Start Applying for Jobs",
    "Start Building Your Online Credibility",
    "Building Online Credibility, Portfolio Projects & ATS Resume",
    "Virtual Internship",
    "Interview Preparation / Job Assistance",
    "DA 2.0: The AI Enabled Data Analyst",
    "Live Webinar",
    "Math and Statistics For AI, Data Science",
    "Deep Learning: Beginner to Advanced",
    "Master Machine Learning for Data Science & AI: Beginner to Advanced",
    "Start Applying for Jobs -DS",
    "Interview Preparation / Job Assistance - DS",
    "Gen AI",
    "Job Assistance Portal, ATS Resume & Portfolio Website",
    "Online Credibility & Domain Knowledge Course",
    "SQL for Data Science",
    "AI Toolkit For Professionals",
    "Mastering Communication & Stakeholder Management",
    "Microsoft Fabric Mini: For Data Analysts",
    "Natural Language Processing",
    "Tableau Mini",
    "Online Credibility",
    "Welcome to The Gen AI and Data Science Bootcamp Experience",
    "Gen AI to Agentic AI with Business Projects",
    "Mastering Time Management & Deep Work",
    "Virtual Internship 2",
    "Supplementary Learning: Projects & Case Studies",
    "Data Engineering Basics for Data Analysts",
    "AI Automation for Data Professionals",
    "Project: Build your first ETL Pipeline using AWS",
    "Data Engineering Foundations - II",
    "Apache Spark Fundamentals",
    "Snowflake Fundamentals",
    "Project: Build E-commerce Data Pipeline using Spark & Databricks",
    "Project 2: Build E-commerce Data Pipeline using Spark & Databricks",
    "Airflow Fundamentals",
    "Start Applying for Jobs - DE",
    "Interview Preparation / Job Assistance - DE",
    "ATS Resume & Portfolio Projects: DE",
    "Welcome to The Data Engineering Bootcamp Experience",
    "SQL Projects [Optional]",
    "Python Projects [Optional]",
    "Project: Securities Pricing Data Pipeline using Docker, Airflow, Snowflake and AWS",
    "Live Webinars",
    "Live Problem-Solving Sessions",
    "Kafka and Flink Fundamentals",
    "Real Time Fleet Telemetry Streaming and Analytics",
    "Data Engineering Foundations - I",
    "Practice Room 4: Snowflake, Airflow",
    "Personal Branding (LinkedIn & Beyond) for All Professionals",
    "HyperDelivery Project: Real-Time Streaming Analytics on Azure",
    "Build In Public",
]


def get_db_connection():
    """Connect to MySQL using environment variables."""
    return pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', '3306')),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', ''),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )


def export_courses(course_titles: list, output_csv: str):
    """Export course data from MySQL to CSV."""
    conn = get_db_connection()
    print(f"Connected to database: {os.getenv('DB_NAME')}")

    all_rows = []
    found_courses = []
    missing_courses = []

    with conn.cursor() as cursor:
        for title in course_titles:
            cursor.execute(
                "SELECT * FROM video_data WHERE course_title = %s ORDER BY id ASC",
                (title,)
            )
            rows = cursor.fetchall()

            if rows:
                all_rows.extend(rows)
                found_courses.append((title, len(rows)))
                print(f"  [OK] {title}: {len(rows)} lectures")
            else:
                missing_courses.append(title)
                print(f"  [MISSING] {title}: 0 lectures")

    conn.close()

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Found: {len(found_courses)} courses, {len(all_rows)} total lectures")
    if missing_courses:
        print(f"Missing: {len(missing_courses)} courses:")
        for title in missing_courses:
            print(f"  - {title}")
    print(f"{'=' * 60}")

    if not all_rows:
        print("ERROR: No data found!")
        sys.exit(1)

    # Save to CSV
    df = pd.DataFrame(all_rows)
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f"\nExported {len(all_rows)} lectures to: {output_csv}")

    return found_courses, missing_courses


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export course data from MySQL to CSV")
    parser.add_argument(
        '--course', default=None,
        help='Single course title to export (default: all courses)'
    )
    parser.add_argument(
        '--output', default='../sql_full.csv',
        help='Output CSV path (default: ../sql_full.csv)'
    )
    args = parser.parse_args()

    if args.course:
        courses = [args.course]
    else:
        courses = ALL_COURSES

    print(f"Exporting {len(courses)} course(s) from MySQL...")
    export_courses(courses, args.output)
