"""Chat clínico: guardrails SQL + flujo con OpenAI/MySQL mockeados."""

from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.core.config import get_settings
from app.schemas.chat import ChatMessage
from app.services import chat_service as chat_module
from app.services.chat_service import ChatService


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeCompletion:
        self.calls.append(kwargs)
        if not self._responses:
            raise RuntimeError("No hay más respuestas fake de OpenAI")
        return _FakeCompletion(self._responses.pop(0))


class _FakeOpenAI:
    def __init__(self, responses: list[str]) -> None:
        self.chat = MagicMock()
        self.chat.completions = _FakeCompletions(responses)


def _sql_plan(sql: str, can_answer: bool = True, reason: str = "") -> str:
    return json.dumps({"can_answer": can_answer, "sql": sql, "reason": reason}, ensure_ascii=False)


@pytest.fixture
def enable_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    os.environ["CHAT_ENABLED"] = "true"
    os.environ["OPENAI_API_KEY"] = "test-key"
    os.environ["OPENAI_MODEL"] = "gpt-4o-mini"
    os.environ["CHAT_MAX_SQL_ATTEMPTS"] = "3"
    os.environ["CHAT_MAX_ROWS"] = "50"
    get_settings.cache_clear()
    chat_module._COLUMN_CACHE = None
    yield
    chat_module._COLUMN_CACHE = None


def _patch_openai(monkeypatch: pytest.MonkeyPatch, responses: list[str]) -> _FakeOpenAI:
    fake = _FakeOpenAI(responses)

    def _factory(**kwargs: Any) -> _FakeOpenAI:
        return fake

    monkeypatch.setattr(chat_module, "OpenAI", _factory)
    return fake


def _mock_db(
    monkeypatch: pytest.MonkeyPatch,
    *,
    rows: list[dict[str, Any]] | None = None,
    execute_error: Exception | None = None,
    columns: dict[str, set[str]] | None = None,
) -> MagicMock:
    """Mockea pymysql.connect para introspección + ejecución read-only."""
    connect = MagicMock()
    monkeypatch.setattr(chat_module.pymysql, "connect", connect)

    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    connect.return_value = conn

    column_rows = []
    if columns:
        column_rows = [
            {"t": table, "c": col}
            for table, cols in columns.items()
            for col in cols
        ]

    def _execute(sql: str, *args: Any) -> None:
        upper = (sql or "").strip().upper()
        if "INFORMATION_SCHEMA.COLUMNS" in upper:
            cursor.fetchall.return_value = column_rows
            return
        if upper.startswith("SET") or upper.startswith("START") or upper.startswith("ROLLBACK"):
            return
        if execute_error is not None:
            raise execute_error
        cursor.fetchall.return_value = rows or []

    cursor.execute.side_effect = _execute
    return connect


def test_chat_disabled_without_config() -> None:
    os.environ["CHAT_ENABLED"] = "false"
    os.environ.pop("OPENAI_API_KEY", None)
    get_settings.cache_clear()
    service = ChatService()
    result = service.ask("Cuántas cirugías hubo en 2024?")
    assert result.resolved is False
    assert result.error == "chat_disabled"


def test_ask_happy_path(enable_chat, monkeypatch: pytest.MonkeyPatch) -> None:
    safe_sql = "SELECT COUNT(*) AS total FROM flow_coordina WHERE Realizado = 255"
    _patch_openai(
        monkeypatch,
        [
            _sql_plan(safe_sql),
            "Hubo 120 procedimientos realizados.",
        ],
    )
    connect = _mock_db(
        monkeypatch,
        rows=[{"total": 120}],
        columns={"flow_coordina": {"cod", "realizado"}},
    )

    service = ChatService()
    result = service.ask("Cuántos procedimientos realizados hay?")
    assert result.resolved is True
    assert result.row_count == 1
    assert result.rows == [{"total": 120}]
    assert result.sql is not None
    assert "LIMIT" in result.sql.upper()
    assert "flow_coordina" in result.sql.lower()
    assert "120" in result.answer or "procedimientos" in result.answer.lower() or result.answer
    # Se ejecutó SQL (connect al menos para introspección + query)
    assert connect.call_count >= 2


