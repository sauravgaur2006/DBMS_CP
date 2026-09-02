"""
Automatic Index Recommendation — SQL / Workload Analyzer (Person 2)
===================================================================
Parses SQL queries from a workload CSV file, extracts key clause features
(table, WHERE columns, JOIN columns, ORDER BY columns, GROUP BY columns),
derives workload-level summary statistics, and saves:
  - data/analyzed_workload.json   (query-level analysis contract for Person 3)
  - data/workload_summary.json    (aggregate factual workload summary)

Usage:
    python analyzer/analyze.py [--input workload/workload.csv]
                               [--output data/analyzed_workload.json]
                               [--summary data/workload_summary.json]
"""

import argparse
from collections import Counter
import csv
import json
import os
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

import sqlglot
from sqlglot import exp

CANONICAL_TABLES = {
    "student": "Student",
    "course": "Course",
    "enrollment": "Enrollment",
    "attendance": "Attendance",
}


def deduplicate(items: List[str]) -> List[str]:
    """Preserve order of first appearance while removing duplicates."""
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def extract_table(tree: exp.Expression) -> str:
    """Extract primary driving table name from FROM clause."""
    from_clause = tree.find(exp.From)
    if not from_clause:
        return "UNKNOWN"
    table_exp = from_clause.find(exp.Table)
    if not table_exp or not table_exp.name:
        return "UNKNOWN"
    table_name = table_exp.name
    return CANONICAL_TABLES.get(table_name.lower(), table_name)


def extract_where_columns(tree: exp.Expression) -> List[str]:
    """
    Extract column names referenced in the WHERE clause in left-to-right order.
    Only returns actual table/column identifiers, ignoring literals,
    constants, strings, and numeric values.
    """
    where_clause = tree.find(exp.Where)
    if not where_clause:
        return []
    columns = [
        col.name.lower()
        for col in where_clause.dfs()
        if isinstance(col, exp.Column) and col.name
    ]
    return deduplicate(columns)


def extract_join_columns(tree: exp.Expression) -> List[str]:
    """
    Extract column names participating in JOIN conditions,
    supporting both ON conditions (e.g., ON s.id = e.id) and
    USING clauses (e.g., USING (student_id)).
    """
    columns = []
    for join in tree.find_all(exp.Join):
        # 1. Handle USING (col1, col2)
        using_items = join.args.get("using")
        if using_items:
            for item in using_items:
                name = getattr(item, "name", None) or str(item)
                if name:
                    columns.append(name.strip("`\"' ").lower())

        # 2. Handle ON conditions
        on_clause = join.args.get("on")
        if on_clause:
            for col in on_clause.dfs():
                if isinstance(col, exp.Column) and col.name:
                    columns.append(col.name.lower())
        elif not using_items:
            # Fallback for implicit or non-standard join expressions
            for col in join.dfs():
                if isinstance(col, exp.Column) and col.name:
                    columns.append(col.name.lower())

    return deduplicate(columns)


def extract_order_columns(tree: exp.Expression) -> List[str]:
    """
    Extract table column names in ORDER BY clauses in left-to-right order.
    Supports multiple ORDER BY columns with ASC/DESC, while excluding
    aggregate function wrappers (e.g. AVG(marks)) and aggregate aliases.
    """
    order_clause = tree.find(exp.Order)
    if not order_clause:
        return []

    # Map of alias names that represent aggregate expressions (e.g., AVG(...) AS avg_marks)
    agg_aliases = set()
    for s in tree.selects:
        if isinstance(s, exp.Alias) and s.find(exp.AggFunc):
            agg_aliases.add(s.alias.lower())

    columns = []
    for col in order_clause.dfs():
        if not isinstance(col, exp.Column) or not col.name:
            continue
        cname = col.name.lower()
        if cname in agg_aliases:
            continue

        # Check if the column is directly enclosed in an aggregate function in ORDER BY
        curr = col
        is_in_agg = False
        while curr and curr is not order_clause:
            if isinstance(curr, exp.AggFunc):
                is_in_agg = True
                break
            curr = curr.parent
        if is_in_agg:
            continue

        columns.append(cname)

    return deduplicate(columns)


