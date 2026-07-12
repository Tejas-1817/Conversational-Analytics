"""Dimension/measure classification heuristics — additivity mistakes cause wrong numbers."""
from app.ingestion.classifier import _classify


class FakeColumn:
    def __init__(self, name, dtype, pk=False, distinct=None):
        self.column_name = name
        self.data_type = dtype
        self.is_primary_key = pk
        self.profile = {"distinct_count_sampled": distinct} if distinct is not None else {}


def test_primary_key_is_key():
    assert _classify(FakeColumn("id", "integer", pk=True)) == ("key", None, "not_applicable")


def test_foreign_key_naming_is_key():
    assert _classify(FakeColumn("customer_id", "integer")) == ("key", None, "not_applicable")


def test_date_is_dimension():
    assert _classify(FakeColumn("order_date", "date")) == ("dimension", None, "not_applicable")


def test_amount_is_additive_measure():
    assert _classify(FakeColumn("net_amt", "numeric(12,2)", distinct=800)) == ("measure", "sum", "additive")


def test_balance_is_semi_additive():
    role, agg, additivity = _classify(FakeColumn("account_balance", "numeric", distinct=900))
    assert (role, additivity) == ("measure", "semi_additive")


def test_percentage_is_non_additive_with_avg():
    assert _classify(FakeColumn("discount_pct", "numeric", distinct=900)) == ("measure", "avg", "non_additive")


def test_low_cardinality_string_is_dimension():
    assert _classify(FakeColumn("order_status", "text", distinct=4)) == ("dimension", None, "not_applicable")


def test_high_cardinality_string_is_attribute():
    assert _classify(FakeColumn("notes", "text", distinct=5000)) == ("attribute", None, "not_applicable")


def test_low_cardinality_numeric_is_dimension_not_measure():
    assert _classify(FakeColumn("priority_level", "integer", distinct=5)) == ("dimension", None, "not_applicable")
