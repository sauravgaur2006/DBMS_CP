"""
Index Redundancy & Budget Optimizer (Person 3)

==============================================
Prunes redundant indexes and enforces strict index storage and count budgets:
  1. Prefix Redundancy Elimination:
     If a composite index `(col1, col2)` is selected, single-column index `(col1)`
     is redundant because MySQL B-Tree can use the leftmost prefix.
  2. Budget Constraint:
     Selects the top-K highest-utility non-redundant indexes subject to
     `--max-indexes` (default 8) and `--max-storage-mb` (default 25.0 MB).
  3. SQL Script Exporter:
     Generates executable `data/apply_indexes.sql` and `data/rollback_indexes.sql`.
"""

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from recommendation.catalog import catalog


def clean_index_name(table: str, columns: List[str]) -> str:
    """Generate a clean, valid MySQL identifier for an index."""
    col_str = "_".join(c.lower() for c in columns)
    col_clean = re.sub(r"[^a-z0-9_]", "", col_str)
    return f"idx_{table.lower()}_{col_clean}"


def is_prefix_redundant(short_cols: List[str], long_cols: List[str]) -> bool:
    """
    Returns True if short_cols is a strict left-prefix of long_cols.
    Example: ['department'] is a prefix of ['department', 'city'].
    """
    if len(short_cols) >= len(long_cols):
        return False
    return long_cols[:len(short_cols)] == short_cols


