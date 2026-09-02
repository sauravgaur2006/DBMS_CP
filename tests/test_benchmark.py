"""
Unit and Integration Test Suite for Person 4 — Benchmarking Engine & Dashboard
=============================================================================
Validates index naming, execution latency calculation formula,
storage overhead computation, benchmark output contract, DataFrame loading for
Streamlit dashboard, and end-to-end multi-role pipeline integration.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from app import load_benchmark_data
from benchmark import (
    generate_index_name,
    load_json_file,
    run_benchmark_simulated,
    save_json_file,
)


class TestBenchmarkPipeline(unittest.TestCase):

    def setUp(self):
        self.mock_recommendations = [
            {
                "query_id": 1,
                "query": "SELECT * FROM Student WHERE department = 'Computer Science';",
                "table": "Student",
                "columns": ["department"],
                "score": 181.0,
                "reason": "High frequency filter",
            },
            {
                "query_id": 2,
                "query": "SELECT * FROM Enrollment WHERE student_id = 42;",
                "table": "Enrollment",
                "columns": ["student_id"],
                "score": 114.0,
                "reason": "Foreign key join",
            },
            {
                "query_id": 3,
                "query": "SELECT * FROM Attendance WHERE student_id = 42 AND course_id = 10;",
                "table": "Attendance",
                "columns": ["student_id", "course_id"],
                "score": 135.0,
                "reason": "Composite filter",
            },
        ]

    def test_01_generate_index_name(self):
        """Verify standardized index naming format."""
        idx_single = generate_index_name("Student", ["department"])
        self.assertEqual(idx_single, "idx_Student_department")

        idx_multi = generate_index_name("Attendance", ["student_id", "course_id"])
        self.assertEqual(idx_multi, "idx_Attendance_student_id_course_id")

    def test_02_simulation_benchmark_math_and_metrics(self):
        """
        Verify that benchmark metrics calculate accurately:
        improvement = ((before - after) / before) * 100
        """
        results = run_benchmark_simulated(self.mock_recommendations)
        self.assertEqual(len(results), len(self.mock_recommendations))

        for res in results:
            before = res["before_ms"]
            after = res["after_ms"]
            pct = res["improvement_percent"]

            self.assertGreater(before, 0)
            self.assertGreater(after, 0)
            self.assertGreater(before, after)

            # Verify math
            expected_pct = round(((before - after) / before) * 100.0, 2)
            self.assertAlmostEqual(pct, expected_pct, places=1)
            self.assertGreater(res["storage_overhead_mb"], 0)

    def test_03_benchmark_output_contract(self):
        """Verify benchmark results contain all required schema fields."""
        results = run_benchmark_simulated(self.mock_recommendations)
        required_keys = {
            "query_id",
            "table",
            "columns",
            "index_name",
            "query",
            "before_ms",
            "after_ms",
            "improvement_percent",
            "storage_overhead_mb",
            "timestamp",
        }

        for res in results:
            self.assertEqual(set(res.keys()), required_keys)
            self.assertIsInstance(res["query_id"], int)
            self.assertIsInstance(res["table"], str)
            self.assertIsInstance(res["columns"], list)
            self.assertIsInstance(res["index_name"], str)
            self.assertIsInstance(res["query"], str)
            self.assertIsInstance(res["before_ms"], float)
            self.assertIsInstance(res["after_ms"], float)
            self.assertIsInstance(res["improvement_percent"], float)
            self.assertIsInstance(res["storage_overhead_mb"], float)
            self.assertIsInstance(res["timestamp"], str)

    def test_04_save_and_load_benchmark_results(self):
        """Verify saving benchmark results to disk and reading via app loader."""
        results = run_benchmark_simulated(self.mock_recommendations)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            save_json_file(results, Path(temp_path))
            df = load_benchmark_data(temp_path)
            self.assertIsNotNone(df)
            self.assertEqual(len(df), len(results))
            self.assertIn("columns_display", df.columns)
            self.assertEqual(df.loc[0, "table"], "Student")
            self.assertEqual(df.loc[0, "columns_display"], "department")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_05_four_person_pipeline_integration(self):
        """
        Verify end-to-end integration across all 4 project roles:
        Person 1 workload -> Person 2 analyzer -> Person 3 recommender -> Person 4 benchmark
        """
        # 1. Verify files exist from prior stages
        self.assertTrue(os.path.exists("workload/workload.csv"))
        self.assertTrue(os.path.exists("data/analyzed_workload.json"))
        self.assertTrue(os.path.exists("data/recommendations.json"))
        self.assertTrue(os.path.exists("data/benchmark_results.json"))

        # 2. Check loaded benchmark results
        benchmark_data = load_json_file(Path("data/benchmark_results.json"))
        self.assertGreater(len(benchmark_data), 0)

        # 3. Ensure all evaluated tables match project tables
        tables = {r["table"] for r in benchmark_data}
        self.assertTrue({"Student", "Course", "Enrollment", "Attendance"}.issubset(tables))


if __name__ == "__main__":
    unittest.main()
