"""
Unit and Integration Test Suite for Person 3 — Index Recommendation Engine & Budget Optimizer
=============================================================================================
Validates:
  1. Candidate index generation with selectivity-aware scoring and B-Tree prefix ordering.
  2. Composite candidate generation following [JOIN] -> [Equality] -> [Range] -> [ORDER BY].
  3. Prefix redundancy elimination (dropping single-column indexes subsumed by composites).
  4. Index count and storage budget optimization.
  5. Executable MySQL SQL generation (apply_indexes.sql and rollback_indexes.sql).
  6. Grounded ML model training, feature extraction, and inference.
  7. End-to-end integration across workload -> analyzer -> candidate generator -> budget optimizer.
"""

import json
import os
import tempfile
import unittest

from analyzer.analyze import analyze_workload
from models.train_model import FEATURE_NAMES, simulate_realistic_dbms_dataset, train_and_save_model
from recommendation.budget_optimizer import (
    clean_index_name,
    generate_sql_scripts,
    is_prefix_redundant,
    optimize_index_selection,
    run_budget_optimizer,
)
from recommendation.candidate_generator import (
    WEIGHTS,
    build_composite_candidate,
    calculate_candidate_score,
    generate_and_score_candidates,
    load_workload,
    save_recommendations,
)
from recommendation.catalog import catalog
from recommendation.ml_recommender import (
    extract_features,
    generate_ml_recommendations,
)