def extract_group_columns(tree: exp.Expression) -> List[str]:
    """
    Extract column names referenced in GROUP BY clauses in left-to-right order.
    Supports single and multiple GROUP BY columns, table-qualified columns,
    and strips table/alias prefixes.
    """
    group_clause = tree.find(exp.Group)
    if not group_clause:
        return []
    columns = [
        col.name.lower()
        for col in group_clause.dfs()
        if isinstance(col, exp.Column) and col.name
    ]
    return deduplicate(columns)


def parse_query(sql: str, query_id: int = 0, frequency: int = 1) -> Dict[str, Any]:
    """
    Parse a single SQL statement and extract features according to the Person 2 contract.
    If the query has syntax errors or unsupported syntax, logs a useful warning and
    returns a safe fallback object rather than crashing the pipeline.
    """
    try:
        tree = sqlglot.parse_one(sql, read="mysql")
        table = extract_table(tree)
        where_cols = extract_where_columns(tree)
        join_cols = extract_join_columns(tree)
        order_cols = extract_order_columns(tree)
        group_cols = extract_group_columns(tree)
    except Exception as e:
        err_msg = str(e).split("\n")[0]
        print(f"Warning: Could not parse query Q{query_id}: {err_msg}", file=sys.stderr)
        return {
            "query_id": query_id,
            "query": sql,
            "table": "UNKNOWN",
            "where_columns": [],
            "join_columns": [],
            "order_columns": [],
            "group_columns": [],
            "frequency": frequency,
        }

    return {
        "query_id": query_id,
        "query": sql,
        "table": table,
        "where_columns": where_cols,
        "join_columns": join_cols,
        "order_columns": order_cols,
        "group_columns": group_cols,
        "frequency": frequency,
    }


def _get_column_usage_stats(
    workload: List[Dict[str, Any]], field: str
) -> List[Dict[str, Any]]:
    """
    Calculate factual column occurrences and frequency sums across the workload.
    Does NOT output index recommendations.
    """
    counts = Counter()
    freqs = Counter()
    for q in workload:
        for col in q.get(field, []):
            counts[col] += 1
            freqs[col] += q.get("frequency", 1)

    stats = []
    # Sort primarily by usage_count desc, then frequency_sum desc, then column name asc
    for col, count in sorted(
        counts.items(), key=lambda item: (-item[1], -freqs[item[0]], item[0])
    ):
        stats.append({
            "column": col,
            "usage_count": count,
            "frequency_sum": freqs[col],
        })
    return stats


