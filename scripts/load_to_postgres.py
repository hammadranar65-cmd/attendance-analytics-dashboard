"""
load_to_postgres.py — Loads the synthetic CSV data into your PostgreSQL database.

Run generate_synthetic_data.py first to create the CSV files, then run this
script to load them into PostgreSQL using the schema from database/schema.sql.

Requires: pip install psycopg2-binary pandas
Requires: a running PostgreSQL server and a database already created
          (e.g. `createdb attendance_db`), plus database/schema.sql already
          applied (see README for the exact commands).

Set your connection details via environment variables or edit DB_CONFIG below.
"""

import os

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

DB_CONFIG = {
    "host": os.environ.get("PGHOST", "localhost"),
    "port": os.environ.get("PGPORT", "5432"),
    "dbname": os.environ.get("PGDATABASE", "attendance_db"),
    "user": os.environ.get("PGUSER", "postgres"),
    "password": os.environ.get("PGPASSWORD", "postgres"),
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# Order matters: parents before children (foreign key dependencies)
LOAD_ORDER = [
    ("students.csv", "students",
     ["student_id", "roll_no", "full_name", "program", "enrollment_year"]),
    ("instructors.csv", "instructors",
     ["instructor_id", "full_name", "email"]),
    ("courses.csv", "courses",
     ["course_id", "course_code", "course_title", "credit_hours"]),
    ("sections.csv", "sections",
     ["section_id", "course_id", "instructor_id", "section_label", "semester", "attendance_method"]),
    ("enrollments.csv", "enrollments",
     ["enrollment_id", "student_id", "section_id"]),
    ("sessions.csv", "sessions",
     ["session_id", "section_id", "session_date", "day_of_week"]),
    ("attendance_records.csv", "attendance_records",
     ["record_id", "session_id", "student_id", "status", "source"]),
]


def load_table(conn, csv_file, table_name, columns):
    path = os.path.join(DATA_DIR, csv_file)
    if not os.path.exists(path):
        print(f"  SKIP {table_name}: {csv_file} not found. Run generate_synthetic_data.py first.")
        return

    df = pd.read_csv(path)
    df = df[columns]  # keep only the columns the table expects, in order

    rows = [tuple(row) for row in df.itertuples(index=False, name=None)]
    if not rows:
        print(f"  SKIP {table_name}: no rows in {csv_file}")
        return

    cols_sql = ", ".join(columns)
    query = f"INSERT INTO {table_name} ({cols_sql}) VALUES %s"

    with conn.cursor() as cur:
        execute_values(cur, query, rows, page_size=1000)
    conn.commit()
    print(f"  Loaded {len(rows)} rows into {table_name}")


def reset_sequences(conn):
    """After inserting explicit IDs, bump each table's auto-increment sequence
    so future inserts (from the app) don't collide with the loaded IDs."""
    sequences = [
        ("students", "student_id"), ("instructors", "instructor_id"),
        ("courses", "course_id"), ("sections", "section_id"),
        ("enrollments", "enrollment_id"), ("sessions", "session_id"),
        ("attendance_records", "record_id"),
    ]
    with conn.cursor() as cur:
        for table, id_col in sequences:
            cur.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', '{id_col}'), "
                f"COALESCE((SELECT MAX({id_col}) FROM {table}), 1))"
            )
    conn.commit()
    print("  Sequences reset to continue after loaded IDs.")


def main():
    print(f"Connecting to PostgreSQL database '{DB_CONFIG['dbname']}'...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
    except Exception as exc:
        print(f"\nERROR: Could not connect to PostgreSQL: {exc}")
        print("\nCheck that:")
        print("  1. PostgreSQL is running")
        print("  2. The database exists (createdb attendance_db)")
        print("  3. database/schema.sql has been applied")
        print("  4. Your connection details are correct (env vars or DB_CONFIG)")
        return

    print("Connected. Loading tables in dependency order...\n")
    for csv_file, table_name, columns in LOAD_ORDER:
        load_table(conn, csv_file, table_name, columns)

    print("\nResetting auto-increment sequences...")
    reset_sequences(conn)

    conn.close()
    print("\nDone. Your database is now populated with synthetic data.")


if __name__ == "__main__":
    main()
