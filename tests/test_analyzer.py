"""
Unit and Integration Test Suite for Person 2 — SQL / Workload Analyzer
=====================================================================
Validates all query parsing capabilities, contract compliance, error handling,
and workload summary generation according to project specifications.
"""

import json
import os
import tempfile
import unittest

from analyzer.analyze import (
    analyze_workload,
    compute_workload_summary,
    parse_query,
    write_json_safely,
)


class TestWorkloadAnalyzer(unittest.TestCase):

    # ---------------------------------------------------------
    # Required Core Tests (Tests 1 through 10)
    # ---------------------------------------------------------

    def test_01_simple_where(self):
        """Test 1 — Simple WHERE clause extraction."""
        sql = "SELECT * FROM Student WHERE department='Computer Science';"
        res = parse_query(sql, query_id=1, frequency=100)
        self.assertEqual(res["table"], "Student")
        self.assertEqual(res["where_columns"], ["department"])

    def test_02_multiple_where(self):
        """Test 2 — Multiple WHERE columns with AND."""
        sql = "SELECT * FROM Student WHERE department='Computer Science' AND city='Pune';"
        res = parse_query(sql, query_id=2, frequency=70)
        self.assertEqual(res["table"], "Student")
        self.assertEqual(res["where_columns"], ["department", "city"])

    def test_03_join(self):
        """Test 3 — JOIN clause extraction."""
        sql = "SELECT * FROM Student s JOIN Enrollment e ON s.student_id=e.student_id;"
        res = parse_query(sql, query_id=3, frequency=50)
        self.assertEqual(res["table"], "Student")
        self.assertEqual(res["join_columns"], ["student_id"])

    def test_04_order_by(self):
        """Test 4 — ORDER BY with direction (DESC)."""
        sql = "SELECT * FROM Student ORDER BY name DESC;"
        res = parse_query(sql, query_id=4, frequency=30)
        self.assertEqual(res["table"], "Student")
        self.assertEqual(res["order_columns"], ["name"])

    def test_05_group_by(self):
        """Test 5 — GROUP BY clause extraction."""
        sql = "SELECT department, COUNT(*) FROM Student GROUP BY department;"
        res = parse_query(sql, query_id=5, frequency=25)
        self.assertEqual(res["table"], "Student")
        self.assertEqual(res["group_columns"], ["department"])

    def test_06_combined_query(self):
        """Test 6 — Combined query: JOIN + WHERE + GROUP BY + ORDER BY."""
        sql = (
            "SELECT s.department, AVG(e.marks) AS avg_marks "
            "FROM Student s "
            "JOIN Enrollment e ON s.student_id = e.student_id "
            "WHERE s.city = 'Pune' "
            "GROUP BY s.department "
            "ORDER BY s.department ASC;"
        )
        res = parse_query(sql, query_id=6, frequency=45)
        self.assertEqual(res["table"], "Student")
        self.assertEqual(res["join_columns"], ["student_id"])
        self.assertEqual(res["where_columns"], ["city"])
        self.assertEqual(res["group_columns"], ["department"])
        self.assertEqual(res["order_columns"], ["department"])

    def test_07_frequency_preservation(self):
        """Test 7 — Verify frequency remains a positive integer."""
        sql = "SELECT * FROM Course WHERE course_id = 10;"
        res = parse_query(sql, query_id=7, frequency=100)
        self.assertIsInstance(res["frequency"], int)
        self.assertEqual(res["frequency"], 100)

    def test_08_duplicate_columns(self):
        """Test 8 — Verify duplicate column references are removed within categories."""
        sql = (
            "SELECT * FROM Student "
            "WHERE department = 'CS' OR department = 'IT' OR department = 'Math' "
            "ORDER BY department ASC, department DESC;"
        )
        res = parse_query(sql, query_id=8, frequency=20)
        self.assertEqual(res["where_columns"], ["department"])
        self.assertEqual(res["order_columns"], ["department"])

    def test_09_malformed_sql(self):
        """Test 9 — Verify the analyzer handles invalid SQL safely without crashing."""
        malformed = "SELECT FROM WHERE ;; INVALID SYNTAX %%"
        res = parse_query(malformed, query_id=999, frequency=10)
        self.assertEqual(res["query_id"], 999)
        self.assertEqual(res["query"], malformed)
        self.assertEqual(res["table"], "UNKNOWN")
        self.assertEqual(res["where_columns"], [])
        self.assertEqual(res["join_columns"], [])
        self.assertEqual(res["order_columns"], [])
        self.assertEqual(res["group_columns"], [])
        self.assertEqual(res["frequency"], 10)

    def test_10_output_contract(self):
        """Test 10 — Verify every successful result contains all 8 mandatory fields."""
        required_fields = {
            "query_id",
            "query",
            "table",
            "where_columns",
            "join_columns",
            "order_columns",
            "group_columns",
            "frequency",
        }
        sql = "SELECT * FROM Student WHERE city = 'Mumbai';"
        res = parse_query(sql, query_id=10, frequency=60)
        self.assertEqual(set(res.keys()), required_fields)
        self.assertIsInstance(res["query_id"], int)
        self.assertIsInstance(res["query"], str)
        self.assertIsInstance(res["table"], str)
        self.assertIsInstance(res["where_columns"], list)
        self.assertIsInstance(res["join_columns"], list)
        self.assertIsInstance(res["order_columns"], list)
        self.assertIsInstance(res["group_columns"], list)
        self.assertIsInstance(res["frequency"], int)

    # ---------------------------------------------------------
    # Additional Pattern & Edge Case Tests
    # ---------------------------------------------------------

    def test_where_parentheses_or(self):
        sql = "SELECT * FROM Student WHERE department = 'Physics' AND (city = 'Delhi' OR city = 'Bangalore');"
        res = parse_query(sql, query_id=11, frequency=50)
        self.assertEqual(res["where_columns"], ["department", "city"])

    def test_where_does_not_return_literal_values(self):
        sql = "SELECT * FROM Student WHERE department = 'Computer Science' AND city = 'Pune' AND year = 3 AND marks > 100;"
        res = parse_query(sql, query_id=12, frequency=10)
        self.assertEqual(res["where_columns"], ["department", "city", "year", "marks"])
        for val in ["computer science", "pune", "3", "100", 3, 100]:
            self.assertNotIn(val, res["where_columns"])

    def test_multi_table_join(self):
        sql = (
            "SELECT s.name, c.course_name, e.marks FROM Student s "
            "JOIN Enrollment e ON s.student_id = e.student_id "
            "JOIN Course c ON e.course_id = c.course_id;"
        )
        res = parse_query(sql, query_id=13, frequency=35)
        self.assertEqual(res["table"], "Student")
        self.assertEqual(res["join_columns"], ["student_id", "course_id"])

    def test_join_using(self):
        sql = "SELECT * FROM Student s JOIN Enrollment e USING (student_id);"
        res = parse_query(sql, query_id=14, frequency=30)
        self.assertEqual(res["join_columns"], ["student_id"])

    def test_multiple_order_by(self):
        sql = "SELECT * FROM Student ORDER BY department ASC, name DESC;"
        res = parse_query(sql, query_id=15, frequency=20)
        self.assertEqual(res["order_columns"], ["department", "name"])

    # ---------------------------------------------------------
    # Robustness & Input Validation Tests
    # ---------------------------------------------------------

    def test_missing_workload_file(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            analyze_workload("nonexistent_path/workload.csv")
        self.assertIn("not found", str(ctx.exception).lower())

    def test_missing_csv_columns(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("id,sql_text\n1,SELECT * FROM Student;\n")
            temp_path = f.name

        try:
            with self.assertRaises(ValueError) as ctx:
                analyze_workload(temp_path)
            self.assertIn("missing required column", str(ctx.exception).lower())
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_empty_csv(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_path = f.name

        try:
            with self.assertRaises(ValueError) as ctx:
                analyze_workload(temp_path)
            self.assertIn("empty", str(ctx.exception).lower())
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_empty_sql_skips_row(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("query_id,query,frequency\n1,,10\n2,SELECT * FROM Student;,20\n")
            temp_path = f.name

        out_path = temp_path + ".json"
        try:
            queries, _ = analyze_workload(temp_path, output_path=out_path, summary_path=None)
            self.assertEqual(len(queries), 1)
            self.assertEqual(queries[0]["query_id"], 2)
        finally:
            for p in [temp_path, out_path]:
                if os.path.exists(p):
                    os.remove(p)

    def test_invalid_frequency_defaults_to_one(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("query_id,query,frequency\n1,SELECT * FROM Student;,invalid\n2,SELECT * FROM Course;,-10\n")
            temp_path = f.name

        out_path = temp_path + ".json"
        try:
            queries, _ = analyze_workload(temp_path, output_path=out_path, summary_path=None)
            self.assertEqual(queries[0]["frequency"], 1)
            self.assertEqual(queries[1]["frequency"], 1)
        finally:
            for p in [temp_path, out_path]:
                if os.path.exists(p):
                    os.remove(p)

    def test_duplicate_query_ids(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("query_id,query,frequency\n1,SELECT * FROM Student;,10\n1,SELECT * FROM Course;,20\n")
            temp_path = f.name

        out_path = temp_path + ".json"
        try:
            queries, _ = analyze_workload(temp_path, output_path=out_path, summary_path=None)
            self.assertEqual(len(queries), 2)
        finally:
            for p in [temp_path, out_path]:
                if os.path.exists(p):
                    os.remove(p)

    def test_invalid_output_path(self):
        invalid_path = "Z:\\nonexistent_volume_root\\path.json" if os.name == "nt" else "/dev/null/impossible/path.json"
        with self.assertRaises(OSError) as ctx:
            write_json_safely({"test": 1}, invalid_path)
        self.assertIn("Unable to write", str(ctx.exception))

    # ---------------------------------------------------------
    # Workload Summary Computation Test
    # ---------------------------------------------------------

    def test_workload_summary(self):
        mock_queries = [
            {
                "query_id": 1,
                "query": "SELECT * FROM Student WHERE department = 'CS';",
                "table": "Student",
                "where_columns": ["department"],
                "join_columns": [],
                "order_columns": [],
                "group_columns": [],
                "frequency": 100,
            }
        ]
        summary = compute_workload_summary(mock_queries)
        self.assertEqual(summary["total_queries"], 1)
        self.assertEqual(summary["total_frequency"], 100)
        self.assertEqual(summary["unique_tables"], 1)
        self.assertEqual(summary["tables"], ["Student"])
        self.assertEqual(summary["most_used_where_columns"][0]["column"], "department")
        self.assertEqual(summary["most_used_where_columns"][0]["usage_count"], 1)

    # ---------------------------------------------------------
    # Full Integration Test with Actual Repository Workload
    # ---------------------------------------------------------

    def test_integration_actual_workload(self):
        """Integration test on actual repository workload using default paths."""
        csv_path = "workload/workload.csv"
        out_path = "data/analyzed_workload.json"
        summary_path = "data/workload_summary.json"

        queries, summary = analyze_workload(csv_path, out_path, summary_path)

        # 1. Check all 43 queries analyzed
        self.assertEqual(len(queries), 43)

        # 2. Check JSON files are valid and exist on disk
        self.assertTrue(os.path.exists(out_path))
        self.assertTrue(os.path.exists(summary_path))

        with open(out_path, "r", encoding="utf-8") as f:
            loaded_queries = json.load(f)
        self.assertEqual(len(loaded_queries), 43)

        required_fields = {
            "query_id", "query", "table", "where_columns",
            "join_columns", "order_columns", "group_columns", "frequency"
        }
        for q in loaded_queries:
            self.assertEqual(set(q.keys()), required_fields)
            self.assertIsInstance(q["query_id"], int)
            self.assertIsInstance(q["query"], str)
            self.assertIsInstance(q["table"], str)
            self.assertIsInstance(q["where_columns"], list)
            self.assertIsInstance(q["join_columns"], list)
            self.assertIsInstance(q["order_columns"], list)
            self.assertIsInstance(q["group_columns"], list)
            self.assertIsInstance(q["frequency"], int)
            self.assertGreater(q["frequency"], 0)
            self.assertNotEqual(q["table"], "UNKNOWN")

            # Check no duplicates
            for col_list in [q["where_columns"], q["join_columns"], q["order_columns"], q["group_columns"]]:
                self.assertEqual(len(col_list), len(set(col_list)))


if __name__ == "__main__":
    unittest.main()
