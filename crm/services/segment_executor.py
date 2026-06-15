"""
Segment Executor — translates a filter_spec dict into Supabase PostgREST
queries and executes them against the database.

Two execution strategies:
  1. PostgREST native filters (for simple AND-only flat specs)
  2. Supabase RPC with dynamic SQL (for nested AND/OR specs)

The executor always returns (customer_count, preview_names).
"""

from __future__ import annotations

import logging
from typing import Any

from config import supabase

logger = logging.getLogger(__name__)

# ── Field mapping ────────────────────────────────────────────────────────────
# Maps filter_spec field names to their table context.
# "score_field" means it lives on customer_scores, "customer_field" on customers.

SCORE_FIELDS = {"monetary", "recency_days", "frequency", "churn_risk", "top_category", "rfm_score"}
CUSTOMER_FIELDS = {"city", "channel_pref"}

ALL_VALID_FIELDS = SCORE_FIELDS | CUSTOMER_FIELDS

# SQL column references for RPC path
FIELD_TO_SQL: dict[str, str] = {
    "monetary": "s.monetary",
    "recency_days": "s.recency_days",
    "frequency": "s.frequency",
    "churn_risk": "s.churn_risk",
    "top_category": "s.top_category",
    "city": "c.city",
    "channel_pref": "c.channel_pref",
    "rfm_score": "s.rfm_score",
}

OP_TO_SQL: dict[str, str] = {
    "eq": "=",
    "neq": "!=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "contains": "ILIKE",
}

# PostgREST operator mapping
OP_TO_POSTGREST: dict[str, str] = {
    "eq": "eq",
    "neq": "neq",
    "gt": "gt",
    "gte": "gte",
    "lt": "lt",
    "lte": "lte",
    "in": "in",
    "not_in": "not.in",
    "contains": "ilike",
}


def _org(query, org_id: str | None):
    """Apply the tenant filter to a customers query (no-op when org_id is None)."""
    return query.eq("org_id", org_id) if org_id else query


# ═══════════════════════════════════════════════════════════════════════════════
# SQL builder (used for filter_spec_to_sql and complex nested specs)
# ═══════════════════════════════════════════════════════════════════════════════

def filter_spec_to_sql(spec: dict) -> tuple[str, list]:
    """
    Recursively convert a filter_spec to a parameterised WHERE clause.

    Returns
    -------
    (where_clause : str, params : list)
    """
    params: list[Any] = []
    clause = _build_clause(spec, params)
    return clause, params


def _build_clause(node: dict, params: list) -> str:
    combinator = node.get("operator", "AND")
    parts: list[str] = []

    for condition in node.get("conditions", []):
        # Nested group (recursive)
        if "operator" in condition and "conditions" in condition:
            parts.append(f"({_build_clause(condition, params)})")
            continue

        field_name = condition.get("field", "")
        op = condition.get("op", "eq")
        value = condition.get("value")

        field = FIELD_TO_SQL.get(field_name)
        if field is None:
            raise ValueError(f"Unknown filter field: {field_name}")

        if op in ("in", "not_in"):
            if not isinstance(value, list) or len(value) == 0:
                raise ValueError(f"Operator '{op}' requires a non-empty list value.")
            placeholders = ", ".join(["$" + str(len(params) + 1 + i) for i in range(len(value))])
            sql_op = "IN" if op == "in" else "NOT IN"
            parts.append(f"{field} {sql_op} ({placeholders})")
            params.extend(value)
        elif op == "contains":
            params.append(f"%{value}%")
            parts.append(f"{field} ILIKE ${len(params)}")
        else:
            sql_op = OP_TO_SQL.get(op)
            if sql_op is None:
                raise ValueError(f"Unknown operator: {op}")
            params.append(value)
            parts.append(f"{field} {sql_op} ${len(params)}")

    if not parts:
        return "TRUE"

    return f" {combinator} ".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# Execution engine: PostgREST path (fast, for flat AND-only specs)
