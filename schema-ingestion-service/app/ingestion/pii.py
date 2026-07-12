"""PII masking for sample values — applied BEFORE anything is persisted or sent to an AI model.

Regex-based v1. Known limitation: does not catch person names or free-text PII;
extend with an NER pass before production use on sensitive schemas.
"""
import re

_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE = re.compile(r"(?<!\d)(\+?\d[\d\s().-]{7,}\d)(?!\d)")
_SSN_LIKE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CARD_LIKE = re.compile(r"\b(?:\d[ -]?){13,19}\b")

_SENSITIVE_COLUMN_HINTS = (
    "email", "phone", "mobile", "ssn", "passport", "tax_id", "aadhaar", "pan",
    "password", "secret", "token", "address", "dob", "birth",
)


def column_is_sensitive(column_name: str) -> bool:
    lowered = column_name.lower()
    return any(hint in lowered for hint in _SENSITIVE_COLUMN_HINTS)


def mask_value(value: str) -> str:
    masked = _EMAIL.sub("***@***", value)
    masked = _SSN_LIKE.sub("***-**-****", masked)
    masked = _CARD_LIKE.sub("**** **** ****", masked)
    masked = _PHONE.sub("***-***-****", masked)
    return masked


def mask_samples(column_name: str, values: list) -> list[str]:
    """Sensitive-named columns store no raw samples at all; others get regex masking."""
    if column_is_sensitive(column_name):
        return ["<masked: sensitive column>"]
    return [mask_value(str(v))[:200] for v in values]
