"""
Automatic Index Recommendation — Unified Recommender Runner (Person 3)
====================================================================
Runs both rule-based candidate index generation and ML-based recommendation.
Outputs:
  - data/recommendations.json      (Rule-based candidate recommendations)
  - data/ml_recommendations.json   (Random Forest ML-evaluated recommendations)
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from recommendation.candidate_generator import (
    load_workload,
    generate_and_score_candidates,
    save_recommendations,
)
from recommendation.ml_recommender import generate_ml_recommendations


def run_recommendations(
    analyzed_path: str = "data/analyzed_workload.json",
    rules_out: str = "data/recommendations.json",
    ml_out: str = "data/ml_recommendations.json",
    model_path: str = "models/rf_model.pkl",
):
    print("[*] Loading analyzed workload data from:", analyzed_path)
    workload = load_workload(analyzed_path)

    print("[*] Generating Rule-Based Candidate Index Recommendations...")
    rule_recs = generate_and_score_candidates(workload)
    save_recommendations(rule_recs, rules_out)

    print("[*] Generating ML-Based Index Recommendations...")
    ml_recs = generate_ml_recommendations(workload, model_path)
    save_recommendations(ml_recs, ml_out)

    print("[OK] Index recommendation stage complete.")


if __name__ == "__main__":
    run_recommendations()