def compute_workload_summary(
    analyzed_queries: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Derive factual workload-level statistics from the analyzed queries.
    Strictly reports factual metrics without making index recommendations.
    """
    total_queries = len(analyzed_queries)
    total_frequency = sum(q.get("frequency", 0) for q in analyzed_queries)

    tables = sorted(
        list(set(q["table"] for q in analyzed_queries if q.get("table") != "UNKNOWN"))
    )

    # Top 5 most frequent queries
    sorted_queries = sorted(
        analyzed_queries,
        key=lambda q: (-q.get("frequency", 0), q.get("query_id", 0)),
    )
    most_frequent = [
        {
            "query_id": q["query_id"],
            "frequency": q["frequency"],
            "table": q["table"],
            "query": q["query"],
        }
        for q in sorted_queries[:5]
    ]

    return {
        "total_queries": total_queries,
        "total_frequency": total_frequency,
        "unique_tables": len(tables),
        "tables": tables,
        "most_frequent_queries": most_frequent,
        "most_used_where_columns": _get_column_usage_stats(
            analyzed_queries, "where_columns"
        ),
        "most_used_join_columns": _get_column_usage_stats(
            analyzed_queries, "join_columns"
        ),
        "most_used_order_columns": _get_column_usage_stats(
            analyzed_queries, "order_columns"
        ),
        "most_used_group_columns": _get_column_usage_stats(
            analyzed_queries, "group_columns"
        ),
    }


def write_json_safely(data: Any, path: str) -> None:
    """
    Validate and save data to a JSON file, creating parent directories if needed.
    Ensures that the output is syntactically valid JSON.
    """
    try:
        parent_dir = os.path.dirname(os.path.abspath(path))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        # Validate serialization
        json_str = json.dumps(data, indent=2)
        # Validate that json_str can be re-parsed
        json.loads(json_str)

        with open(path, mode="w", encoding="utf-8") as f:
            f.write(json_str)
    except (OSError, IOError, PermissionError) as e:
        raise OSError(f"Error: Unable to write output file to '{path}': {e}") from e


def analyze_workload(
    csv_path: str = "workload/workload.csv",
    output_path: str = "data/analyzed_workload.json",
    summary_path: Optional[str] = "data/workload_summary.json",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Load queries from workload CSV, analyze each query, validate inputs,
    and save both the structured query analysis and aggregate workload summary.
    """
    # 1. Validate file existence
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Error: Workload file not found at '{csv_path}'. Please provide a valid file path."
        )

    # 2. Validate non-empty file
    if os.path.getsize(csv_path) == 0:
        raise ValueError(f"Error: Workload file '{csv_path}' is empty (0 bytes).")

    analyzed_queries = []
    seen_ids: Set[int] = set()

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # 3. Validate CSV headers
        if not reader.fieldnames:
            raise ValueError(
                f"Error: Workload file '{csv_path}' has no valid header row."
            )

        header_map = {name.strip().lower(): name for name in reader.fieldnames if name}
        required_fields = ["query_id", "query", "frequency"]
        missing_fields = [rf for rf in required_fields if rf not in header_map]
        if missing_fields:
            raise ValueError(
                f"Error: Missing required column(s) in '{csv_path}': {missing_fields}. "
                f"Found columns: {reader.fieldnames}"
            )

        qid_col = header_map["query_id"]
        query_col = header_map["query"]
        freq_col = header_map["frequency"]

        line_no = 1  # header is line 1
        for row in reader:
            line_no += 1

            # Validate query_id
            raw_qid = (row.get(qid_col) or "").strip()
            try:
                qid = int(raw_qid)
            except (ValueError, TypeError):
                qid = line_no - 1
                print(
                    f"Warning: Missing or non-integer query_id on line {line_no}. "
                    f"Using fallback query_id {qid}.",
                    file=sys.stderr,
                )

            # Check for duplicate query_id
            if qid in seen_ids:
                print(
                    f"Warning: Duplicate query_id '{qid}' detected on line {line_no}.",
                    file=sys.stderr,
                )
            else:
                seen_ids.add(qid)

            # Validate SQL text
            sql = (row.get(query_col) or "").strip()
            if not sql:
                print(
                    f"Warning: Query Q{qid} on line {line_no} has empty SQL text. Skipping.",
                    file=sys.stderr,
                )
                continue

            # Validate frequency
            raw_freq = (row.get(freq_col) or "").strip()
            try:
                freq = int(raw_freq)
                if freq <= 0:
                    print(
                        f"Warning: Non-positive frequency '{raw_freq}' for query Q{qid} on line {line_no}. "
                        f"Defaulting to 1.",
                        file=sys.stderr,
                    )
                    freq = 1
            except (ValueError, TypeError):
                print(
                    f"Warning: Invalid frequency value '{raw_freq}' for query Q{qid} on line {line_no}. "
                    f"Defaulting to 1.",
                    file=sys.stderr,
                )
                freq = 1

            # Parse query safely
            analysis = parse_query(sql, query_id=qid, frequency=freq)
            analyzed_queries.append(analysis)

    if not analyzed_queries:
        raise ValueError(
            f"Error: Workload file '{csv_path}' contains no valid query records to analyze."
        )

    # Compute aggregate workload statistics
    summary = compute_workload_summary(analyzed_queries)

    # Save primary query-level output
    write_json_safely(analyzed_queries, output_path)
    print(f"[OK] Successfully analyzed {len(analyzed_queries)} queries.")
    print(f"[OK] Query analysis saved to: {output_path}")

    # Save auxiliary summary output if requested
    if summary_path:
        write_json_safely(summary, summary_path)
        print(f"[OK] Workload summary saved to: {summary_path}")

    return analyzed_queries, summary


def main():
    parser = argparse.ArgumentParser(
        description="SQL Workload Analyzer (Person 2) — Parses queries and generates workload summary"
    )
    parser.add_argument(
        "--input",
        "-i",
        default="workload/workload.csv",
        help="Path to the input workload CSV (default: workload/workload.csv)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="data/analyzed_workload.json",
        help="Path to the output JSON file for analyzed queries (default: data/analyzed_workload.json)",
    )
    parser.add_argument(
        "--summary",
        "-s",
        default="data/workload_summary.json",
        help="Path to the output JSON file for workload summary (default: data/workload_summary.json)",
    )
    args = parser.parse_args()

    try:
        analyze_workload(
            csv_path=args.input,
            output_path=args.output,
            summary_path=args.summary,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
