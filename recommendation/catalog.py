"""
Database Catalog & Selectivity Provider (Person 3)
===================================================
Provides table catalog statistics, column cardinalities, selectivity fractions,
and physical index storage size estimations for MySQL InnoDB B-Tree indexes.
Supports live querying against MySQL with automatic graceful fallback to
ground-truth seeded catalog distributions.
"""

import math
import os
import sys
from typing import Dict, List, Optional, Tuple

# Try loading environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Known ground-truth table statistics from database/seed.py
DEFAULT_TABLE_ROWS: Dict[str, int] = {
    "Student": 10_000,
    "Course": 500,
    "Enrollment": 50_000,
    "Attendance": 100_000,
}

# Known ground-truth column cardinalities (number of distinct values)
DEFAULT_COLUMN_CARDINALITY: Dict[str, Dict[str, int]] = {
    "Student": {
        "student_id": 10_000,
        "name": 9_800,
        "department": 10,
        "city": 15,
        "year": 4,
    },
    "Course": {
        "course_id": 500,
        "course_name": 500,
        "department": 10,
    },
    "Enrollment": {
        "enrollment_id": 50_000,
        "student_id": 10_000,
        "course_id": 500,
        "marks": 2_500,
        "semester": 6,
    },
    "Attendance": {
        "attendance_id": 100_000,
        "student_id": 10_000,
        "course_id": 500,
        "percentage": 3_000,
    },
}

# Approximate average byte widths per column for B-Tree storage estimation
DEFAULT_COLUMN_BYTES: Dict[str, Dict[str, int]] = {
    "Student": {
        "student_id": 4,
        "name": 25,
        "department": 20,
        "city": 15,
        "year": 4,
    },
    "Course": {
        "course_id": 4,
        "course_name": 30,
        "department": 20,
    },
    "Enrollment": {
        "enrollment_id": 4,
        "student_id": 4,
        "course_id": 4,
        "marks": 4,
        "semester": 12,
    },
    "Attendance": {
        "attendance_id": 4,
        "student_id": 4,
        "course_id": 4,
        "percentage": 4,
    },
}

PRIMARY_KEY_BYTES = 4  # All 4 tables use INT primary keys in schema.sql


class CatalogProvider:
    """
    Manages metadata, selectivity, and storage calculations.
    Queries live MySQL if reachable, otherwise uses calibrated catalog statistics.
    """

    def __init__(self, enable_live_db: bool = True):
        self.enable_live_db = enable_live_db
        self.live_connected = False
        self._table_rows: Dict[str, int] = dict(DEFAULT_TABLE_ROWS)
        self._column_cardinalities: Dict[str, Dict[str, int]] = {
            t: dict(cols) for t, cols in DEFAULT_COLUMN_CARDINALITY.items()
        }
        if self.enable_live_db:
            self._try_connect_mysql()

    def _try_connect_mysql(self) -> None:
        """Attempt to read live catalog stats from MySQL if credentials exist."""
        host = os.getenv("DB_HOST", "localhost")
        user = os.getenv("DB_USER", "indexrec_user")
        password = os.getenv("DB_PASSWORD", "")
        database = os.getenv("DB_NAME", "index_recommender")

        if not password and not os.path.exists(".env"):
            return

        try:
            import mysql.connector
            conn = mysql.connector.connect(
                host=host,
                user=user,
                password=password,
                database=database,
                connection_timeout=2
            )
            cursor = conn.cursor()
            
            # Fetch row counts
            for table in list(self._table_rows.keys()):
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
                    row_count = cursor.fetchone()[0]
                    if row_count > 0:
                        self._table_rows[table] = row_count
                except Exception:
                    pass

            cursor.close()
            conn.close()
            self.live_connected = True
        except Exception:
            # Fall back to calibrated defaults silently
            self.live_connected = False

    def get_table_rows(self, table: str) -> int:
        """Return table row count."""
        return self._table_rows.get(table, 10_000)

    def get_cardinality(self, table: str, column: str) -> int:
        """Return distinct value count for a column."""
        table_cards = self._column_cardinalities.get(table, {})
        return table_cards.get(column.lower(), max(1, int(self.get_table_rows(table) * 0.05)))

    def get_column_selectivity(self, table: str, column: str) -> float:
        """
        Calculate equality filter selectivity (fraction of rows returned by WHERE col = val).
        Selectivity fraction = 1.0 / Cardinality.
        A low fraction (e.g. 0.0001) means high selectivity (very few rows matched, huge index benefit).
        """
        cardinality = self.get_cardinality(table, column)
        if cardinality <= 0:
            return 1.0
        return max(1.0 / self.get_table_rows(table), 1.0 / cardinality)

    def get_composite_selectivity(self, table: str, columns: List[str]) -> float:
        """
        Calculate combined selectivity for composite index columns.
        Accounts for attribute correlation damping to prevent underflow.
        """
        if not columns:
            return 1.0
        
        sel = 1.0
        for i, col in enumerate(columns):
            col_sel = self.get_column_selectivity(table, col)
            factor = col_sel if i == 0 else math.sqrt(col_sel)
            sel *= factor

        total_rows = self.get_table_rows(table)
        return max(1.0 / total_rows, sel)

    def estimate_index_size_mb(self, table: str, columns: List[str]) -> float:
        """
        Estimate physical disk space (in MB) required by an InnoDB secondary B-Tree index.
        """
        rows = self.get_table_rows(table)
        table_col_bytes = DEFAULT_COLUMN_BYTES.get(table, {})
        
        col_bytes_sum = 0
        for col in columns:
            col_bytes_sum += table_col_bytes.get(col.lower(), 8)

        entry_size = col_bytes_sum + PRIMARY_KEY_BYTES + 12
        total_bytes = rows * entry_size * 1.33
        size_mb = total_bytes / (1024 * 1024)
        return round(size_mb, 3)


# Shared global instance
catalog = CatalogProvider()
