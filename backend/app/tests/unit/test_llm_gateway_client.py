"""Cliente LLM Gateway: errores de red y respuestas válidas."""

from __future__ import annotations

import os
from typing import Any

import httpx
import pytest

from app.core.config import get_settings
from app.services.llm_gateway_client import LLMGatewayClient


@pytest.fixture
def gateway_enabled() -> None:
    os.environ["LLM_GATEWAY_ENABLED"] = "true"
    os.environ["LLM_GATEWAY_URL"] = "http://gateway.test"
    os.environ["LLM_GATEWAY_TIMEOUT_SECONDS"] = "0.5"
    get_settings.cache_clear()


def test_disabled_returns_error() -> None:
    os.environ["LLM_GATEWAY_ENABLED"] = "false"
    get_settings.cache_clear()
    result, err = LLMGatewayClient().interpret("hola")
    assert result is None
    assert "deshabilitado" in (err or "").lower()


def test_enabled_without_url() -> None:
    os.environ["LLM_GATEWAY_ENABLED"] = "true"
    os.environ["LLM_GATEWAY_URL"] = ""
    get_settings.cache_clear()
    result, err = LLMGatewayClient().interpret("hola")
    assert result is None
    assert "LLM_GATEWAY_URL" in (err or "")


def test_interpret_ok(gateway_enabled, monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {
                "resolved": True,
                "source": "llm",
                "intent": "trend",
                "metric": "avg_wait_days",
                "endpoint": "/api/v1/kpis/query",
                "translated_payload": {"intent": "trend", "metric": "avg_wait_days"},
                "assumptions": [],
                "confidence": 0.9,
            }

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp())
    result, err = LLMGatewayClient().interpret("espera promedio?")
    assert err is None
    assert result is not None
    assert result.intent == "trend"


def test_interpret_non_object_json(gateway_enabled, monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> list[int]:
            return [1, 2]

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp())
    result, err = LLMGatewayClient().interpret("q")
    assert result is None
    assert "JSON" in (err or "")


def test_interpret_timeout(gateway_enabled, monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*a, **k):
        raise httpx.TimeoutException("slow")

    monkeypatch.setattr(httpx, "post", _raise)
    result, err = LLMGatewayClient().interpret("q")
    assert result is None
    assert "Timeout" in (err or "")


def test_interpret_request_error(gateway_enabled, monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*a, **k):
        raise httpx.RequestError("down")

    monkeypatch.setattr(httpx, "post", _raise)
    result, err = LLMGatewayClient().interpret("q")
    assert result is None
    assert "conectar" in (err or "").lower()


def test_interpret_http_status(gateway_enabled, monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("POST", "http://gateway.test/x")
    response = httpx.Response(500, request=request)

    def _raise(*a, **k):
        raise httpx.HTTPStatusError("boom", request=request, response=response)

    monkeypatch.setattr(httpx, "post", _raise)
    result, err = LLMGatewayClient().interpret("q")
    assert result is None
    assert "HTTP 500" in (err or "")


def test_interpret_invalid_json_body(gateway_enabled, monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            raise ValueError("bad json")

    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp())
    result, err = LLMGatewayClient().interpret("q")
    assert result is None
    assert "JSON invalido" in (err or "")
