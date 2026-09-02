import json
import os

WEIGHTS = {
    "where": 1.0,
    "join": 1.5,
    "order": 0.5
}

def load_workload(filepath):
    with open(filepath, 'r') as file:
        return json.load(file)

def generate_and_score_candidates(workload):
    recommendations = []
    
    for query in workload:
        table = query["table"]
        freq = query["frequency"]
        column_scores = {}
        
        for col in query["where_columns"]:
            column_scores[col] = column_scores.get(col, 0) + (freq * WEIGHTS["where"])
            
        for col in query["join_columns"]:
            column_scores[col] = column_scores.get(col, 0) + (freq * WEIGHTS["join"])
            
        for col in query["order_columns"]:
            column_scores[col] = column_scores.get(col, 0) + (freq * WEIGHTS["order"])
            
        for col, score in column_scores.items():
            if score > 20: 
                recommendations.append({
                    "query_id": query["query_id"],
                    "table": table,
                    "columns": [col],
                    "score": score,
                    "reason": f"Rule-based score based on frequency ({freq}) and usage."
                })
                
    return recommendations

def save_recommendations(recommendations, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as file:
        json.dump(recommendations, file, indent=2)
    print(f"Success! {len(recommendations)} index recommendations saved to {filepath}")

if __name__ == "__main__":
    input_path = "data/analyzed_workload.json"
    output_path = "data/recommendations.json"
    
    print("Loading workload data...")
    workload_data = load_workload(input_path)
    
    print("Generating candidate indexes...")
    recs = generate_and_score_candidates(workload_data)
    
    save_recommendations(recs, output_path)
