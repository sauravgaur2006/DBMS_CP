"""
Automatic Index Recommendation — Synthetic Data Seeder
======================================================
Populates the index_recommender database with realistic synthetic data:
  - Student:    10,000 rows
  - Course:       500 rows
  - Enrollment: 50,000 rows
  - Attendance: 100,000 rows

Uses a fixed random seed (42) so every teammate gets functionally
equivalent data distributions when running on their own local MySQL.

Usage:
    python database/seed.py

Requires a .env file in the project root with DB_HOST, DB_USER,
DB_PASSWORD, and DB_NAME.
"""

import os
import random

from dotenv import load_dotenv
from faker import Faker
import mysql.connector

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SEED = 42
BATCH_SIZE = 5000

NUM_STUDENTS = 10_000
NUM_COURSES = 500
NUM_ENROLLMENTS = 50_000
NUM_ATTENDANCE = 100_000

DEPARTMENTS = [
    "Computer Science", "Electrical Engineering", "Mechanical Engineering",
    "Civil Engineering", "Mathematics", "Physics", "Chemistry",
    "Biology", "Economics", "Business Administration",
]

CITIES = [
    "Mumbai", "Pune", "Delhi", "Bangalore", "Chennai",
    "Hyderabad", "Kolkata", "Ahmedabad", "Jaipur", "Lucknow",
    "Nagpur", "Indore", "Bhopal", "Patna", "Chandigarh",
]

SEMESTERS = [
    "Fall 2022", "Spring 2023", "Fall 2023", "Spring 2024",
    "Fall 2024", "Spring 2025",
]

COURSE_PREFIXES = [
    "Introduction to", "Advanced", "Principles of", "Fundamentals of",
    "Applied", "Topics in", "Workshop on", "Seminar in",
]

COURSE_SUBJECTS = [
    "Algorithms", "Data Structures", "Database Systems", "Machine Learning",
    "Artificial Intelligence", "Computer Networks", "Operating Systems",
    "Software Engineering", "Thermodynamics", "Circuit Analysis",
    "Structural Mechanics", "Linear Algebra", "Calculus", "Statistics",
    "Quantum Physics", "Organic Chemistry", "Microeconomics",
    "Financial Accounting", "Signal Processing", "Control Systems",
    "Embedded Systems", "Compiler Design", "Digital Logic",
    "Probability Theory", "Discrete Mathematics",
]


def resolve_host(h: str) -> str:
    if h in ("localhost", "127.0.0.1"):
        return h
    try:
        import socket
        return socket.gethostbyname(h)
    except Exception:
        try:
            import urllib.request, json
            url = f"https://dns.google/resolve?name={h}"
            res = json.loads(urllib.request.urlopen(url, timeout=5).read())
            for ans in res.get("Answer", []):
                if ans.get("type") == 1:
                    return ans["data"]
        except Exception:
            pass
    return h


def get_connection():
    """Create a MySQL connection using .env credentials."""
    load_dotenv()
    host = os.getenv("DB_HOST", "localhost")
    resolved_host = resolve_host(host)
    kwargs = {
        "host": resolved_host,
        "port": int(os.getenv("DB_PORT", 3306)),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME"),
    }
    if host not in ("localhost", "127.0.0.1"):
        kwargs["ssl_disabled"] = False
    return mysql.connector.connect(**kwargs)


def truncate_tables(cursor):
    """Clear all tables in dependency-safe order."""
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    for table in ("Attendance", "Enrollment", "Course", "Student"):
        cursor.execute(f"TRUNCATE TABLE {table};")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    print("[OK] Truncated all tables.")


def seed_students(cursor, fake):
    """Generate and insert Student rows."""
    print(f"  Seeding {NUM_STUDENTS:,} students ...", end=" ", flush=True)
    rows = []
    for _ in range(NUM_STUDENTS):
        rows.append((
            fake.name(),
            random.choice(DEPARTMENTS),
            random.randint(1, 4),
            random.choice(CITIES),
        ))
    sql = "INSERT INTO Student (name, department, year, city) VALUES (%s, %s, %s, %s)"
    for i in range(0, len(rows), BATCH_SIZE):
        cursor.executemany(sql, rows[i : i + BATCH_SIZE])
    print("done.")


def seed_courses(cursor, fake):
    """Generate and insert Course rows."""
    print(f"  Seeding {NUM_COURSES:,} courses ...", end=" ", flush=True)
    rows = []
    used_names = set()
    while len(rows) < NUM_COURSES:
        name = f"{random.choice(COURSE_PREFIXES)} {random.choice(COURSE_SUBJECTS)}"
        # Append a number if we get a duplicate
        if name in used_names:
            name = f"{name} {random.randint(1, 99)}"
        if name not in used_names:
            used_names.add(name)
            rows.append((name, random.choice(DEPARTMENTS)))
    sql = "INSERT INTO Course (course_name, department) VALUES (%s, %s)"
    for i in range(0, len(rows), BATCH_SIZE):
        cursor.executemany(sql, rows[i : i + BATCH_SIZE])
    print("done.")


def seed_enrollments(cursor):
    """Generate and insert Enrollment rows."""
    print(f"  Seeding {NUM_ENROLLMENTS:,} enrollments ...", end=" ", flush=True)
    rows = []
    for _ in range(NUM_ENROLLMENTS):
        rows.append((
            random.randint(1, NUM_STUDENTS),
            random.randint(1, NUM_COURSES),
            round(random.uniform(0, 100), 2),
            random.choice(SEMESTERS),
        ))
    sql = ("INSERT INTO Enrollment (student_id, course_id, marks, semester) "
           "VALUES (%s, %s, %s, %s)")
    for i in range(0, len(rows), BATCH_SIZE):
        cursor.executemany(sql, rows[i : i + BATCH_SIZE])
    print("done.")


def seed_attendance(cursor):
    """Generate and insert Attendance rows."""
    print(f"  Seeding {NUM_ATTENDANCE:,} attendance records ...", end=" ", flush=True)
    rows = []
    for _ in range(NUM_ATTENDANCE):
        rows.append((
            random.randint(1, NUM_STUDENTS),
            random.randint(1, NUM_COURSES),
            round(random.uniform(0, 100), 2),
        ))
    sql = ("INSERT INTO Attendance (student_id, course_id, percentage) "
           "VALUES (%s, %s, %s)")
    for i in range(0, len(rows), BATCH_SIZE):
        cursor.executemany(sql, rows[i : i + BATCH_SIZE])
    print("done.")


def verify_counts(cursor):
    """Print row counts for all four tables."""
    print("\n  Row counts:")
    for table in ("Student", "Course", "Enrollment", "Attendance"):
        cursor.execute(f"SELECT COUNT(*) FROM {table};")
        count = cursor.fetchone()[0]
        print(f"    {table:15s} -> {count:>10,}")


def main():
    random.seed(SEED)
    fake = Faker()
    Faker.seed(SEED)

    conn = get_connection()
    cursor = conn.cursor()

    print("=" * 50)
    print("Automatic Index Recommendation — Data Seeder")
    print("=" * 50)

    truncate_tables(cursor)
    conn.commit()

    seed_students(cursor, fake)
    conn.commit()

    seed_courses(cursor, fake)
    conn.commit()

    seed_enrollments(cursor)
    conn.commit()

    seed_attendance(cursor)
    conn.commit()

    verify_counts(cursor)

    cursor.close()
    conn.close()
    print("\n[OK] Seeding complete.")


if __name__ == "__main__":
    main()
