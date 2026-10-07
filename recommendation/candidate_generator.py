"""
Candidate Index Generator with B-Tree Ordering & Selectivity Scoring (Person 3)
================================================================================
Generates single-column and composite index candidates based on workload analysis.
Enforces the MySQL B-Tree prefix ordering rule:
    [JOIN columns] -> [Equality WHERE columns] -> [Range WHERE column] -> [ORDER BY column]
Scores candidates using realistic query frequency, clause weights, and column selectivity:
    Benefit = Query Frequency * (1.0 - Selectivity) * Weight_clause
"""

import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from recommendation.catalog import catalog

# Clause weights representing access-path performance impact in MySQL B-Trees
WEIGHTS: Dict[str, float] = {
    "where": 1.0,
    "equality": 1.2,
    "join": 1.5,
    "range": 0.8,
    "order": 0.5,
}


def load_workload(filepath: str) -> List[Dict[str, Any]]:
    """Load analyzed workload JSON file."""
    with open(filepath, "r", encoding="utf-8") as file:
        return json.load(file)


def classify_where_predicates(query_str: str, where_cols: List[str]) -> Tuple[List[str], List[str]]:
    """
    Classify where_columns into equality vs range columns if not already provided.
    Detects range operators (<, >, <=, >=, BETWEEN, LIKE).
    """
    equality_cols = []
    range_cols = []
    q_lower = query_str.lower()

    for col in where_cols:
        col_lower = col.lower()
        pattern = rf"\b{re.escape(col_lower)}\b\s*(\bbetween\b|\blike\b|>=|<=|>|<)"
        if re.search(pattern, q_lower):
            range_cols.append(col)
        else:
            equality_cols.append(col)

    return equality_cols, range_cols


def build_composite_candidate(
    table: str,
    join_cols: List[str],
    equality_cols: List[str],
    range_cols: List[str],
    order_cols: List[str],
    max_cols: int = 3,
) -> Optional[List[str]]:
    """
    Constructs a composite candidate adhering to the B-Tree prefix ordering rule:
      [JOIN columns] -> [Equality WHERE columns] -> [Range WHERE column] -> [ORDER BY column]
    Caps index length at `max_cols` to prevent index bloat.
    """
    ordered_cols: List[str] = []

    # 1. JOIN columns
    for col in join_cols:
        if col not in ordered_cols:
            ordered_cols.append(col)

    # 2. Equality WHERE columns
    for col in equality_cols:
        if col not in ordered_cols:
            ordered_cols.append(col)

    # 3. First Range WHERE column (B-Tree index can only do range search on 1 column)
    for col in range_cols:
        if col not in ordered_cols:
            ordered_cols.append(col)
            break

    # 4. ORDER BY column (if not already included and space permits)
    for col in order_cols:
        if col not in ordered_cols:
            ordered_cols.append(col)
            break

    composite = ordered_cols[:max_cols]
    if len(composite) >= 2:
        return composite
    return None


def calculate_candidate_score(
    table: str,
    columns: List[str],
    freq: int,
    clause_types: Set[str],
    use_selectivity: bool = True,
) -> Tuple[float, float]:
    """
    Computes cost-benefit score:
      Benefit = Query Frequency * (1.0 - Selectivity) * Weight_clause
    Returns (score, selectivity).
    """
    if len(columns) == 1:
        sel = catalog.get_column_selectivity(table, columns[0])
    else:
        sel = catalog.get_composite_selectivity(table, columns)

    weight = 0.0
    for clause in clause_types:
        weight += WEIGHTS.get(clause, 1.0)
    if not weight:
        weight = 1.0

    if len(columns) > 1:
        weight *= 1.25

    if use_selectivity:
        score = freq * (1.0 - sel) * weight
    else:
        score = freq * weight

    return round(score, 2), round(sel, 6)


