"""Unit tests for Ollama provider HTTP failure diagnostics."""

from unittest.mock import Mock, patch

import pytest
import requests
from pydantic import BaseModel

from app.llm.providers.ollama import OllamaProvider


class _ResponseSchema(BaseModel):
    value: str


def test_structured_generation_logs_ollama_error_body_before_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expose Ollama's bounded error body when structured generation fails."""
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test")
    monkeypatch.setenv("OLLAMA_MODEL", "test-model")

    response = Mock(status_code=400, text='{"error":"unsupported format"}')
    response.raise_for_status.side_effect = requests.HTTPError("400 Client Error")
    logger = Mock()

    with (
        patch("app.llm.providers.ollama.requests.post", return_value=response),
        patch("app.llm.providers.ollama.logger", logger),
        pytest.raises(requests.HTTPError),
    ):
        OllamaProvider().generate_structured_json("Generate a value", _ResponseSchema)

    logger.error.assert_called_once_with(
        "ollama_generate_error",
        status=400,
        body='{"error":"unsupported format"}',
    )
    response.raise_for_status.assert_called_once()
