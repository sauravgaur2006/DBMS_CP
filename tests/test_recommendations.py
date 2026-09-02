"""
Unit and Integration Test Suite for Person 3 — Index Recommendation + ML
========================================================================
Validates candidate index generation, ML-based recommendation scoring,
output structure compliance, resilience against edge cases, and end-to-end
pipeline integration from Person 1 (workload) -> Person 2 (analyzer) -> Person 3 (recommender).
"""

import json
import os
import tempfile
import unittest

from analyzer.analyze import analyze_workload
from models.train_model import generate_synthetic_data, train_and_save_model
from recommendation.candidate_generator import (
    WEIGHTS,
    generate_and_score_candidates,
    load_workload,
    save_recommendations,
)
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
            },
            {
                "query_id": 2,
                "table": "Enrollment",
                "where_columns": [],
                "join_columns": ["student_id"],
                "order_columns": [],
                "group_columns": [],
                "frequency": 40,
            },
            {
                "query_id": 3,
                "table": "Attendance",
                "where_columns": ["course_id"],
                "join_columns": ["student_id"],
                "order_columns": ["percentage"],
                "group_columns": [],
                "frequency": 50,
            },
            {
                "query_id": 99,
                "table": "UNKNOWN",
                "where_columns": ["col_unknown"],
                "join_columns": [],
                "order_columns": [],
                "group_columns": [],
                "frequency": 100,
            },
        ]

    def test_01_weights_and_scoring(self):
        """Verify rule-based candidate scoring matches formula and weights."""
        recs = generate_and_score_candidates(self.mock_workload)
        
        # Query 1: freq=100, where_columns=['department', 'city']
        # score = 100 * 1.0 = 100.0 each
        q1_recs = [r for r in recs if r["query_id"] == 1]
        self.assertEqual(len(q1_recs), 2)
        dept_rec = next(r for r in q1_recs if r["columns"] == ["department"])
        self.assertEqual(dept_rec["score"], 100.0 * WEIGHTS["where"])
        self.assertEqual(dept_rec["table"], "Student")

        # Query 2: freq=40, join_columns=['student_id']
        # score = 40 * 1.5 = 60.0
        q2_recs = [r for r in recs if r["query_id"] == 2]
        self.assertEqual(len(q2_recs), 1)
        self.assertEqual(q2_recs[0]["columns"], ["student_id"])
        self.assertEqual(q2_recs[0]["score"], 40.0 * WEIGHTS["join"])

        # Query 3: freq=50, order_columns=['percentage'] -> score = 50 * 0.5 = 25.0 (> 20 threshold)
        q3_recs = [r for r in recs if r["query_id"] == 3]
        order_rec = next((r for r in q3_recs if r["columns"] == ["percentage"]), None)
        self.assertIsNotNone(order_rec)
        self.assertEqual(order_rec["score"], 50.0 * WEIGHTS["order"])

    def test_02_skips_unknown_table(self):
        """Verify queries with table UNKNOWN or empty are ignored."""
        recs = generate_and_score_candidates(self.mock_workload)
        unknown_recs = [r for r in recs if r["table"] == "UNKNOWN"]
        self.assertEqual(len(unknown_recs), 0)

    def test_03_recommendation_contract(self):
        """Verify candidate recommendations adhere to expected structure."""
        recs = generate_and_score_candidates(self.mock_workload)
        self.assertGreater(len(recs), 0)
        required_keys = {"query_id", "table", "columns", "score", "reason", "query"}
        for r in recs:
            self.assertEqual(set(r.keys()), required_keys)
            self.assertIsInstance(r["query_id"], int)
            self.assertIsInstance(r["query"], str)
            self.assertIsInstance(r["table"], str)
            self.assertIsInstance(r["columns"], list)
            self.assertIsInstance(r["score"], (int, float))
            self.assertIsInstance(r["reason"], str)

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
        """Verify feature extraction for ML model input."""
        q = {
            "query_id": 1,
            "frequency": 80,
            "where_columns": ["department"],
            "join_columns": ["student_id"],
            "order_columns": [],
        }
        f_dept = extract_features(q, "department")
        self.assertEqual(f_dept["frequency"], 80)
        self.assertEqual(f_dept["is_where"], 1)
        self.assertEqual(f_dept["is_join"], 0)
        self.assertEqual(f_dept["is_order"], 0)

        f_join = extract_features(q, "student_id")
        self.assertEqual(f_join["is_where"], 0)
        self.assertEqual(f_join["is_join"], 1)

    def test_06_ml_synthetic_training_and_recommendations(self):
        """Verify ML model training and inference generation."""
        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            temp_model_path = f.name

        try:
            # Verify training
            train_and_save_model(temp_model_path)
            self.assertTrue(os.path.exists(temp_model_path))

            # Verify ML recommendations
            ml_recs = generate_ml_recommendations(self.mock_workload, temp_model_path)
            self.assertIsInstance(ml_recs, list)
            self.assertGreater(len(ml_recs), 0)

            required_keys = {"query_id", "table", "columns", "confidence_score", "reason", "query"}
            for r in ml_recs:
                self.assertEqual(set(r.keys()), required_keys)
                self.assertIsInstance(r["query"], str)
                self.assertGreater(r["confidence_score"], 60.0)
                self.assertNotEqual(r["table"], "UNKNOWN")
        finally:
            if os.path.exists(temp_model_path):
                os.remove(temp_model_path)

    def test_07_end_to_end_pipeline(self):
        """
        Verify full pipeline:
        workload.csv -> Person 2 analyze_workload -> analyzed_workload.json -> Person 3 recommender.
        """
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f_analyzed:
            analyzed_path = f_analyzed.name
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f_summary:
            summary_path = f_summary.name
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f_recs:
            recs_path = f_recs.name

        try:
            # 1. Run Person 2 analyzer on actual 43 queries
            analyzed_queries, summary = analyze_workload(
                csv_path="workload/workload.csv",
                output_path=analyzed_path,
                summary_path=summary_path,
            )
            self.assertEqual(len(analyzed_queries), 43)

            # 2. Run Person 3 candidate generator
            workload_data = load_workload(analyzed_path)
            recs = generate_and_score_candidates(workload_data)
            self.assertGreater(len(recs), 0)
            save_recommendations(recs, recs_path)

            # 3. Verify recommendations file content
            loaded_recs = load_workload(recs_path)
            self.assertEqual(len(loaded_recs), len(recs))

            # Ensure recommendations cover key indexed tables
            tables_recommended = {r["table"] for r in loaded_recs}
            self.assertTrue({"Student", "Course", "Enrollment", "Attendance"}.issubset(tables_recommended))

        finally:
            for p in [analyzed_path, summary_path, recs_path]:
                if os.path.exists(p):
                    os.remove(p)


if __name__ == "__main__":
    unittest.main()
