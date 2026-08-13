"""Guardrails para SQL generado por el LLM antes de ejecutarlo.

La barrera de seguridad principal es el usuario MySQL de solo lectura. Esta capa
es defensa en profundidad: garantiza que solo se ejecute un único SELECT sobre
las tablas permitidas, y fuerza un LIMIT.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp

# Tablas clínicas que el chat puede consultar. Excluye intencionalmente las
# tablas use_* (usuarios, claves, permisos).
ALLOWED_TABLES: frozenset[str] = frozenset(
    {
        "flow_coordina",
        "dat_cirugia",
        "call_ptcamaster",
        "flow_procedimientocardiologia",
        "sqlsalud_fallece",
    }
)

_FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
    exp.Command,
    exp.Set,
    exp.Use,
)


class UnsafeQueryError(ValueError):
    """Se levanta cuando el SQL no pasa las validaciones de seguridad."""


def validate_select(sql: str) -> exp.Expression:
    """Valida que `sql` sea un único SELECT sobre tablas permitidas.

    Devuelve el AST parseado. Levanta UnsafeQueryError si no es seguro.
    """
    raw = (sql or "").strip()
    if not raw:
        raise UnsafeQueryError("La consulta está vacía.")

    try:
        statements = sqlglot.parse(raw, read="mysql")
    except Exception as exc:  # noqa: BLE001 - cualquier error de parseo es inseguro
        raise UnsafeQueryError(f"No se pudo interpretar el SQL: {exc}") from exc

    statements = [stmt for stmt in statements if stmt is not None]
    if len(statements) != 1:
        raise UnsafeQueryError("Se permite exactamente una sentencia SQL.")

    stmt = statements[0]

    # El nodo raíz debe ser un SELECT (o un SELECT envuelto en paréntesis/CTE).
    root = stmt
    if isinstance(root, exp.Subquery):
        root = root.this
    if not isinstance(root, (exp.Select, exp.Union)):
        raise UnsafeQueryError("Solo se permiten consultas SELECT.")

    # Ninguna operación de escritura/comando, ni siquiera anidada.
    for node_type in _FORBIDDEN_NODES:
        if stmt.find(node_type) is not None:
            raise UnsafeQueryError("La consulta contiene una operación no permitida.")

    # Todas las tablas referenciadas deben estar en la allowlist.
    referenced = {table.name.lower() for table in stmt.find_all(exp.Table) if table.name}
    not_allowed = referenced - ALLOWED_TABLES
    if not_allowed:
        raise UnsafeQueryError(f"Tabla(s) no permitida(s): {', '.join(sorted(not_allowed))}.")
    if not referenced:
        raise UnsafeQueryError("La consulta no referencia ninguna tabla permitida.")

    return stmt


def validate_columns(stmt: exp.Expression, columns_by_table: dict[str, set[str]]) -> None:
    """Verifica que las columnas calificadas (alias.columna) existan en su tabla.

    Solo valida referencias calificadas (con prefijo de tabla/alias), porque son
    resolubles sin ambigüedad. Las columnas sin calificar suelen ser alias de salida
    (ej. `GROUP BY mes`) y se omiten para no generar falsos positivos. Si no hay
    metadata de columnas, no valida nada (la ejecución y el reintento cubren el resto).
    """
    if not columns_by_table:
        return

    # alias/nombre de tabla -> nombre real de tabla (en minúsculas).
    alias_to_table: dict[str, str] = {}
    for table in stmt.find_all(exp.Table):
        real = (table.name or "").lower()
        if not real:
            continue
        alias = (table.alias or table.name or "").lower()
        alias_to_table[alias] = real

    unknown: set[str] = set()
    for col in stmt.find_all(exp.Column):
        qualifier = (col.table or "").lower()
        name = (col.name or "").lower()
        if not qualifier or not name or name == "*":
            continue
        real = alias_to_table.get(qualifier)
        if real is None:
            continue  # qualifier no resoluble (subconsulta, etc.): no bloquear
        valid = columns_by_table.get(real)
        if valid is None:
            continue  # sin metadata para esa tabla
        if name not in valid:
            unknown.add(f"{col.table}.{col.name}")

    if unknown:
        raise UnsafeQueryError(f"Columna(s) inexistente(s): {', '.join(sorted(unknown))}.")


def enforce_limit(stmt: exp.Expression, max_rows: int) -> str:
    """Devuelve el SQL final asegurando un LIMIT no mayor a `max_rows`."""
    limit = stmt.args.get("limit") if isinstance(stmt, exp.Select) else None

    current_limit: int | None = None
    if isinstance(limit, exp.Limit):
        try:
            current_limit = int(limit.expression.this)  # type: ignore[union-attr]
        except (AttributeError, TypeError, ValueError):
            current_limit = None

    if current_limit is None or current_limit > max_rows:
        stmt = stmt.limit(max_rows)

    return stmt.sql(dialect="mysql")


def sanitize(
    sql: str,
    max_rows: int,
    allowed_columns: dict[str, set[str]] | None = None,
) -> str:
    """Valida y normaliza el SQL, devolviendo la sentencia segura a ejecutar.

    Si se provee `allowed_columns` ({tabla: {columnas}}), valida que las columnas
    calificadas existan; si no, omite esa verificación.
    """
    stmt = validate_select(sql)
    if allowed_columns:
        validate_columns(stmt, allowed_columns)
    return enforce_limit(stmt, max_rows)
