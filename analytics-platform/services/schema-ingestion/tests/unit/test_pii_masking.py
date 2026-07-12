"""Guardrail tests: PII must never reach storage or LLMs unmasked."""
from app.ingestion.pii import column_is_sensitive, mask_samples, mask_value


def test_email_is_masked():
    assert mask_value("contact john.doe@acme.com today") == "contact ***@*** today"


def test_phone_is_masked():
    assert "***-***-****" in mask_value("call 555-123-4567")


def test_ssn_like_is_masked():
    assert "***-**-****" in mask_value("ssn 123-45-6789")


def test_card_like_is_masked():
    assert "**** **** ****" in mask_value("4111 1111 1111 1111")


def test_sensitive_column_stores_no_raw_samples():
    assert mask_samples("email", ["real@person.com"]) == ["<masked: sensitive column>"]
    assert mask_samples("customer_phone", ["+1 555 000 1111"]) == ["<masked: sensitive column>"]


def test_non_sensitive_values_pass_through():
    assert mask_samples("region", ["NE-US", "EMEA"]) == ["NE-US", "EMEA"]


def test_sensitive_column_detection():
    assert column_is_sensitive("user_email_address")
    assert column_is_sensitive("date_of_birth")
    assert not column_is_sensitive("order_status")


def test_samples_are_truncated():
    assert len(mask_samples("notes", ["x" * 500])[0]) <= 200