# ═══════════════════════════════════════════════════════════════════════════════

def _is_flat_and_spec(spec: dict) -> bool:
    """Check if this spec is a simple flat AND with no nesting."""
    if spec.get("operator", "AND") != "AND":
        return False
    for cond in spec.get("conditions", []):
        if "operator" in cond and "conditions" in cond:
            return False
    return True


def _apply_postgrest_filter(query, field: str, op: str, value: Any, table_ref: str | None):
    """Apply a single PostgREST filter to a query builder."""
    postgrest_op = OP_TO_POSTGREST.get(op)
    if postgrest_op is None:
        raise ValueError(f"Unsupported operator for PostgREST path: {op}")

    if op == "contains":
        value = f"*{value}*"

    if op in ("in", "not_in"):
        # PostgREST expects a tuple-like string for IN: (val1,val2,val3)
        value_str = "(" + ",".join(str(v) for v in value) + ")"
        if table_ref:
            return query.filter(f"{table_ref}.{field}", postgrest_op, value_str)
        else:
            return query.filter(field, postgrest_op, value_str)

    if table_ref:
        return query.filter(f"{table_ref}.{field}", postgrest_op, value)
    else:
        return query.filter(field, postgrest_op, value)


def _spec_needs_score(spec: dict) -> bool:
    """True if any condition (recursively) filters on a customer_scores field."""
    for cond in spec.get("conditions", []):
        if "operator" in cond and "conditions" in cond:
            if _spec_needs_score(cond):
                return True
        elif cond.get("field") in SCORE_FIELDS:
            return True
    return False


def _execute_via_postgrest(spec: dict, org_id: str | None = None) -> tuple[int, list[str]]:
    """Execute a flat AND-only filter spec using PostgREST native filters."""
    # Only require a score (inner join) when the filter actually uses score
    # fields. A city/channel-only filter must still match brand-new customers
    # who have no orders yet (and therefore no customer_scores row).
    join = "!inner" if _spec_needs_score(spec) else ""
    query = supabase.table("customers").select(
        f"id, first_name, last_name, score:customer_scores{join}(*)",
        count="exact",
    )
    query = _org(query, org_id)

    for cond in spec.get("conditions", []):
        field = cond["field"]
        op = cond["op"]
        value = cond["value"]

        if field in SCORE_FIELDS:
            query = _apply_postgrest_filter(query, field, op, value, table_ref="score")
        elif field in CUSTOMER_FIELDS:
            query = _apply_postgrest_filter(query, field, op, value, table_ref=None)
        else:
            raise ValueError(f"Unknown filter field: {field}")

    # Limit to first 5 for preview
    query = query.limit(5)
    res = query.execute()

    total = res.count if res.count is not None else len(res.data)
    preview = [
        f"{row['first_name']} {row.get('last_name') or ''}".strip()
        for row in (res.data or [])
    ]
    return total, preview


# ═══════════════════════════════════════════════════════════════════════════════
# Execution engine: RPC path (for complex nested AND/OR specs)
# ═══════════════════════════════════════════════════════════════════════════════

def _execute_via_rpc(spec: dict, org_id: str | None = None) -> tuple[int, list[str]]:
    """
    Execute a complex nested filter spec. The deployed RPC is a stub, so this
    falls back to client-side filtering (org-scoped).
    """
    return _execute_fallback(spec, org_id)


