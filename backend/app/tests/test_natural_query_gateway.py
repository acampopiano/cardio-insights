import os
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.schemas.natural_query import NaturalQueryGatewayResponse
from app.services.llm_gateway_client import LLMGatewayClient

client = TestClient(app)


def _get_token(username: str = "clinician", password: str = "Demo1234!") -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _set_gateway(enabled: bool) -> None:
    os.environ["LLM_GATEWAY_ENABLED"] = "true" if enabled else "false"
    os.environ["LLM_GATEWAY_URL"] = "http://127.0.0.1:8000"
    os.environ["LLM_GATEWAY_TIMEOUT_SECONDS"] = "0.05"
    get_settings.cache_clear()


def _reset_gateway() -> None:
    os.environ.pop("LLM_GATEWAY_ENABLED", None)
    os.environ.pop("LLM_GATEWAY_URL", None)
    os.environ.pop("LLM_GATEWAY_TIMEOUT_SECONDS", None)
    get_settings.cache_clear()


def _mock_gateway_trend() -> NaturalQueryGatewayResponse:
    return NaturalQueryGatewayResponse(
        resolved=True,
        source="llm",
        intent="trend",
        metric="avg_wait_days",
        endpoint="/api/v1/kpis/query",
        translated_payload={
            "intent": "trend",
            "metric": "avg_wait_days",
            "granularity": "month",
            "period": {"type": "current_year"},
        },
        assumptions=["Se interpreto la consulta como tendencia."],
        confidence=0.88,
    )


def _mock_gateway_ranking() -> NaturalQueryGatewayResponse:
    return NaturalQueryGatewayResponse(
        resolved=True,
        source="llm",
        intent="ranking",
        metric="surgery_volume",
        endpoint="/api/v1/analytics/query",
        translated_payload={
            "intent": "ranking",
            "metric": "surgery_volume",
            "granularity": "month",
            "period": {"type": "current_year"},
            "limit": 3,
        },
        assumptions=["Se interpreto la consulta como ranking."],
        confidence=0.81,
    )