class TestRecommendationPipeline(unittest.TestCase):

    def setUp(self):
        self.mock_workload = [
            {
                "query_id": 1,
                "table": "Student",
                "where_columns": ["department", "city"],
                "join_columns": [],
                "order_columns": [],
                "group_columns": [],
                "frequency": 100,
                "query": "SELECT * FROM Student WHERE department = 'Computer Science' AND city = 'Pune';",
            },
            {
                "query_id": 2,
                "table": "Enrollment",
                "where_columns": [],
                "join_columns": ["student_id"],
                "order_columns": [],
                "group_columns": [],
                "frequency": 40,
                "query": "SELECT * FROM Enrollment JOIN Student USING (student_id);",
            },
            {
                "query_id": 3,
                "table": "Attendance",
                "where_columns": ["course_id"],
                "join_columns": ["student_id"],
                "order_columns": ["percentage"],
                "group_columns": [],
                "frequency": 50,
                "query": "SELECT * FROM Attendance WHERE course_id = 10 AND student_id = 42 ORDER BY percentage;",
            },
            {
                "query_id": 99,
                "table": "UNKNOWN",
                "where_columns": ["col_unknown"],
                "join_columns": [],
                "order_columns": [],
                "group_columns": [],
                "frequency": 100,
                "query": "SELECT * FROM UNKNOWN WHERE col_unknown = 1;",
            },
        ]

    def test_01_candidate_generation_and_selectivity_scoring(self):
        """Verify candidate generation produces single-col and composite candidates with selectivity."""
        recs = generate_and_score_candidates(self.mock_workload)

        # Query 1 produces single-column candidates ('department', 'city') AND composite candidate ['department', 'city']
        q1_recs = [r for r in recs if r["query_id"] == 1]
        self.assertGreaterEqual(len(q1_recs), 2)

        # Verify department recommendation
        dept_rec = next(r for r in q1_recs if r["columns"] == ["department"])
        self.assertEqual(dept_rec["table"], "Student")
        self.assertGreater(dept_rec["score"], 0)
        self.assertIn("selectivity", dept_rec)
        self.assertLess(dept_rec["selectivity"], 1.0)

        # Verify composite candidate for Query 1
        comp_rec = next((r for r in q1_recs if r["columns"] == ["department", "city"]), None)
        self.assertIsNotNone(comp_rec)
        self.assertTrue(comp_rec["is_composite"])

        # Query 2 produces join candidate on student_id
        q2_recs = [r for r in recs if r["query_id"] == 2]
        self.assertEqual(len(q2_recs), 1)
        self.assertEqual(q2_recs[0]["columns"], ["student_id"])
        self.assertEqual(q2_recs[0]["table"], "Enrollment")

    def test_02_skips_unknown_table(self):
        """Verify queries with table UNKNOWN or empty are ignored."""
        recs = generate_and_score_candidates(self.mock_workload)
        unknown_recs = [r for r in recs if r["table"] == "UNKNOWN"]
        self.assertEqual(len(unknown_recs), 0)

    def test_03_recommendation_contract(self):
        """Verify candidate recommendations adhere to expected structure contract."""
        recs = generate_and_score_candidates(self.mock_workload)
        self.assertGreater(len(recs), 0)
        expected_keys = {"query_id", "table", "columns", "score", "reason", "query", "selectivity", "estimated_size_mb", "is_composite"}
        for r in recs:
            for k in expected_keys:
                self.assertIn(k, r, f"Missing key {k} in recommendation")
            self.assertIsInstance(r["query_id"], int)
            self.assertIsInstance(r["query"], str)
            self.assertIsInstance(r["table"], str)
            self.assertIsInstance(r["columns"], list)
            self.assertIsInstance(r["score"], (int, float))
            self.assertIsInstance(r["reason"], str)
            self.assertIsInstance(r["estimated_size_mb"], float)

    def test_04_save_and_load_recommendations(self):
        """Verify save_recommendations writes valid JSON that reloads cleanly."""
        recs = generate_and_score_candidates(self.mock_workload)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            save_recommendations(recs, temp_path)
            loaded = load_workload(temp_path)
            self.assertEqual(len(loaded), len(recs))
            self.assertEqual(loaded[0]["query_id"], recs[0]["query_id"])
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_05_ml_feature_extraction(self):
        """Verify feature extraction for ML model input includes both grounded and legacy fields."""
        q = {
            "query_id": 1,
            "frequency": 80,
            "where_columns": ["department"],
            "join_columns": ["student_id"],
            "order_columns": [],
            "query": "SELECT * FROM Student WHERE department = 'CS';",
        }
        f_dept = extract_features(q, "department", "Student")
        self.assertEqual(f_dept["frequency"], 80)
        self.assertEqual(f_dept["is_where"], 1)
        self.assertEqual(f_dept["is_equality"], 1)
        self.assertEqual(f_dept["is_join"], 0)
        self.assertEqual(f_dept["is_order"], 0)
        self.assertIn("selectivity", f_dept)
        self.assertIn("table_size_log", f_dept)

        f_join = extract_features(q, "student_id", "Student")
        self.assertEqual(f_join["is_where"], 0)
        self.assertEqual(f_join["is_join"], 1)

    def test_06_ml_grounded_training_and_recommendations(self):
        """Verify grounded ML model training and inference generation."""
        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            temp_model_path = f.name

        try:
            clf = train_and_save_model(temp_model_path, num_samples=300)
            self.assertTrue(os.path.exists(temp_model_path))

            ml_recs = generate_ml_recommendations(self.mock_workload, temp_model_path, confidence_threshold=0.50)
            self.assertIsInstance(ml_recs, list)
            self.assertGreater(len(ml_recs), 0)

            required_keys = {"query_id", "table", "columns", "confidence_score", "reason", "query"}
            for r in ml_recs:
                for k in required_keys:
                    self.assertIn(k, r)
                self.assertIsInstance(r["query"], str)
                self.assertGreater(r["confidence_score"], 45.0)
                self.assertNotEqual(r["table"], "UNKNOWN")
        finally:
            if os.path.exists(temp_model_path):
                os.remove(temp_model_path)

    def test_07_composite_btree_ordering_rule(self):
        """
        Verify B-Tree prefix ordering rule:
          [JOIN columns] -> [Equality WHERE columns] -> [Range WHERE column] -> [ORDER BY column]
        """
        table = "Student"
        join_cols = ["student_id"]
        eq_cols = ["department", "city"]
        rng_cols = ["year"]
        order_cols = ["name"]

        comp = build_composite_candidate(
            table=table,
            join_cols=join_cols,
            equality_cols=eq_cols,
            range_cols=rng_cols,
            order_cols=order_cols,
            max_cols=3,
        )
        self.assertEqual(comp, ["student_id", "department", "city"])

        comp2 = build_composite_candidate(
            table=table,
            join_cols=[],
            equality_cols=["department"],
            range_cols=["year"],
            order_cols=["city"],
            max_cols=3,
        )
        self.assertEqual(comp2, ["department", "year", "city"])

    def test_08_prefix_redundancy_elimination(self):
        """Verify that shorter prefix indexes are pruned when a composite index exists."""
        self.assertTrue(is_prefix_redundant(["department"], ["department", "city"]))
        self.assertTrue(is_prefix_redundant(["department", "city"], ["department", "city", "year"]))
        self.assertFalse(is_prefix_redundant(["city"], ["department", "city"]))
        self.assertFalse(is_prefix_redundant(["department", "city"], ["department"]))

        candidates = [
            {
                "query_id": 1,
                "table": "Student",
                "columns": ["department", "city"],
                "score": 150.0,
                "estimated_size_mb": 0.5,
            },
            {
                "query_id": 2,
                "table": "Student",
                "columns": ["department"],
                "score": 100.0,
                "estimated_size_mb": 0.3,
            },
        ]
        selected, pruned = optimize_index_selection(candidates, max_indexes=5, max_storage_mb=10.0)
        selected_cols = [s["columns"] for s in selected]

        self.assertIn(["department", "city"], selected_cols)
        self.assertNotIn(["department"], selected_cols)
        self.assertEqual(len(pruned), 1)
        self.assertIn("Prefix redundant", pruned[0]["prune_reason"])

    def test_09_budget_optimizer_limits(self):
        """Verify strict enforcement of max_indexes and max_storage_mb."""
        candidates = [
            {"table": "Student", "columns": [f"col_{i}"], "score": 100 - i, "estimated_size_mb": 5.0}
            for i in range(10)
        ]
        selected, pruned = optimize_index_selection(candidates, max_indexes=3, max_storage_mb=50.0)
        self.assertEqual(len(selected), 3)
        self.assertEqual(len(pruned), 7)

        selected_storage, pruned_storage = optimize_index_selection(candidates, max_indexes=10, max_storage_mb=12.0)
        self.assertEqual(len(selected_storage), 2)
        total_size = sum(s["estimated_size_mb"] for s in selected_storage)
        self.assertLessEqual(total_size, 12.0)

    def test_10_sql_script_generation(self):
        """Verify generation of valid apply_indexes.sql and rollback_indexes.sql."""
        test_indexes = [
            {"table": "Student", "columns": ["department", "city"], "index_name": "idx_student_dept_city"},
            {"table": "Enrollment", "columns": ["student_id"], "index_name": "idx_enrollment_student_id"},
        ]
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as f_apply:
            apply_path = f_apply.name
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as f_rollback:
            rollback_path = f_rollback.name

        try:
            generate_sql_scripts(test_indexes, apply_path=apply_path, rollback_path=rollback_path)

            with open(apply_path, "r", encoding="utf-8") as f:
                apply_content = f.read()
            with open(rollback_path, "r", encoding="utf-8") as f:
                rollback_content = f.read()

            self.assertIn("CREATE INDEX `idx_student_dept_city` ON `Student`(`department`, `city`);", apply_content)
            self.assertIn("CREATE INDEX `idx_enrollment_student_id` ON `Enrollment`(`student_id`);", apply_content)
            self.assertIn("DROP INDEX `idx_student_dept_city` ON `Student`;", rollback_content)
            self.assertIn("DROP INDEX `idx_enrollment_student_id` ON `Enrollment`;", rollback_content)
        finally:
            for p in [apply_path, rollback_path]:
                if os.path.exists(p):
                    os.remove(p)

    def test_11_end_to_end_pipeline(self):
        """
        Verify full pipeline:
        workload.csv -> Person 2 analyzer -> candidate generator -> budget optimizer -> SQL scripts.
        """
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f_analyzed:
            analyzed_path = f_analyzed.name
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f_summary:
            summary_path = f_summary.name
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f_recs:
            recs_path = f_recs.name
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as f_apply:
            apply_path = f_apply.name
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as f_rollback:
            rollback_path = f_rollback.name

        try:
            analyzed_queries, summary = analyze_workload(
                csv_path="workload/workload.csv",
                output_path=analyzed_path,
                summary_path=summary_path,
            )
            self.assertEqual(len(analyzed_queries), 43)

            workload_data = load_workload(analyzed_path)
            raw_recs = generate_and_score_candidates(workload_data)
            self.assertGreater(len(raw_recs), 0)
            save_recommendations(raw_recs, recs_path)

            optimized = run_budget_optimizer(
                input_path=recs_path,
                output_path=recs_path,
                apply_sql_path=apply_path,
                rollback_sql_path=rollback_path,
                max_indexes=8,
                max_storage_mb=25.0,
            )
            self.assertLessEqual(len(optimized), 8)
            self.assertTrue(os.path.exists(apply_path))
            self.assertTrue(os.path.exists(rollback_path))

        finally:
            for p in [analyzed_path, summary_path, recs_path, apply_path, rollback_path]:
                if os.path.exists(p):
                    os.remove(p)


if __name__ == "__main__":
    unittest.main()