def _execute_fallback(spec: dict, org_id: str | None = None) -> tuple[int, list[str]]:
    """
    Fallback execution: fetch all customers with scores and filter client-side.
    Suitable for datasets up to ~50k customers. For larger datasets, deploy the RPC.
    """
    # Fetch all customers with their scores
    all_data: list[dict] = []
    offset = 0
    chunk_size = 1000

    while True:
        res = (
            _org(
                supabase.table("customers")
                .select("id, first_name, last_name, city, channel_pref, score:customer_scores(*)"),
                org_id,
            )
            .range(offset, offset + chunk_size - 1)
            .execute()
        )
        if not res.data:
            break
        all_data.extend(res.data)
        if len(res.data) < chunk_size:
            break
        offset += chunk_size

    # Flatten score into the top-level dict for filtering
    flat_rows = []
    for row in all_data:
        score = row.get("score")
        if isinstance(score, list):
            score = score[0] if score else {}
        elif not score:
            score = {}
        flat = {
            "id": row["id"],
            "first_name": row["first_name"],
            "last_name": row.get("last_name", ""),
            "city": row.get("city"),
            "channel_pref": row.get("channel_pref"),
            "monetary": score.get("monetary"),
            "recency_days": score.get("recency_days"),
            "frequency": score.get("frequency"),
            "churn_risk": score.get("churn_risk"),
            "top_category": score.get("top_category"),
            "rfm_score": score.get("rfm_score"),
        }
        flat_rows.append(flat)

    # Apply filter spec in memory
    matched = [row for row in flat_rows if _evaluate_spec(spec, row)]
    preview = [
        f"{row['first_name']} {row.get('last_name') or ''}".strip()
        for row in matched[:5]
    ]
    return len(matched), preview


def _evaluate_spec(spec: dict, row: dict) -> bool:
    """Recursively evaluate a filter_spec against a single flattened row."""
    combinator = spec.get("operator", "AND")
    results = []

    for cond in spec.get("conditions", []):
        if "operator" in cond and "conditions" in cond:
            results.append(_evaluate_spec(cond, row))
            continue

        field = cond.get("field", "")
        op = cond.get("op", "eq")
        expected = cond.get("value")
        actual = row.get(field)

        if actual is None:
            results.append(False)
            continue

        results.append(_compare(actual, op, expected))

    if not results:
        return True

    if combinator == "AND":
        return all(results)
    elif combinator == "OR":
        return any(results)
    return False


def _compare(actual: Any, op: str, expected: Any) -> bool:
    """Compare a single value using the given operator."""
    try:
        if op == "eq":
            return actual == expected
        elif op == "neq":
            return actual != expected
        elif op == "gt":
            return float(actual) > float(expected)
        elif op == "gte":
            return float(actual) >= float(expected)
        elif op == "lt":
            return float(actual) < float(expected)
        elif op == "lte":
            return float(actual) <= float(expected)
        elif op == "in":
            return actual in expected
        elif op == "not_in":
            return actual not in expected
        elif op == "contains":
            return str(expected).lower() in str(actual).lower()
    except (TypeError, ValueError):
        return False
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def execute_filter_spec(spec: dict, org_id: str | None = None) -> tuple[int, list[str]]:
    """
    Run a filter_spec against Supabase and return (count, preview_names),
    scoped to org_id when provided.
    """
    if not spec or not spec.get("conditions"):
        # Empty spec matches everyone (in the org)
        res = _org(
            supabase.table("customers").select("id, first_name, last_name", count="exact"),
            org_id,
        ).limit(5).execute()
        total = res.count if res.count is not None else len(res.data)
        preview = [
            f"{row['first_name']} {row.get('last_name') or ''}".strip()
            for row in (res.data or [])
        ]
        return total, preview

    # Validate all fields before execution
    _validate_spec_fields(spec)

    if _is_flat_and_spec(spec):
        logger.info("Executing segment via PostgREST native filters (fast path).")
        return _execute_via_postgrest(spec, org_id)
    else:
        logger.info("Executing segment via RPC/fallback (complex nested spec).")
        return _execute_via_rpc(spec, org_id)


