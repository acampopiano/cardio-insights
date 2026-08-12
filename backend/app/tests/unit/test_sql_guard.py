"""Matriz de seguridad para sql_guard (defensa en profundidad del chat clínico)."""

from __future__ import annotations

import pytest
from sqlglot import exp, parse_one

from app.services import sql_guard as sql_guard_module
from app.services.sql_guard import UnsafeQueryError, enforce_limit, sanitize, validate_columns, validate_select


def test_validate_select_accepts_simple_select() -> None:
    stmt = validate_select("SELECT COUNT(*) AS n FROM flow_coordina WHERE Realizado = 255")
    assert stmt is not None


def test_validate_select_accepts_join_of_allowed_tables() -> None:
    sql = """
        SELECT f.Cod, d.POestadiaUCI
        FROM flow_coordina f
        JOIN dat_cirugia d ON d.CodCoordina = f.Cod
        WHERE f.Realizado = 255
    """
    stmt = validate_select(sql)
    assert stmt is not None


def test_validate_select_accepts_union_of_selects() -> None:
    sql = """
        SELECT Cod FROM flow_coordina
        UNION
        SELECT Cod FROM call_ptcamaster
    """
    stmt = validate_select(sql)
    assert stmt is not None


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "   ",
        None,
    ],
)
def test_validate_select_rejects_empty(sql: str | None) -> None:
    with pytest.raises(UnsafeQueryError, match="vacía"):
        validate_select(sql)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "sql,match",
    [
        ("DELETE FROM flow_coordina", "SELECT"),
        ("UPDATE flow_coordina SET Realizado = 0", "SELECT"),
        ("INSERT INTO flow_coordina (Cod) VALUES (1)", "SELECT"),
        ("DROP TABLE flow_coordina", "SELECT"),
        ("TRUNCATE TABLE flow_coordina", "SELECT|interpretar|permitida"),
        ("CREATE TABLE evil (id INT)", "SELECT"),
        ("ALTER TABLE flow_coordina ADD COLUMN x INT", "SELECT|interpretar|permitida"),
    ],
)
def test_validate_select_rejects_write_ops(sql: str, match: str) -> None:
    with pytest.raises(UnsafeQueryError, match=match):
        validate_select(sql)


def test_validate_select_rejects_multi_statement() -> None:
    sql = "SELECT Cod FROM flow_coordina; DROP TABLE flow_coordina"
    with pytest.raises(UnsafeQueryError, match="exactamente una sentencia"):
        validate_select(sql)


def test_validate_select_rejects_forbidden_tables_use_users() -> None:
    sql = "SELECT * FROM use_usuarios"
    with pytest.raises(UnsafeQueryError, match="no permitida"):
        validate_select(sql)


def test_validate_select_rejects_mix_allowed_and_forbidden() -> None:
    sql = """
        SELECT f.Cod, u.Clave
        FROM flow_coordina f
        JOIN use_usuarios u ON u.Cod = f.CodPac
    """
    with pytest.raises(UnsafeQueryError, match="no permitida"):
        validate_select(sql)


def test_validate_select_rejects_no_table_reference() -> None:
    with pytest.raises(UnsafeQueryError, match="no referencia ninguna tabla"):
        validate_select("SELECT 1 AS n")


def test_validate_select_rejects_unparseable_sql() -> None:
    with pytest.raises(UnsafeQueryError, match="interpretar"):
        validate_select("SELECT FROM WHERE ;;;%%%")


def test_validate_columns_noop_without_metadata() -> None:
    stmt = validate_select("SELECT f.Cod FROM flow_coordina f")
    validate_columns(stmt, {})  # no debe fallar


def test_validate_columns_accepts_known_qualified_columns() -> None:
    stmt = validate_select("SELECT f.Cod, f.Realizado FROM flow_coordina f")
    validate_columns(
        stmt,
        {"flow_coordina": {"cod", "realizado", "fechacoordina"}},
    )


def test_validate_columns_rejects_unknown_qualified_column() -> None:
    stmt = validate_select("SELECT f.ClaveSecreta FROM flow_coordina f")
    with pytest.raises(UnsafeQueryError, match="inexistente"):
        validate_columns(stmt, {"flow_coordina": {"cod", "realizado"}})