def generate_and_score_candidates(
    workload: List[Dict[str, Any]],
    min_score: float = 20.0,
    use_selectivity: bool = True,
) -> List[Dict[str, Any]]:
    """
    Analyzes workload queries to generate single-column and composite index candidates.
    Outputs structured recommendations with scores, selectivity, storage, and rationale.
    """
    recommendations: List[Dict[str, Any]] = []
    seen_candidates: Set[Tuple[int, str, Tuple[str, ...]]] = set()

    for query in workload:
        table = query.get("table", "UNKNOWN")
        if not table or table == "UNKNOWN":
            continue

        freq = query.get("frequency", 1)
        query_id = query.get("query_id", 0)
        query_sql = query.get("query", "")

        where_cols = query.get("where_columns", [])
        join_cols = query.get("join_columns", [])
        order_cols = query.get("order_columns", [])

        equality_cols = query.get("equality_columns")
        range_cols = query.get("range_columns")
        if equality_cols is None or range_cols is None:
            equality_cols, range_cols = classify_where_predicates(query_sql, where_cols)

        # 1. Single-Column Candidates
        all_cols_in_query = set(where_cols + join_cols + order_cols)
        for col in sorted(list(all_cols_in_query)):
            clauses: Set[str] = set()
            if col in join_cols:
                clauses.add("join")
            if col in equality_cols:
                clauses.add("equality")
            elif col in range_cols:
                clauses.add("range")
            elif col in where_cols:
                clauses.add("where")
            if col in order_cols:
                clauses.add("order")

            score, sel = calculate_candidate_score(
                table=table,
                columns=[col],
                freq=freq,
                clause_types=clauses,
                use_selectivity=use_selectivity,
            )

            if score > min_score:
                key = (query_id, table, (col,))
                if key not in seen_candidates:
                    seen_candidates.add(key)
                    size_mb = catalog.estimate_index_size_mb(table, [col])
                    reasons = [f"freq={freq}"]
                    if "join" in clauses:
                        reasons.append("JOIN lookup")
                    if "equality" in clauses:
                        reasons.append("equality filter")
                    if "range" in clauses:
                        reasons.append("range filter")
                    if "order" in clauses:
                        reasons.append("ORDER BY sorting")
                    reasons.append(f"sel={sel:.4f}")

                    recommendations.append({
                        "query_id": query_id,
                        "query": query_sql,
                        "table": table,
                        "columns": [col],
                        "score": score,
                        "selectivity": sel,
                        "estimated_size_mb": size_mb,
                        "is_composite": False,
                        "reason": f"Rule-based single-col index on {col} ({', '.join(reasons)})."
                    })

        # 2. Composite Candidates
        precomputed_composites = query.get("composite_candidates", [])
        composite_lists = []
        if precomputed_composites:
            for cand in precomputed_composites:
                if isinstance(cand, list) and len(cand) >= 2:
                    composite_lists.append(cand)

        generated_comp = build_composite_candidate(
            table=table,
            join_cols=join_cols,
            equality_cols=equality_cols,
            range_cols=range_cols,
            order_cols=order_cols,
        )
        if generated_comp and generated_comp not in composite_lists:
            composite_lists.append(generated_comp)

        for comp_cols in composite_lists:
            comp_clauses = set()
            for c in comp_cols:
                if c in join_cols:
                    comp_clauses.add("join")
                if c in equality_cols:
                    comp_clauses.add("equality")
                if c in range_cols:
                    comp_clauses.add("range")
                if c in order_cols:
                    comp_clauses.add("order")

            comp_score, comp_sel = calculate_candidate_score(
                table=table,
                columns=comp_cols,
                freq=freq,
                clause_types=comp_clauses,
                use_selectivity=use_selectivity,
            )

            if comp_score > min_score:
                comp_key = (query_id, table, tuple(comp_cols))
                if comp_key not in seen_candidates:
                    seen_candidates.add(comp_key)
                    comp_size_mb = catalog.estimate_index_size_mb(table, comp_cols)
                    recommendations.append({
                        "query_id": query_id,
                        "query": query_sql,
                        "table": table,
                        "columns": comp_cols,
                        "score": comp_score,
                        "selectivity": comp_sel,
                        "estimated_size_mb": comp_size_mb,
                        "is_composite": True,
                        "reason": (
                            f"Composite B-Tree index ({', '.join(comp_cols)}) covering "
                            f"{'+'.join(comp_clauses)} with B-Tree prefix ordering."
                        )
                    })

    return recommendations


def save_recommendations(recommendations: List[Dict[str, Any]], filepath: str) -> None:
    """Save recommendations to JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(recommendations, file, indent=2)
    print(f"Success! {len(recommendations)} index recommendations saved to {filepath}")


if __name__ == "__main__":
    input_path = "data/analyzed_workload.json"
    output_path = "data/recommendations.json"

    if os.path.exists(input_path):
        print(f"Loading workload from {input_path}...")
        workload_data = load_workload(input_path)
        print("Generating candidate indexes with B-Tree ordering and selectivity...")
        recs = generate_and_score_candidates(workload_data)
        save_recommendations(recs, output_path)
    else:
        print(f"File {input_path} does not exist yet. Please run analyzer first.")
