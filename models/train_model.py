"""
Realistic DBMS Index Benefit Machine Learning Model Trainer (Person 3)
=======================================================================
Replaces synthetic random noise with grounded DBMS cost-model feature vectors:
  Features:
    - frequency: Query execution frequency in workload
    - is_join: 1 if column is in JOIN clause (repeated nested-loop lookup)
    - is_equality: 1 if column is in equality predicate (point B-Tree seek)
    - is_range: 1 if column is in range predicate (leaf page scan)
    - is_order: 1 if column is in ORDER BY (avoids filesort)
    - selectivity: Filter factor sigma = (1.0 / cardinality). Lower is better!
    - table_size_log: log10(table_row_count)
  Target:
    - achieves_cost_reduction_gt_30pct: 1 if index reduces query cost by >30%, else 0

Trains a Random Forest classifier and exports:
  - models/index_recommender_model.pkl
  - models/rf_model.pkl (backward-compatible)
"""

import math
import os
import sys
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

FEATURE_NAMES = [
    "frequency",
    "is_join",
    "is_equality",
    "is_range",
    "is_order",
    "selectivity",
    "table_size_log",
]


def simulate_realistic_dbms_dataset(num_samples: int = 1200, seed: int = 42) -> pd.DataFrame:
    """
    Simulates training samples based on MySQL optimizer cost dynamics:
    - Joins on large tables with high cardinality have extreme index benefits (>85% cost reduction).
    - Equality filters on selective columns bypass full table scans.
    - Low-cardinality columns gain minimal benefit from B-Trees.
    - Small tables (Course: 500 rows) often cost less to scan in memory than random index seeks.
    """
    rng = np.random.RandomState(seed)

    frequencies = rng.randint(1, 250, size=num_samples)
    table_sizes = rng.choice([500, 10_000, 50_000, 100_000], size=num_samples, p=[0.1, 0.3, 0.3, 0.3])
    table_size_logs = np.log10(table_sizes)

    # Clause participation
    is_join = rng.choice([0, 1], size=num_samples, p=[0.65, 0.35])
    is_equality = rng.choice([0, 1], size=num_samples, p=[0.40, 0.60])
    is_range = np.where(is_equality == 1, rng.choice([0, 1], size=num_samples, p=[0.85, 0.15]), rng.choice([0, 1], size=num_samples, p=[0.5, 0.5]))
    is_order = rng.choice([0, 1], size=num_samples, p=[0.75, 0.25])

    cardinality_types = rng.choice(["high", "medium", "low"], size=num_samples, p=[0.4, 0.4, 0.2])
    selectivities = np.zeros(num_samples)
    for i, ctype in enumerate(cardinality_types):
        if ctype == "high":
            selectivities[i] = rng.uniform(0.0001, 0.01)
        elif ctype == "medium":
            selectivities[i] = rng.uniform(0.02, 0.15)
        else:
            selectivities[i] = rng.uniform(0.20, 0.45)

    cost_reductions = np.zeros(num_samples)

    for i in range(num_samples):
        N = table_sizes[i]
        sigma = selectivities[i]
        tree_depth = max(2, int(np.log2(N) / 4))

        if is_join[i] == 1:
            fts_cost = N * 1.0
            idx_cost = tree_depth * 1.0 + (sigma * N * 1.0)
            reduction = max(0.0, 1.0 - (idx_cost / max(1.0, fts_cost)))
            reduction = min(0.98, reduction + 0.15)
        elif is_equality[i] == 1:
            fts_cost = N * 1.0
            idx_cost = tree_depth * 1.0 + (sigma * N * 1.0)
            reduction = max(0.0, 1.0 - (idx_cost / max(1.0, fts_cost)))
        elif is_range[i] == 1:
            fts_cost = N * 1.0
            idx_cost = tree_depth * 1.0 + (sigma * N * 1.5)
            reduction = max(0.0, 1.0 - (idx_cost / max(1.0, fts_cost)))
        else:
            reduction = 0.10

        if N <= 500:
            reduction *= 0.60

        if is_order[i] == 1:
            reduction = min(0.95, reduction + 0.08)

        if frequencies[i] < 5:
            reduction *= 0.85

        cost_reductions[i] = np.clip(reduction, 0.0, 0.99)

    is_beneficial = (cost_reductions > 0.30).astype(int)

    df = pd.DataFrame({
        "frequency": frequencies,
        "is_join": is_join,
        "is_equality": is_equality,
        "is_range": is_range,
        "is_order": is_order,
        "selectivity": np.round(selectivities, 6),
        "table_size_log": np.round(table_size_logs, 2),
        "is_where": np.maximum(is_equality, is_range),  # backward compatibility
        "cost_reduction": np.round(cost_reductions, 4),
        "is_beneficial": is_beneficial,
    })
    return df


def generate_synthetic_data(num_samples: int = 500) -> pd.DataFrame:
    """Wrapper preserved for backward compatibility with existing tests."""
    return simulate_realistic_dbms_dataset(num_samples=num_samples)


def train_and_save_model(
    model_output_path: str = "models/index_recommender_model.pkl",
    num_samples: int = 1500
) -> RandomForestClassifier:
    """Trains Random Forest model on grounded DBMS cost reduction features."""
    print(f"Generating {num_samples} realistic DBMS optimizer workload samples...")
    data = simulate_realistic_dbms_dataset(num_samples=num_samples)

    X = data[FEATURE_NAMES]
    y = data["is_beneficial"]

    print(f"Dataset class balance: Beneficial={y.sum()}/{len(y)} ({y.mean()*100:.1f}%)")
    print(f"Training Random Forest Classifier on {len(X)} samples with features {FEATURE_NAMES}...")

    clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=8,
        min_samples_split=5,
        random_state=42
    )
    clf.fit(X, y)

    train_acc = accuracy_score(y, clf.predict(X))
    print(f"Model Training Accuracy: {train_acc * 100:.2f}%")

    os.makedirs(os.path.dirname(model_output_path), exist_ok=True)
    joblib.dump(clf, model_output_path)
    print(f"Model successfully saved to {model_output_path}")

    legacy_path = "models/rf_model.pkl"
    if os.path.abspath(model_output_path) != os.path.abspath(legacy_path):
        joblib.dump(clf, legacy_path)
        print(f"Compatible mirror model saved to {legacy_path}")

    return clf


if __name__ == "__main__":
    train_and_save_model()
