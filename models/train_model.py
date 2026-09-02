import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib


def generate_synthetic_data(num_samples=500):
    """
    Generates synthetic workload training data.
    Features:
      - frequency: How often the query runs (1 to 200)
      - is_where: 1 if column is in WHERE clause, else 0
      - is_join: 1 if column is in JOIN clause, else 0
      - is_order: 1 if column is in ORDER BY clause, else 0
    Target:
      - is_beneficial: 1 if creating an index helps, else 0
    """
    np.random.seed(42)

    frequencies = np.random.randint(1, 200, size=num_samples)
    is_where = np.random.choice([0, 1], size=num_samples, p=[0.3, 0.7])
    is_join = np.random.choice([0, 1], size=num_samples, p=[0.6, 0.4])
    is_order = np.random.choice([0, 1], size=num_samples, p=[0.7, 0.3])

    # Simple mathematical logic for synthetic ground truth (label):
    # High frequency + JOIN/WHERE usage -> Highly beneficial (1)
    score = (frequencies * 0.5) + (is_where * 40) + \
        (is_join * 60) + (is_order * 15)
    noise = np.random.normal(0, 15, size=num_samples)
    final_score = score + noise

    is_beneficial = (final_score > 70).astype(int)

    df = pd.DataFrame({
        'frequency': frequencies,
        'is_where': is_where,
        'is_join': is_join,
        'is_order': is_order,
        'is_beneficial': is_beneficial
    })
    return df


def train_and_save_model(model_output_path="models/rf_model.pkl"):
    print("Generating synthetic workload data for model training...")
    data = generate_synthetic_data(num_samples=500)

    X = data[['frequency', 'is_where', 'is_join', 'is_order']]
    y = data['is_beneficial']

    print(f"Training Random Forest model on {len(data)} samples...")
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X, y)

    os.makedirs(os.path.dirname(model_output_path), exist_ok=True)
    joblib.dump(clf, model_output_path)
    print(f"Model successfully saved to {model_output_path}")


if __name__ == "__main__":
    train_and_save_model()
