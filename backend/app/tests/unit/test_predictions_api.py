"""Contratos HTTP de /predictions."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.services import ml_service as ml_service_module
from app.services.ml_service import _get_model
from app.tests.conftest import get_token
from app.tests.helpers.ml_artifacts import write_ptca_artifacts


@pytest.fixture
def ptca_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    models_dir = tmp_path / "models"
    write_ptca_artifacts(models_dir)
    monkeypatch.setattr(ml_service_module, "MODELS_DIR", models_dir)
    _get_model.cache_clear()
    yield
    _get_model.cache_clear()


def test_predictions_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/predictions/models").status_code == 401
    assert client.get("/api/v1/predictions/models/ptca").status_code == 401
    assert client.post("/api/v1/predictions/ptca", json={"values": {}}).status_code == 401


def test_predictions_forbid_gestion_role(client: TestClient, ptca_ready: None) -> None:
    token = get_token(client, username="ggarcia", password="Demo1234!")
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/predictions/models", headers=headers).status_code == 403
    assert client.get("/api/v1/predictions/models/ptca", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/predictions/ptca",
            headers=headers,
            json={"values": {"edad": 60}},
        ).status_code
        == 403
    )


def test_predictions_allow_admin_role(client: TestClient, ptca_ready: None) -> None:
    token = get_token(client, username="admin", password="Admin1234!")
    response = client.get(
        "/api/v1/predictions/models",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


def test_list_models(client: TestClient, ptca_ready: None) -> None:
    token = get_token(client)
    response = client.get(
        "/api/v1/predictions/models",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(m["cohort"] == "ptca" and m["available"] for m in data)


def test_get_model_meta(client: TestClient, ptca_ready: None) -> None:
    token = get_token(client)
    response = client.get(
        "/api/v1/predictions/models/ptca",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["cohort"] == "ptca"


def test_get_model_404(client: TestClient, ptca_ready: None) -> None:
    token = get_token(client)
    response = client.get(
        "/api/v1/predictions/models/nope",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_get_model_503_when_missing_artifacts(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ml_service_module, "MODELS_DIR", tmp_path / "empty")
    _get_model.cache_clear()
    token = get_token(client)
    response = client.get(
        "/api/v1/predictions/models/ptca",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 503
    _get_model.cache_clear()


def test_predict_ok(client: TestClient, ptca_ready: None) -> None:
    token = get_token(client)
    response = client.post(
        "/api/v1/predictions/ptca",
        headers={"Authorization": f"Bearer {token}"},
        json={"values": {"edad": 68, "sexo": "1", "FRhipertension": True}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["cohort"] == "ptca"
    assert "probability" in data
    assert data["risk_level"] in {"bajo", "moderado", "alto"}


def test_predict_unknown_cohort(client: TestClient, ptca_ready: None) -> None:
    token = get_token(client)
    response = client.post(
        "/api/v1/predictions/ghost",
        headers={"Authorization": f"Bearer {token}"},
        json={"values": {}},
    )
    assert response.status_code == 404


def test_predict_503_without_artifacts(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ml_service_module, "MODELS_DIR", tmp_path / "empty")
    _get_model.cache_clear()
    token = get_token(client)
    response = client.post(
        "/api/v1/predictions/ptca",
        headers={"Authorization": f"Bearer {token}"},
        json={"values": {"edad": 60}},
    )
    assert response.status_code == 503
    _get_model.cache_clear()


def test_predict_422_on_value_error(
    client: TestClient,
    ptca_ready: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(self, cohort: str, values: dict):
        raise ValueError("feature inválida")

    monkeypatch.setattr(ml_service_module.MLService, "predict", _boom)
    token = get_token(client)
    response = client.post(
        "/api/v1/predictions/ptca",
        headers={"Authorization": f"Bearer {token}"},
        json={"values": {"edad": "no-num"}},
    )
    assert response.status_code == 422