def deduplicate_and_aggregate_candidates(
    raw_recommendations: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Aggregates duplicate recommendations across different queries.
    Combines utility scores and tracks all servicing query IDs.
    """
    index_map: Dict[Tuple[str, Tuple[str, ...]], Dict[str, Any]] = {}

    for rec in raw_recommendations:
        table = rec.get("table", "")
        cols = tuple(c.lower() for c in rec.get("columns", []))
        if not table or not cols:
            continue

        key = (table, cols)
        score = float(rec.get("score", 0.0))
        qid = rec.get("query_id")

        if key not in index_map:
            size_mb = rec.get("estimated_size_mb")
            if size_mb is None:
                size_mb = catalog.estimate_index_size_mb(table, list(cols))

            index_map[key] = {
                "table": table,
                "columns": list(cols),
                "index_name": clean_index_name(table, list(cols)),
                "total_score": score,
                "query_ids": [qid] if qid is not None else [],
                "estimated_size_mb": size_mb,
                "selectivity": rec.get("selectivity", 0.1),
                "is_composite": len(cols) > 1,
                "reasons": [rec.get("reason", "")]
            }
        else:
            index_map[key]["total_score"] += score
            if qid is not None and qid not in index_map[key]["query_ids"]:
                index_map[key]["query_ids"].append(qid)

    aggregated = list(index_map.values())
    aggregated.sort(key=lambda x: x["total_score"], reverse=True)
    return aggregated


def optimize_index_selection(
    candidates: List[Dict[str, Any]],
    max_indexes: int = 8,
    max_storage_mb: float = 25.0,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Selects optimal non-redundant indexes within storage and count budgets.
    Returns (selected_indexes, pruned_indexes).
    """
    aggregated = deduplicate_and_aggregate_candidates(candidates)

    selected: List[Dict[str, Any]] = []
    pruned: List[Dict[str, Any]] = []
    current_storage_mb = 0.0

    for cand in aggregated:
        table = cand["table"]
        cols = cand["columns"]
        size_mb = cand["estimated_size_mb"]

        redundant = False
        redundancy_reason = ""
        for sel in selected:
            if sel["table"] == table:
                if is_prefix_redundant(cols, sel["columns"]):
                    redundant = True
                    redundancy_reason = (
                        f"Prefix redundant with selected composite index "
                        f"{sel['index_name']} ({', '.join(sel['columns'])})"
                    )
                    break

        if redundant:
            cand["prune_reason"] = redundancy_reason
            pruned.append(cand)
            continue

        if len(selected) >= max_indexes:
            cand["prune_reason"] = f"Exceeds max index count limit ({max_indexes})"
            pruned.append(cand)
            continue

        if current_storage_mb + size_mb > max_storage_mb:
            cand["prune_reason"] = (
                f"Exceeds storage budget ({current_storage_mb + size_mb:.2f}MB > {max_storage_mb}MB)"
            )
            pruned.append(cand)
            continue

        to_remove = []
        for sel in selected:
            if sel["table"] == table and is_prefix_redundant(sel["columns"], cols):
                to_remove.append(sel)

        for rem in to_remove:
            selected.remove(rem)
            current_storage_mb -= rem["estimated_size_mb"]
            rem["prune_reason"] = f"Subsumed by composite index {cand['index_name']}"
            pruned.append(rem)

        selected.append(cand)
        current_storage_mb += size_mb

    return selected, pruned


def generate_sql_scripts(
    indexes: List[Dict[str, Any]],
    apply_path: str = "data/apply_indexes.sql",
    rollback_path: str = "data/rollback_indexes.sql",
) -> None:
    """Generate executable MySQL scripts to create and drop recommended indexes."""
    os.makedirs(os.path.dirname(apply_path), exist_ok=True)
    os.makedirs(os.path.dirname(rollback_path), exist_ok=True)

    apply_lines = [
        "-- ============================================================",
        "-- Automatic Index Recommendation System — Apply Script",
        "-- Generated by Person 3 (Cost-Benefit & Budget Optimizer)",
        "-- ============================================================",
        "USE index_recommender;",
        ""
    ]

    rollback_lines = [
        "-- ============================================================",
        "-- Automatic Index Recommendation System — Rollback Script",
        "-- Drops all recommended secondary indexes to return to baseline",
        "-- ============================================================",
        "USE index_recommender;",
        ""
    ]

    for idx in indexes:
        table = idx["table"]
        cols = ", ".join(f"`{c}`" for c in idx["columns"])
        name = idx["index_name"]

        apply_lines.append(f"CREATE INDEX `{name}` ON `{table}`({cols});")
        rollback_lines.append(f"DROP INDEX `{name}` ON `{table}`;")

    apply_content = "\n".join(apply_lines) + "\n"
    rollback_content = "\n".join(rollback_lines) + "\n"

    with open(apply_path, "w", encoding="utf-8") as f:
        f.write(apply_content)

    with open(rollback_path, "w", encoding="utf-8") as f:
        f.write(rollback_content)

    print(f"Generated SQL Apply script: {apply_path} ({len(indexes)} indexes)")
    print(f"Generated SQL Rollback script: {rollback_path}")


def run_budget_optimizer(
    input_path: str = "data/recommendations.json",
    output_path: str = "data/recommendations.json",
    apply_sql_path: str = "data/apply_indexes.sql",
    rollback_sql_path: str = "data/rollback_indexes.sql",
    max_indexes: int = 8,
    max_storage_mb: float = 25.0,
) -> List[Dict[str, Any]]:
    """Runs end-to-end redundancy pruning and budget optimization."""
    if not os.path.exists(input_path):
        print(f"Warning: {input_path} not found.")
        return []

    with open(input_path, "r", encoding="utf-8") as f:
        raw_recs = json.load(f)

    selected, pruned = optimize_index_selection(
        candidates=raw_recs,
        max_indexes=max_indexes,
        max_storage_mb=max_storage_mb,
    )

    print(f"\n--- Budget Optimizer Summary ---")
    print(f"Total raw candidates: {len(raw_recs)}")
    print(f"Selected indexes: {len(selected)} (Budget: max {max_indexes})")
    print(f"Pruned indexes: {len(pruned)} (Redundancy / Budget limits)")
    total_size = sum(s["estimated_size_mb"] for s in selected)
    print(
        f"Estimated Total Index Storage: {total_size:.2f} MB (Budget: max {max_storage_mb} MB)")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(selected, f, indent=2)

    generate_sql_scripts(selected, apply_sql_path, rollback_sql_path)

    return selected


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Index Redundancy & Budget Optimizer")
    parser.add_argument(
        "--input", default="data/recommendations.json", help="Input recommendations JSON")
    parser.add_argument("--output", default="data/recommendations.json",
                        help="Output optimized recommendations JSON")
    parser.add_argument("--max-indexes", type=int, default=8,
                        help="Maximum number of indexes to create")
    parser.add_argument("--max-storage-mb", type=float,
                        default=25.0, help="Maximum index disk storage in MB")
    args = parser.parse_args()

    run_budget_optimizer(
        input_path=args.input,
        output_path=args.output,
        max_indexes=args.max_indexes,
        max_storage_mb=args.max_storage_mb,
    )
