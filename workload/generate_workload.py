"""
Automatic Index Recommendation — Workload Generator
====================================================
Reads workload/queries.sql, extracts individual SQL queries and their
category tags, assigns realistic per-category frequencies, and writes
workload/workload.csv.

Usage:
    python workload/generate_workload.py

Output:
    workload/workload.csv  (columns: query_id, query, frequency)
"""

import csv
import os
import random
import re

SEED = 42

# Frequency ranges per category (min, max)
FREQUENCY_RANGES = {
    "HIGH_FREQ":    (100, 200),
    "SIMPLE_WHERE": (60, 90),
    "COMPOSITE":    (50, 75),
    "JOIN":         (40, 70),
    "JOIN_GROUPBY": (20, 40),
    "ORDERBY":      (20, 40),
    "GROUPBY":      (15, 35),
    "LOW_FREQ":     (3, 10),
}

# Regex to extract the category tag from a comment like "-- [HIGH_FREQ] description"
CATEGORY_RE = re.compile(r"--\s*\[(\w+)\]\s*(.+)")


def parse_queries(sql_path: str) -> list[dict]:
    """
    Parse queries.sql and return a list of dicts with keys:
      - query: the SQL string (single line, trimmed)
      - category: the tag from the preceding comment
    """
    with open(sql_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    queries = []
    current_category = None

    for line in lines:
        stripped = line.strip()

        # Check for category tag comment
        match = CATEGORY_RE.match(stripped)
        if match:
            current_category = match.group(1)
            continue

        # Skip blank lines and non-tagged comments
        if not stripped or stripped.startswith("--"):
            continue

        # This line is a SQL statement (may span one line)
        if stripped.endswith(";"):
            queries.append({
                "query": stripped,
                "category": current_category or "LOW_FREQ",
            })
            current_category = None  # Reset so next query needs its own tag

    return queries


def assign_frequencies(queries: list[dict]) -> list[dict]:
    """Assign a frequency to each query based on its category."""
    random.seed(SEED)

    result = []
    for i, q in enumerate(queries, start=1):
        cat = q["category"]
        lo, hi = FREQUENCY_RANGES.get(cat, (10, 30))
        freq = random.randint(lo, hi)
        result.append({
            "query_id": i,
            "query": q["query"],
            "frequency": freq,
        })
    return result


def write_csv(workload: list[dict], csv_path: str):
    """Write the workload to a CSV file."""
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["query_id", "query", "frequency"])
        writer.writeheader()
        writer.writerows(workload)


def main():
    # Resolve paths relative to this script's location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sql_path = os.path.join(script_dir, "queries.sql")
    csv_path = os.path.join(script_dir, "workload.csv")

    queries = parse_queries(sql_path)
    print(f"Parsed {len(queries)} queries from queries.sql")

    workload = assign_frequencies(queries)

    write_csv(workload, csv_path)
    print(f"Wrote {len(workload)} rows to {csv_path}")

    # Summary by category
    print("\nFrequency summary:")
    from collections import Counter
    cats = Counter()
    for q in queries:
        cats[q["category"]] += 1
    for cat, count in sorted(cats.items()):
        lo, hi = FREQUENCY_RANGES.get(cat, (10, 30))
        print(f"  {cat:15s} -> {count:2d} queries  (freq range {lo}-{hi})")


if __name__ == "__main__":
    main()
