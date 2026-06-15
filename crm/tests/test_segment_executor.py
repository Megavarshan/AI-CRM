"""
Tests for the segment executor's filter_spec → SQL translation.
"""

import pytest

from services.segment_executor import filter_spec_to_sql


def test_simple_gte():
    spec = {
        "operator": "AND",
        "conditions": [{"field": "monetary", "op": "gte", "value": 5000}],
    }
    clause, params = filter_spec_to_sql(spec)
    assert "s.monetary" in clause
    assert ">=" in clause
    assert params == [5000]


def test_compound_and():
    spec = {
        "operator": "AND",
        "conditions": [
            {"field": "monetary", "op": "gte", "value": 5000},
            {"field": "recency_days", "op": "gte", "value": 60},
        ],
    }
    clause, params = filter_spec_to_sql(spec)
    assert "AND" in clause
    assert len(params) == 2


def test_in_operator():
    spec = {
        "operator": "AND",
        "conditions": [
            {"field": "churn_risk", "op": "in", "value": ["high", "critical"]}
        ],
    }
    clause, params = filter_spec_to_sql(spec)
    assert "IN" in clause
    assert params == ["high", "critical"]


def test_unknown_field_raises():
    spec = {
        "operator": "AND",
        "conditions": [{"field": "nonexistent", "op": "eq", "value": 1}],
    }
    with pytest.raises(ValueError, match="Unknown filter field"):
        filter_spec_to_sql(spec)