def test_validate_columns_ignores_unqualified_aliases() -> None:
    stmt = validate_select(
        "SELECT COUNT(*) AS total FROM flow_coordina f GROUP BY total"
    )
    # 'total' sin calificar no debe bloquear
    validate_columns(stmt, {"flow_coordina": {"cod"}})


def test_enforce_limit_adds_limit_when_missing() -> None:
    stmt = validate_select("SELECT Cod FROM flow_coordina")
    sql = enforce_limit(stmt, max_rows=100)
    assert "LIMIT 100" in sql.upper()


def test_enforce_limit_caps_excessive_limit() -> None:
    stmt = validate_select("SELECT Cod FROM flow_coordina LIMIT 99999")
    sql = enforce_limit(stmt, max_rows=50)
    assert "LIMIT 50" in sql.upper()
    assert "99999" not in sql


def test_enforce_limit_keeps_smaller_limit() -> None:
    stmt = validate_select("SELECT Cod FROM flow_coordina LIMIT 10")
    sql = enforce_limit(stmt, max_rows=100)
    assert "LIMIT 10" in sql.upper()


def test_sanitize_happy_path() -> None:
    sql = sanitize(
        "SELECT f.Cod FROM flow_coordina f WHERE f.Realizado = 255",
        max_rows=25,
        allowed_columns={"flow_coordina": {"cod", "realizado"}},
    )
    assert "flow_coordina" in sql.lower()
    assert "LIMIT 25" in sql.upper()


def test_sanitize_rejects_forbidden_before_limit() -> None:
    with pytest.raises(UnsafeQueryError, match="no permitida"):
        sanitize("SELECT * FROM use_permisos", max_rows=10)


def test_sanitize_rejects_bad_columns() -> None:
    with pytest.raises(UnsafeQueryError, match="inexistente"):
        sanitize(
            "SELECT f.PasswordHash FROM flow_coordina f",
            max_rows=10,
            allowed_columns={"flow_coordina": {"cod"}},
        )


def test_validate_select_accepts_parenthesized_subquery_root() -> None:
    stmt = validate_select("(SELECT Cod FROM flow_coordina)")
    assert isinstance(stmt, exp.Subquery)


def test_validate_select_rejects_nested_forbidden_ops(monkeypatch: pytest.MonkeyPatch) -> None:
    """SELECT con operación de escritura anidada en el AST (defensa en profundidad)."""
    sel = parse_one("SELECT Cod FROM flow_coordina", read="mysql")
    sel.set("limit", exp.Delete(this=exp.table_("flow_coordina")))

    monkeypatch.setattr(sql_guard_module.sqlglot, "parse", lambda sql, read=None: [sel])
    with pytest.raises(UnsafeQueryError, match="no permitida"):
        validate_select("SELECT Cod FROM flow_coordina")


def test_validate_columns_skips_unresolved_qualifier() -> None:
    stmt = validate_select("SELECT x.Cod FROM flow_coordina f")
    validate_columns(stmt, {"flow_coordina": {"cod"}})


def test_validate_columns_skips_table_without_metadata() -> None:
    stmt = validate_select(
        "SELECT f.Cod, d.k_id FROM flow_coordina f "
        "JOIN dat_cirugia d ON d.CodCoordina = f.Cod"
    )
    # Solo hay metadata de flow_coordina; dat_cirugia se omite sin bloquear.
    validate_columns(stmt, {"flow_coordina": {"cod"}})


def test_validate_columns_skips_table_nodes_without_name() -> None:
    stmt = parse_one("SELECT f.Cod FROM flow_coordina f", read="mysql")
    stmt.find(exp.Table).set("this", None)
    validate_columns(stmt, {"flow_coordina": {"cod"}})


def test_enforce_limit_when_limit_expression_is_not_int() -> None:
    stmt = validate_select("SELECT Cod FROM flow_coordina LIMIT 1 + 2")
    sql = enforce_limit(stmt, max_rows=10)
    assert "LIMIT 10" in sql.upper()


def test_sanitize_without_column_metadata() -> None:
    sql = sanitize("SELECT Cod FROM flow_coordina", max_rows=5)
    assert "LIMIT 5" in sql.upper()
