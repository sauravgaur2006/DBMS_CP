import json
import os
import joblib
import pandas as pd


def load_workload(filepath):
    with open(filepath, 'r') as file:
        return json.load(file)


def extract_features(query, column):
    """
    Extracts features for a specific column in a query to feed into the ML model.
    """
    return {
        'frequency': query.get("frequency", 1),
        'is_where': 1 if column in query.get("where_columns", []) else 0,
        'is_join': 1 if column in query.get("join_columns", []) else 0,
        'is_order': 1 if column in query.get("order_columns", []) else 0
    }


def generate_ml_recommendations(workload, model_path):
    if not os.path.exists(model_path):
        print(f"Model file not found at {model_path}. Training a new model...")
        from models.train_model import train_and_save_model
        train_and_save_model(model_path)

    print(f"Loading ML Model from {model_path}...")
    model = joblib.load(model_path)
    recommendations = []

    for query in workload:
        table = query.get("table", "UNKNOWN")
        if not table or table == "UNKNOWN":
            continue

        # Collect all unique columns mentioned in this query
        all_columns = set(
            query.get("where_columns", []) +
            query.get("join_columns", []) +
            query.get("order_columns", [])
        )

        for col in all_columns:
            # Extract features for the model
            features = extract_features(query, col)
            features_df = pd.DataFrame([features])

            # Ask the model to predict if indexing this column is beneficial
            # predict_proba returns probability for [0 (not beneficial), 1 (beneficial)]
            probabilities = model.predict_proba(features_df)[0]
            beneficial_prob = probabilities[1]

            # If the model is more than 60% confident it's beneficial, recommend it!
            if beneficial_prob > 0.60:
                recommendations.append({
                    "query_id": query["query_id"],
                    "table": table,
                    "columns": [col],
                    "confidence_score": round(beneficial_prob * 100, 2),
                    "reason": f"ML Model predicted beneficial with {round(beneficial_prob * 100, 2)}% confidence."
                })

    return recommendations


def save_recommendations(recommendations, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as file:
        json.dump(recommendations, file, indent=2)
    print(
        f"Success! {len(recommendations)} ML-based index recommendations saved to {filepath}")


if __name__ == "__main__":
    input_path = "data/analyzed_workload.json"
    model_path = "models/rf_model.pkl"
    output_path = "data/ml_recommendations.json"

    print("Loading workload data...")
    workload_data = load_workload(input_path)

    print("Generating ML candidate indexes...")
    recs = generate_ml_recommendations(workload_data, model_path)

    save_recommendations(recs, output_path)