def _validate_spec_fields(spec: dict) -> None:
    """Recursively validate that all fields in the spec are known."""
    for cond in spec.get("conditions", []):
        if "operator" in cond and "conditions" in cond:
            _validate_spec_fields(cond)
            continue
        field = cond.get("field", "")
        if field not in ALL_VALID_FIELDS:
            raise ValueError(f"Unknown filter field: '{field}'. Valid fields: {sorted(ALL_VALID_FIELDS)}")
        op = cond.get("op", "")
        valid_ops = set(OP_TO_SQL.keys()) | {"in", "not_in"}
        if op not in valid_ops:
            raise ValueError(f"Unknown operator: '{op}'. Valid operators: {sorted(valid_ops)}")


def get_segment_customer_ids(spec: dict, org_id: str | None = None) -> list[str]:
    """
    Execute the filter spec and return the full list of matching customer IDs,
    scoped to org_id. Used by the campaign launcher to resolve segment → customers.
    """
    # Semantic segments carry an explicit id list (from RAG search).
    if spec and spec.get("static_ids"):
        ids = spec["static_ids"]
        if not org_id:
            return ids
        # Keep only ids that belong to this org
        kept: list[str] = []
        for i in range(0, len(ids), 200):
            chunk = ids[i : i + 200]
            res = supabase.table("customers").select("id").eq("org_id", org_id).in_("id", chunk).execute()
            kept.extend(r["id"] for r in (res.data or []))
        return kept

    if not spec or not spec.get("conditions"):
        # Empty spec: all customers (in the org)
        all_data: list[dict] = []
        offset = 0
        chunk_size = 1000
        while True:
            res = (
                _org(supabase.table("customers").select("id"), org_id)
                .range(offset, offset + chunk_size - 1)
                .execute()
            )
            if not res.data:
                break
            all_data.extend(res.data)
            if len(res.data) < chunk_size:
                break
            offset += chunk_size
        return [row["id"] for row in all_data]

    _validate_spec_fields(spec)

    if _is_flat_and_spec(spec):
        return _get_ids_postgrest(spec, org_id)
    else:
        return _get_ids_fallback(spec, org_id)


def _get_ids_postgrest(spec: dict, org_id: str | None = None) -> list[str]:
    """Get all matching customer IDs via PostgREST for flat AND specs."""
    all_ids: list[str] = []
    offset = 0
    chunk_size = 1000

    needs_score = _spec_needs_score(spec)
    select_str = "id, score:customer_scores!inner(customer_id)" if needs_score else "id"
    while True:
        query = supabase.table("customers").select(select_str)
        query = _org(query, org_id)
        for cond in spec.get("conditions", []):
            field = cond["field"]
            op = cond["op"]
            value = cond["value"]
            if field in SCORE_FIELDS:
                query = _apply_postgrest_filter(query, field, op, value, table_ref="score")
            else:
                query = _apply_postgrest_filter(query, field, op, value, table_ref=None)

        query = query.range(offset, offset + chunk_size - 1)
        res = query.execute()
        if not res.data:
            break
        all_ids.extend(row["id"] for row in res.data)
        if len(res.data) < chunk_size:
            break
        offset += chunk_size

    return all_ids


def _get_ids_fallback(spec: dict, org_id: str | None = None) -> list[str]:
    """Get matching IDs for complex specs via client-side filtering."""
    all_data: list[dict] = []
    offset = 0
    chunk_size = 1000

    while True:
        res = (
            _org(
                supabase.table("customers")
                .select("id, first_name, last_name, city, channel_pref, score:customer_scores(*)"),
                org_id,
            )
            .range(offset, offset + chunk_size - 1)
            .execute()
        )
        if not res.data:
            break
        all_data.extend(res.data)
        if len(res.data) < chunk_size:
            break
        offset += chunk_size

    flat_rows = []
    for row in all_data:
        score = row.get("score")
        if isinstance(score, list):
            score = score[0] if score else {}
        elif not score:
            score = {}
        flat = {
            "id": row["id"],
            "city": row.get("city"),
            "channel_pref": row.get("channel_pref"),
            **{k: score.get(k) for k in SCORE_FIELDS},
        }
        flat_rows.append(flat)

    return [row["id"] for row in flat_rows if _evaluate_spec(spec, row)]
