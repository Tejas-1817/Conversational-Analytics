"""Naming-convention relationship matcher."""
from app.ingestion.relationships import _match_by_naming


class Stub:
    pass


def _tables(*names):
    return {n: Stub() for n in names}, {n: Stub() for n in names}


def test_simple_plural_match():
    tables, pks = _tables("customers")
    assert _match_by_naming("customer_id", tables, pks) is not None


def test_exact_singular_match():
    tables, pks = _tables("order")
    assert _match_by_naming("order_id", tables, pks) is not None


def test_y_to_ies_plural():
    tables, pks = _tables("categories")
    assert _match_by_naming("category_id", tables, pks) is not None


def test_plain_id_never_matches():
    tables, pks = _tables("customers")
    assert _match_by_naming("id", tables, pks) is None


def test_non_id_column_never_matches():
    tables, pks = _tables("customers")
    assert _match_by_naming("net_amt", tables, pks) is None


def test_no_match_without_single_column_pk():
    tables, _ = _tables("customers")
    assert _match_by_naming("customer_id", tables, {}) is None