def test_gateway_responde_correctamente(monkeypatch) -> None:
    _set_gateway(True)
    token = _get_token()

    def _fake_interpret(self: LLMGatewayClient, question: str, use_llm_fallback: bool = True):
        assert question
        assert use_llm_fallback is True
        return _mock_gateway_trend(), None

    monkeypatch.setattr(LLMGatewayClient, "interpret", _fake_interpret)

    try:
        response = client.post(
            "/api/v1/natural-query/run",
            json={"question": "Como viene la espera promedio este ano?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "llm"
        assert data["resolved"] is True
        assert data["intent"] == "trend"
        assert data["endpoint"] == "/api/v1/kpis/query"
        assert data["metric"] == "avg_wait_days"
        assert "result" in data
    finally:
        _reset_gateway()


def test_gateway_no_disponible(monkeypatch) -> None:
    _set_gateway(True)
    token = _get_token()

    def _fake_interpret(self: LLMGatewayClient, question: str, use_llm_fallback: bool = True):
        return None, "No se pudo conectar al LLM Gateway."

    monkeypatch.setattr(LLMGatewayClient, "interpret", _fake_interpret)

    try:
        response = client.post(
            "/api/v1/natural-query/run",
            json={"question": "Como viene la espera promedio este ano?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "rules"
        assert any("No se pudo conectar" in item for item in data["errors"])
    finally:
        _reset_gateway()


def test_gateway_endpoint_invalido(monkeypatch) -> None:
    _set_gateway(True)
    token = _get_token()

    def _fake_interpret(self: LLMGatewayClient, question: str, use_llm_fallback: bool = True):
        return (
            NaturalQueryGatewayResponse(
                resolved=True,
                source="llm",
                intent="trend",
                metric="avg_wait_days",
                endpoint="/api/v1/otro/endpoint",
                translated_payload={
                    "intent": "trend",
                    "metric": "avg_wait_days",
                    "granularity": "month",
                    "period": {"type": "current_year"},
                },
            ),
            None,
        )

    monkeypatch.setattr(LLMGatewayClient, "interpret", _fake_interpret)

    try:
        response = client.post(
            "/api/v1/natural-query/run",
            json={"question": "Como viene la espera promedio este ano?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "rules"
        assert any("Endpoint invalido" in item for item in data["errors"])
    finally:
        _reset_gateway()


def test_gateway_metric_invalida(monkeypatch) -> None:
    _set_gateway(True)
    token = _get_token()

    def _fake_interpret(self: LLMGatewayClient, question: str, use_llm_fallback: bool = True):
        return (
            NaturalQueryGatewayResponse(
                resolved=True,
                source="llm",
                intent="trend",
                metric="metric_no_existente",
                endpoint="/api/v1/kpis/query",
                translated_payload={
                    "intent": "trend",
                    "metric": "metric_no_existente",
                    "granularity": "month",
                    "period": {"type": "current_year"},
                },
            ),
            None,
        )

    monkeypatch.setattr(LLMGatewayClient, "interpret", _fake_interpret)

    try:
        response = client.post(
            "/api/v1/natural-query/run",
            json={"question": "Como viene la espera promedio este ano?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "rules"
        assert any("Metrica no permitida" in item for item in data["errors"])
    finally:
        _reset_gateway()


def test_gateway_consulta_trend_valida(monkeypatch) -> None:
    _set_gateway(True)
    token = _get_token()

    def _fake_interpret(self: LLMGatewayClient, question: str, use_llm_fallback: bool = True):
        return _mock_gateway_trend(), None

    monkeypatch.setattr(LLMGatewayClient, "interpret", _fake_interpret)

    try:
        response = client.post(
            "/api/v1/natural-query/run",
            json={"question": "Como viene la espera promedio este ano?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "llm"
        assert data["intent"] == "trend"
        assert data["endpoint"] == "/api/v1/kpis/query"
        assert data["payload"]["kpi_keys"] == ["avg_wait_days"]
    finally:
        _reset_gateway()


def test_gateway_consulta_ranking_valida(monkeypatch) -> None:
    _set_gateway(True)
    token = _get_token()

    def _fake_interpret(self: LLMGatewayClient, question: str, use_llm_fallback: bool = True):
        return _mock_gateway_ranking(), None

    monkeypatch.setattr(LLMGatewayClient, "interpret", _fake_interpret)

    try:
        response = client.post(
            "/api/v1/natural-query/run",
            json={"question": "Top meses con mayor volumen"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "llm"
        assert data["intent"] == "ranking"
        assert data["endpoint"] == "/api/v1/analytics/query"
        assert data["payload"]["widget_type"] == "ranking"
    finally:
        _reset_gateway()


def test_gateway_timeout(monkeypatch) -> None:
    _set_gateway(True)
    token = _get_token()

    def _fake_interpret(self: LLMGatewayClient, question: str, use_llm_fallback: bool = True):
        return None, "Timeout consultando LLM Gateway (0.05s)."

    monkeypatch.setattr(LLMGatewayClient, "interpret", _fake_interpret)

    try:
        response = client.post(
            "/api/v1/natural-query/run",
            json={"question": "Como viene la espera promedio este ano?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "rules"
        assert any("Timeout" in item for item in data["errors"])
    finally:
        _reset_gateway()


def test_gateway_period_year_sin_type_aplica_filtros(monkeypatch) -> None:
    _set_gateway(True)
    token = _get_token()

    def _fake_interpret(self: LLMGatewayClient, question: str, use_llm_fallback: bool = True):
        return (
            NaturalQueryGatewayResponse(
                resolved=True,
                source="llm",
                intent="trend",
                metric="avg_wait_days",
                endpoint="/api/v1/kpis/query",
                translated_payload={
                    "intent": "trend",
                    "metric": "avg_wait_days",
                    "granularity": "month",
                    "period": {"year": 2025},
                },
            ),
            None,
        )

    monkeypatch.setattr(LLMGatewayClient, "interpret", _fake_interpret)

    try:
        response = client.post(
            "/api/v1/natural-query/run",
            json={"question": "Cual fue la espera promedio para el ano 2025"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "llm"
        assert data["payload"]["filters"] == [
            {"key": "date_from", "values": ["2025-01-01"]},
            {"key": "date_to", "values": ["2025-12-31"]},
        ]
    finally:
        _reset_gateway()


def test_gateway_refina_filtro_anual_si_pregunta_indica_rango_meses(monkeypatch) -> None:
    _set_gateway(True)
    token = _get_token()

    def _fake_interpret(self: LLMGatewayClient, question: str, use_llm_fallback: bool = True):
        return (
            NaturalQueryGatewayResponse(
                resolved=True,
                source="llm",
                intent="ranking",
                metric="avg_wait_days",
                endpoint="/api/v1/analytics/query",
                translated_payload={
                    "intent": "ranking",
                    "metric": "avg_wait_days",
                    "granularity": "month",
                    "period": {"year": 2025},
                    "limit": 10,
                },
            ),
            None,
        )

    monkeypatch.setattr(LLMGatewayClient, "interpret", _fake_interpret)

    try:
        response = client.post(
            "/api/v1/natural-query/run",
            json={
                "question": "Como se comporto la demora quirurgica entre marzo y agosto de 2025, y en que mes pego el salto mas fuerte?"
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "llm"
        assert data["payload"]["filters"] == [
            {"key": "date_from", "values": ["2025-03-01"]},
            {"key": "date_to", "values": ["2025-08-31"]},
        ]
    finally:
        _reset_gateway()


def test_gateway_comparacion_trimestre_filtra_solo_q1_entre_anos(monkeypatch) -> None:
    _set_gateway(True)
    token = _get_token()

    def _fake_interpret(self: LLMGatewayClient, question: str, use_llm_fallback: bool = True):
        return (
            NaturalQueryGatewayResponse(
                resolved=True,
                source="rules",
                intent="comparison",
                metric="avg_wait_days",
                endpoint="/api/v1/kpis/query",
                translated_payload={
                    "intent": "comparison",
                    "metric": "avg_wait_days",
                    "granularity": "month",
                    "period": {"year": 2026},
                },
            ),
            None,
        )

    monkeypatch.setattr(LLMGatewayClient, "interpret", _fake_interpret)

    try:
        response = client.post(
            "/api/v1/natural-query/run",
            json={
                "question": "Comparame el promedio de espera del primer trimestre 2026 contra el primer trimestre 2025"
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "rules"
        assert data["payload"]["filters"] == [
            {"key": "date_from", "values": ["2025-01-01"]},
            {"key": "date_to", "values": ["2026-03-31"]},
        ]
        periods = [point["period"] for point in data["result"]["series"][0]["points"]]
        assert periods
        for period in periods:
            year, month = period.split("-")
            assert year in {"2025", "2026"}
            assert month in {"01", "02", "03"}
    finally:
        _reset_gateway()


def test_gateway_ultimos_90_dias_completa_filtros_desde_pregunta(monkeypatch) -> None:
    _set_gateway(True)
    token = _get_token()

    def _fake_interpret(self: LLMGatewayClient, question: str, use_llm_fallback: bool = True):
        return (
            NaturalQueryGatewayResponse(
                resolved=True,
                source="llm",
                intent="trend",
                metric="avg_wait_days",
                endpoint="/api/v1/kpis/query",
                translated_payload={
                    "intent": "trend",
                    "metric": "avg_wait_days",
                    "granularity": "month",
                    "period": {},
                    "filters": [],
                },
            ),
            None,
        )

    monkeypatch.setattr(LLMGatewayClient, "interpret", _fake_interpret)

    today = datetime.now(UTC).date()
    expected_from = (today - timedelta(days=89)).isoformat()
    expected_to = today.isoformat()

    try:
        response = client.post(
            "/api/v1/natural-query/run",
            json={
                "question": "Si miramos los ultimos 90 dias, cual KPI muestra el deterioro mas marcado y desde cuando empezo la tendencia?"
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "llm"
        assert data["payload"]["filters"] == [
            {"key": "date_from", "values": [expected_from]},
            {"key": "date_to", "values": [expected_to]},
        ]
    finally:
        _reset_gateway()


def test_fallback_controlado_con_gateway_deshabilitado(monkeypatch) -> None:
    _set_gateway(False)
    token = _get_token()

    def _must_not_call(self: LLMGatewayClient, question: str, use_llm_fallback: bool = True):
        raise AssertionError("No deberia invocarse gateway si LLM_GATEWAY_ENABLED=false")

    monkeypatch.setattr(LLMGatewayClient, "interpret", _must_not_call)

    try:
        response = client.post(
            "/api/v1/natural-query/run",
            json={"question": "Como viene la espera promedio este ano?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "rules"
        assert data["resolved"] is True
    finally:
        _reset_gateway()
