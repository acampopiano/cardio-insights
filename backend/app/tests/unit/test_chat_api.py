"""Contratos HTTP del endpoint /chat."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.schemas.chat import ChatResponse
from app.tests.conftest import get_token


def test_chat_requires_auth(client: TestClient) -> None:
    response = client.post("/api/v1/chat", json={"question": "Cuántas cirugías hubo?"})
    assert response.status_code == 401


def test_chat_disabled_response(client: TestClient) -> None:
    os.environ["CHAT_ENABLED"] = "false"
    get_settings.cache_clear()
    token = get_token(client)
    response = client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "Cuántas cirugías hubo en 2024?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["resolved"] is False
    assert data["error"] == "chat_disabled"


def test_chat_ok_with_mocked_service(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response = ChatResponse(
        question="Cuántas cirugías?",
        answer="Hubo 10 cirugías.",
        resolved=True,
        sql="SELECT COUNT(*) AS total FROM dat_cirugia LIMIT 50",
        rows=[{"total": 10}],
        row_count=1,
    )

    mock_svc = MagicMock()
    mock_svc.ask.return_value = fake_response
    monkeypatch.setattr("app.api.v1.chat.ChatService", lambda: mock_svc)

    token = get_token(client)
    response = client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "question": "Cuántas cirugías?",
            "history": [{"role": "user", "content": "contexto previo"}],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["resolved"] is True
    assert data["row_count"] == 1
    mock_svc.ask.assert_called_once()
