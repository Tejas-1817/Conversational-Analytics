"""Tests for semantic generation recovery after an empty prior version."""

from app.ingestion.semantic_generator import needs_full_regeneration


def test_empty_active_semantic_model_forces_full_regeneration() -> None:
    """A manual seed must not prevent retrying a failed AI generation."""
    assert needs_full_regeneration(has_active_model=True, ai_entity_count=0)


def test_populated_active_semantic_model_keeps_incremental_generation() -> None:
    """An existing AI baseline only requires changed-table enrichment."""
    assert not needs_full_regeneration(has_active_model=True, ai_entity_count=1)