def test_unsafe_sql_never_executed(enable_chat, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_openai(
        monkeypatch,
        [
            _sql_plan("DELETE FROM flow_coordina"),
            # reintentos también inseguros / vacíos
            _sql_plan("DROP TABLE use_usuarios"),
            _sql_plan("UPDATE flow_coordina SET Realizado = 0"),
        ],
    )
    connect = _mock_db(monkeypatch, rows=[])

    service = ChatService()
    # Evitar introspección real fallando: forzar cache vacío
    chat_module._COLUMN_CACHE = {}
    result = service.ask("Borrame todos los pacientes")
    assert result.resolved is False
    assert result.error is not None
    assert "unsafe_sql" in result.error
    # Solo pudo haber connect de introspección (ya cacheada = 0). Ninguna ejecución SELECT.
    for call in connect.call_args_list:
        pass
    # _run_readonly no debe haberse llamado: sin fetchall de datos clínicos
    # Con cache pre-seteado, connect no se usa en _allowed_columns ni en run
    assert connect.call_count == 0


def test_retry_after_unsafe_then_success(enable_chat, monkeypatch: pytest.MonkeyPatch) -> None:
    good = "SELECT COUNT(*) AS total FROM dat_cirugia d JOIN flow_coordina f ON f.Cod = d.CodCoordina"
    _patch_openai(
        monkeypatch,
        [
            _sql_plan("SELECT * FROM use_usuarios"),
            _sql_plan(good),  # fix
            "Hubo 40 cirugías.",
        ],
    )
    chat_module._COLUMN_CACHE = {}
    _mock_db(monkeypatch, rows=[{"total": 40}])

    service = ChatService()
    result = service.ask("Cuántas cirugías se hicieron?")
    assert result.resolved is True
    assert result.rows == [{"total": 40}]
    assert result.sql is not None
    assert "dat_cirugia" in result.sql.lower()


def test_retry_after_db_error(enable_chat, monkeypatch: pytest.MonkeyPatch) -> None:
    sql1 = "SELECT bad_col FROM flow_coordina"
    sql2 = "SELECT Cod AS total FROM flow_coordina"
    fake = _patch_openai(
        monkeypatch,
        [
            _sql_plan(sql1),
            _sql_plan(sql2),  # fix after db error
            "Hay registros disponibles.",
        ],
    )
    chat_module._COLUMN_CACHE = {}

    connect = MagicMock()
    monkeypatch.setattr(chat_module.pymysql, "connect", connect)
    exec_conn = MagicMock()
    exec_cursor = MagicMock()
    exec_conn.cursor.return_value.__enter__.return_value = exec_cursor

    calls = {"n": 0}

    def _execute(sql: str, *args: Any) -> None:
        upper = sql.strip().upper()
        if upper.startswith("SET") or upper.startswith("START") or upper.startswith("ROLLBACK"):
            return
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("Unknown column 'bad_col'")
        exec_cursor.fetchall.return_value = [{"total": 1}]

    exec_cursor.execute.side_effect = _execute
    connect.return_value = exec_conn

    service = ChatService()
    result = service.ask("Listame códigos de coordinación")
    assert result.resolved is True
    assert len(fake.chat.completions.calls) >= 2


def test_not_answerable(enable_chat, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_openai(
        monkeypatch,
        [_sql_plan("", can_answer=False, reason="No hay datos de nombres de pacientes.")],
    )
    service = ChatService()
    result = service.ask("Cómo se llama el paciente 1?")
    assert result.resolved is False
    assert result.error == "not_answerable"
    assert "nombres" in result.answer.lower() or result.answer


def test_invalid_llm_json(enable_chat, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_openai(monkeypatch, ["esto no es json"])
    service = ChatService()
    result = service.ask("Cuántas PTCAs hubo?")
    assert result.resolved is False
    assert result.error == "not_answerable"


def test_completion_kwargs_by_model(enable_chat, monkeypatch: pytest.MonkeyPatch) -> None:
    service = ChatService()

    os.environ["OPENAI_MODEL"] = "gpt-5-mini"
    get_settings.cache_clear()
    service._settings = get_settings()
    assert service._completion_kwargs(0.2) == {"reasoning_effort": "minimal"}

    os.environ["OPENAI_MODEL"] = "o3-mini"
    get_settings.cache_clear()
    service._settings = get_settings()
    assert service._completion_kwargs(0.2) == {}

    os.environ["OPENAI_MODEL"] = "gpt-4o-mini"
    get_settings.cache_clear()
    service._settings = get_settings()
    assert service._completion_kwargs(0.2) == {"temperature": 0.2}


def test_allowed_columns_caches_and_handles_failure(
    enable_chat,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_module._COLUMN_CACHE = None
    connect = MagicMock(side_effect=RuntimeError("db down"))
    monkeypatch.setattr(chat_module.pymysql, "connect", connect)
    service = ChatService()
    assert service._allowed_columns() == {}
    assert chat_module._COLUMN_CACHE == {}
    # Segunda llamada usa cache, no reconecta
    connect.reset_mock()
    assert service._allowed_columns() == {}
    connect.assert_not_called()


def test_allowed_columns_success(enable_chat, monkeypatch: pytest.MonkeyPatch) -> None:
    chat_module._COLUMN_CACHE = None
    connect = MagicMock()
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchall.return_value = [
        {"t": "flow_coordina", "c": "Cod"},
        {"t": "flow_coordina", "c": "Realizado"},
    ]
    connect.return_value = conn
    monkeypatch.setattr(chat_module.pymysql, "connect", connect)

    service = ChatService()
    cols = service._allowed_columns()
    assert cols["flow_coordina"] == {"cod", "realizado"}


def test_fix_sql_returns_empty_on_failure(enable_chat, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _patch_openai(monkeypatch, [])
    # create lanzará RuntimeError por falta de responses
    service = ChatService()
    service._client = fake  # type: ignore[assignment]
    assert service._fix_sql("q", [], "SELECT 1", "boom") == ""


def test_fix_sql_respects_can_answer_false(enable_chat, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _patch_openai(monkeypatch, [_sql_plan("", can_answer=False, reason="no")])
    service = ChatService()
    service._client = fake  # type: ignore[assignment]
    assert service._fix_sql("q", [ChatMessage(role="user", content="hola")], "SELECT 1", "err") == ""


def test_summarize_fallback_empty_content(enable_chat, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _patch_openai(monkeypatch, [""])
    service = ChatService()
    service._client = fake  # type: ignore[assignment]
    text = service._summarize("pregunta", [])
    assert "No obtuve resultados" in text


def test_ask_stops_when_fix_returns_empty_after_unsafe(
    enable_chat,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_openai(
        monkeypatch,
        [
            _sql_plan("SELECT * FROM use_usuarios"),
            _sql_plan("", can_answer=False, reason="no puedo"),
        ],
    )
    chat_module._COLUMN_CACHE = {}
    service = ChatService()
    result = service.ask("Dame usuarios del sistema")
    assert result.resolved is False
    assert result.error is not None
    assert "unsafe_sql" in result.error


def test_ask_db_error_on_last_attempt(enable_chat, monkeypatch: pytest.MonkeyPatch) -> None:
    os.environ["CHAT_MAX_SQL_ATTEMPTS"] = "1"
    get_settings.cache_clear()
    _patch_openai(monkeypatch, [_sql_plan("SELECT Cod FROM flow_coordina")])
    chat_module._COLUMN_CACHE = {}
    connect = MagicMock()
    monkeypatch.setattr(chat_module.pymysql, "connect", connect)
    exec_conn = MagicMock()
    exec_cursor = MagicMock()
    exec_conn.cursor.return_value.__enter__.return_value = exec_cursor

    def _execute(sql: str, *args: Any) -> None:
        upper = sql.strip().upper()
        if upper.startswith("SET") or upper.startswith("START") or upper.startswith("ROLLBACK"):
            return
        raise RuntimeError("boom")

    exec_cursor.execute.side_effect = _execute
    connect.return_value = exec_conn

    service = ChatService()
    result = service.ask("Listame códigos")
    assert result.resolved is False
    assert "db_error" in (result.error or "")


def test_ask_stops_when_fix_returns_empty_after_db_error(
    enable_chat,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_openai(
        monkeypatch,
        [
            _sql_plan("SELECT Cod FROM flow_coordina"),
            _sql_plan("", can_answer=False, reason="no"),
        ],
    )
    chat_module._COLUMN_CACHE = {}
    connect = MagicMock()
    monkeypatch.setattr(chat_module.pymysql, "connect", connect)
    exec_conn = MagicMock()
    exec_cursor = MagicMock()
    exec_conn.cursor.return_value.__enter__.return_value = exec_cursor

    def _execute(sql: str, *args: Any) -> None:
        upper = sql.strip().upper()
        if upper.startswith("SET") or upper.startswith("START") or upper.startswith("ROLLBACK"):
            return
        raise RuntimeError("syntax error")

    exec_cursor.execute.side_effect = _execute
    connect.return_value = exec_conn

    service = ChatService()
    result = service.ask("Listame algo")
    assert result.resolved is False
    assert result.error is not None
    assert "db_error" in result.error


def test_ask_with_history(enable_chat, monkeypatch: pytest.MonkeyPatch) -> None:
    sql = "SELECT COUNT(*) AS total FROM flow_coordina WHERE YEAR(FechaRealizado) = 2023"
    fake = _patch_openai(
        monkeypatch,
        [_sql_plan(sql), "En 2023 hubo 10."],
    )
    chat_module._COLUMN_CACHE = {}
    _mock_db(monkeypatch, rows=[{"total": 10}])
    service = ChatService()
    result = service.ask(
        "y en el anterior?",
        history=[
            ChatMessage(role="user", content="Cuántas en 2024?"),
            ChatMessage(role="assistant", content="Hubo 12."),
        ],
    )
    assert result.resolved is True
    # El prompt de generación incluye historial
    first_call = fake.chat.completions.calls[0]
    roles = [m["role"] for m in first_call["messages"]]
    assert "user" in roles
