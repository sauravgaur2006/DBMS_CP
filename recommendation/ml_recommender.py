"""
Machine Learning Index Recommender (Person 3)
==============================================
Infers index recommendation utility using a trained Random Forest model
grounded on realistic DBMS query execution cost features:
  [frequency, is_join, is_equality, is_range, is_order, selectivity, table_size_log]
"""

import json
import math
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import joblib
import numpy as np
import pandas as pd

from recommendation.catalog import catalog

FEATURE_NAMES = [
    "frequency",
    "is_join",
    "is_equality",
    "is_range",
    "is_order",
    "selectivity",
    "table_size_log",
]


def load_workload(filepath: str) -> List[Dict[str, Any]]:
    """Loads analyzed workload JSON file."""
    with open(filepath, "r", encoding="utf-8") as file:
        return json.load(file)


def extract_features(query: Dict[str, Any], column: str, table: Optional[str] = None) -> Dict[str, Any]:
    """
    Extracts DBMS feature vector for a column within a specific query.
    Maintains backward compatibility with legacy `is_where` field.
    """
    table_name = table or query.get("table", "Student")
    query_str = query.get("query", "").lower()
    col_lower = column.lower()

    where_cols = [c.lower() for c in query.get("where_columns", [])]
    join_cols = [c.lower() for c in query.get("join_columns", [])]
    order_cols = [c.lower() for c in query.get("order_columns", [])]

    is_eq = 0
    is_rng = 0
    if col_lower in where_cols:
        range_match = re.search(rf"\b{re.escape(col_lower)}\b\s*(\bbetween\b|\blike\b|>=|<=|>|<)", query_str)
        if range_match:
            is_rng = 1
        else:
            is_eq = 1

    if "equality_columns" in query:
        is_eq = 1 if col_lower in [c.lower() for c in query["equality_columns"]] else 0
    if "range_columns" in query:
        is_rng = 1 if col_lower in [c.lower() for c in query["range_columns"]] else 0

    is_jn = 1 if col_lower in join_cols else 0
    is_ord = 1 if col_lower in order_cols else 0
    freq = query.get("frequency", 1)

    sel = catalog.get_column_selectivity(table_name, col_lower)
    table_rows = catalog.get_table_rows(table_name)
    table_size_log = round(math.log10(max(10, table_rows)), 2)

    return {
        "frequency": freq,
        "is_join": is_jn,
        "is_equality": is_eq,
        "is_range": is_rng,
        "is_order": is_ord,
        "selectivity": round(sel, 6),
        "table_size_log": table_size_log,
        "is_where": 1 if (is_eq or is_rng or col_lower in where_cols) else 0,
    }


def find_model_path(preferred_path: str = "models/index_recommender_model.pkl") -> str:
    """Finds an existing model file or returns default path."""
    if os.path.exists(preferred_path):
        return preferred_path
    legacy_path = "models/rf_model.pkl"
    if os.path.exists(legacy_path):
        return legacy_path
    return preferred_path


def generate_ml_recommendations(
    workload: List[Dict[str, Any]],
    model_path: str = "models/index_recommender_model.pkl",
    confidence_threshold: float = 0.55
) -> List[Dict[str, Any]]:
    """
    Evaluates workload queries with the trained ML classifier to recommend beneficial indexes.
    """
    resolved_path = find_model_path(model_path)
    if not os.path.exists(resolved_path):
        print(f"Model not found at {resolved_path}. Training a new model now...")
        from models.train_model import train_and_save_model
        train_and_save_model(resolved_path)

    print(f"Loading ML Model from {resolved_path}...")
    model = joblib.load(resolved_path)
    recommendations: List[Dict[str, Any]] = []

    for query in workload:
        table = query.get("table", "UNKNOWN")
        if not table or table == "UNKNOWN":
            continue

        query_id = query.get("query_id", 0)
        query_sql = query.get("query", "")

        all_columns = sorted(list(set(
            query.get("where_columns", []) +
            query.get("join_columns", []) +
            query.get("order_columns", [])
        )))

        for col in all_columns:
            feat_dict = extract_features(query, col, table)
            feat_df = pd.DataFrame([[feat_dict[k] for k in FEATURE_NAMES]], columns=FEATURE_NAMES)

            probabilities = model.predict_proba(feat_df)[0]
            pos_idx = 1 if len(probabilities) > 1 else 0
            beneficial_prob = probabilities[pos_idx]

            if beneficial_prob >= confidence_threshold:
                conf_pct = round(float(beneficial_prob) * 100, 2)
                size_mb = catalog.estimate_index_size_mb(table, [col])
                recommendations.append({
                    "query_id": query_id,
                    "query": query_sql,
                    "table": table,
                    "columns": [col],
                    "confidence_score": conf_pct,
                    "score": round(conf_pct, 1),
                    "estimated_size_mb": size_mb,
                    "reason": f"ML Model predicted beneficial with {conf_pct}% confidence (>30% estimated cost reduction)."
                })

    return recommendations


def save_recommendations(recommendations: List[Dict[str, Any]], filepath: str) -> None:
    """Save recommendations to JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(recommendations, file, indent=2)
    print(f"Success! {len(recommendations)} ML-based index recommendations saved to {filepath}")


if __name__ == "__main__":
    input_path = "data/analyzed_workload.json"
    model_path = "models/index_recommender_model.pkl"
    output_path = "data/ml_recommendations.json"

    if os.path.exists(input_path):
        print("Loading workload data...")
        workload_data = load_workload(input_path)
        print("Generating ML-grounded candidate recommendations...")
        recs = generate_ml_recommendations(workload_data, model_path)
        save_recommendations(recs, output_path)
    else:
        print(f"Workload file {input_path} does not exist. Run analyzer first.")
