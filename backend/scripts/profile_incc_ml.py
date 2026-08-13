"""Fase 0 (Machine Learning): perfilado del esquema real de `incc`.

Objetivo: descubrir qué variables clínicas existen de verdad y cuáles sirven
como predictores/target para el primer modelo (mortalidad), SIN entrenar nada
todavía. Solo lee metadata y estadísticas de calidad de dato.

Qué reporta, por cada tabla clínica relevante:
  1. Cantidad de filas.
  2. TODAS las columnas (nombre + tipo) desde INFORMATION_SCHEMA -> sirve para
     descubrir factores de riesgo/comorbilidades desconocidos (sobre todo en
     pvd_master, dat_cirugia, pac_ficha).
  3. Perfil de calidad de columnas candidatas: % de centinelas/nulos, cantidad
     de valores distintos, min/max. Los centinelas de esta base son:
        - fechas <= '1900-01-01'  -> nulo lógico
        - numéricos = -99          -> "sin dato"
        - flags tinyint = 255      -> "sin dato"
  4. Balance del target de mortalidad (base rate), imprescindible para saber
     cuán desbalanceado está el problema.

Uso (solo lectura; no modifica nada):
    # contra la base local del docker (seed)
    python scripts/profile_incc_ml.py

    # contra la base real (ajustá host/credenciales por variables de entorno)
    set INCC_MYSQL_HOST=190.64.90.170
    set INCC_MYSQL_PORT=3306
    set INCC_MYSQL_USER=<usuario_lectura>
    set INCC_MYSQL_PASSWORD=<password>
    set INCC_MYSQL_DB=incc
    python scripts/profile_incc_ml.py --json perfil_incc.json

Requiere: pymysql (ya está en requirements.txt).
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

# --------------------------------------------------------------------------
# Conexión (configurable por entorno; defaults = base local del docker).
# --------------------------------------------------------------------------
DB_CONFIG = {
    "host": os.getenv("INCC_MYSQL_HOST", "localhost"),
    "port": int(os.getenv("INCC_MYSQL_PORT", "3306")),
    "user": os.getenv("INCC_MYSQL_USER", "cardio"),
    "password": os.getenv("INCC_MYSQL_PASSWORD", "cardio"),
    "database": os.getenv("INCC_MYSQL_DB", "incc"),
}

# Tablas clínicas relevantes y cómo se unen al núcleo (flow_coordina).
# El join se documenta para armar después el SQL de extracción del dataset.
RELEVANT_TABLES = {
    "flow_coordina": "núcleo: una fila por acto coordinado (PK Cod)",
    "pac_ficha": "paciente (PK Cod). Join: flow_coordina.CodPac = pac_ficha.Cod",
    "dat_cirugia": "cirugía. Join: dat_cirugia.CodCoordina = flow_coordina.Cod",
    "call_ptcamaster": "PTCA. Join: call_ptcamaster.CodCoordina = flow_coordina.Cod",
    "pvd_master": "formulario perioperatorio. Join: pvd_master.CodFlow = flow_coordina.Cod",
    "flow_procedimientocardiologia": "desenlaces (egreso/fallece). Join por CodCoordina",
}

# Columnas candidatas a perfilar en detalle, con el tipo de centinela a medir.
# 'date'  -> cuenta <= '1900-01-01'
# 'num'   -> cuenta = -99 y también negativos
# 'flag'  -> cuenta = 255
# 'plain' -> solo NULL + distintos (categórica/código)
CANDIDATE_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "flow_coordina": [
        ("EdadCoo", "num"),
        ("CodSeguroCoo", "plain"),
        ("CodCoordinaReglaMotivo", "plain"),
        ("FechaCoordina", "date"),
        ("FechaRealizado", "date"),
        ("FechaEgreso", "date"),
        ("Realizado", "flag"),
        ("Autorizado", "flag"),
    ],
    "pac_ficha": [
        ("FecNace", "date"),
        ("CodSexo", "plain"),
        ("Fallecio", "plain"),
    ],
    "dat_cirugia": [
        # POestadiaUCI y CIO* son POSToperatorios (leakage para mortalidad);
        # se perfilan solo para documentar calidad de dato.
        ("POestadiaUCI", "num"),
        ("CIOstroke", "flag"),
        ("CIOsepsis", "flag"),
        ("CIOfallaRenalAguda", "flag"),
    ],
    "call_ptcamaster": [
        # Features pre-procedimiento (FR* factores de riesgo, CE* cuadro de entrada)
        ("FRhipertension", "plain"),
        ("FRdiabetes", "plain"),
        ("FRdislipemia", "plain"),
        ("FRimc", "num"),
        ("FRldl", "num"),
        ("CEinsRenal", "plain"),
        ("CEfuncVentricular", "plain"),
        ("CEangorInestable", "plain"),
        ("CEiamCurso", "plain"),
        ("CEtasaFiltracionGlomecular", "num"),
        # Target de mortalidad PTCA (255 = falleció)
        ("IPfallece", "flag"),
        ("PPfallece", "flag"),
    ],
    "flow_procedimientocardiologia": [
        ("FechaEgreso", "date"),
        ("FechaFallece", "date"),
    ],
}


def connect() -> pymysql.connections.Connection:
    return pymysql.connect(cursorclass=DictCursor, autocommit=True, read_timeout=60, **DB_CONFIG)


def fetch(conn, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def table_exists(conn, table: str) -> bool:
    rows = fetch(
        conn,
        "SELECT COUNT(*) AS n FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
        (DB_CONFIG["database"], table),
    )
    return bool(rows and rows[0]["n"])


def list_columns(conn, table: str) -> list[dict[str, str]]:
    return fetch(
        conn,
        "SELECT COLUMN_NAME AS name, COLUMN_TYPE AS type, IS_NULLABLE AS nullable "
        "FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION",
        (DB_CONFIG["database"], table),
    )


def row_count(conn, table: str) -> int:
    rows = fetch(conn, f"SELECT COUNT(*) AS n FROM `{table}`")
    return int(rows[0]["n"]) if rows else 0


def column_exists(conn, table: str, column: str) -> bool:
    rows = fetch(
        conn,
        "SELECT COUNT(*) AS n FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s",
        (DB_CONFIG["database"], table, column),
    )
    return bool(rows and rows[0]["n"])


def profile_column(conn, table: str, column: str, kind: str, total: int) -> dict[str, Any]:
    """Estadísticas de calidad de una columna, según su tipo de centinela."""
    col = f"`{column}`"
    base = f"FROM `{table}`"
    stats: dict[str, Any] = {"column": column, "kind": kind}

    nulls = fetch(conn, f"SELECT COUNT(*) AS n {base} WHERE {col} IS NULL")[0]["n"]
    distinct = fetch(conn, f"SELECT COUNT(DISTINCT {col}) AS n {base}")[0]["n"]
    stats["null_pct"] = round(100.0 * nulls / total, 2) if total else None
    stats["distinct"] = int(distinct)

    if kind == "date":
        sentinel = fetch(conn, f"SELECT COUNT(*) AS n {base} WHERE {col} <= '1900-01-01'")[0]["n"]
        stats["sentinel_pct"] = round(100.0 * sentinel / total, 2) if total else None
        rng = fetch(conn, f"SELECT MIN({col}) AS mn, MAX({col}) AS mx {base} WHERE {col} > '1900-01-01'")[0]
        stats["min"] = str(rng["mn"])
        stats["max"] = str(rng["mx"])
    elif kind == "num":
        sentinel = fetch(conn, f"SELECT COUNT(*) AS n {base} WHERE {col} = -99")[0]["n"]
        neg = fetch(conn, f"SELECT COUNT(*) AS n {base} WHERE {col} < 0")[0]["n"]
        stats["sentinel_pct"] = round(100.0 * sentinel / total, 2) if total else None
        stats["negative_pct"] = round(100.0 * neg / total, 2) if total else None
        rng = fetch(conn, f"SELECT MIN({col}) AS mn, MAX({col}) AS mx, AVG({col}) AS av {base} WHERE {col} >= 0")[0]
        stats["min"], stats["max"] = rng["mn"], rng["mx"]
        stats["avg_valid"] = round(float(rng["av"]), 2) if rng["av"] is not None else None
    elif kind == "flag":
        sentinel = fetch(conn, f"SELECT COUNT(*) AS n {base} WHERE {col} = 255")[0]["n"]
        stats["sentinel_pct"] = round(100.0 * sentinel / total, 2) if total else None
        vals = fetch(conn, f"SELECT {col} AS v, COUNT(*) AS n {base} GROUP BY {col} ORDER BY n DESC LIMIT 8")
        stats["value_counts"] = {str(r["v"]): int(r["n"]) for r in vals}
    else:  # plain
        vals = fetch(conn, f"SELECT {col} AS v, COUNT(*) AS n {base} GROUP BY {col} ORDER BY n DESC LIMIT 8")
        stats["top_values"] = {str(r["v"]): int(r["n"]) for r in vals}

    return stats


def mortality_base_rate(conn) -> dict[str, Any] | None:
    """Base rate del target de mortalidad sobre flow_procedimientocardiologia."""
    if not table_exists(conn, "flow_procedimientocardiologia"):
        return None
    rows = fetch(
        conn,
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN FechaFallece > '1900-01-01' THEN 1 ELSE 0 END) AS fallecidos
        FROM flow_procedimientocardiologia
        WHERE FechaEgreso > '1900-01-01'
        """,
    )[0]
    total = int(rows["total"] or 0)
    fall = int(rows["fallecidos"] or 0)
    return {
        "egresos_validos": total,
        "fallecidos": fall,
        "mortalidad_pct": round(100.0 * fall / total, 3) if total else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Perfilado Fase 0 del esquema incc para ML.")
    parser.add_argument("--json", dest="json_out", default="", help="ruta para volcar el perfil en JSON")
    parser.add_argument("--full-columns", action="store_true", help="listar TODAS las columnas de cada tabla")
    args = parser.parse_args()

    report: dict[str, Any] = {"database": DB_CONFIG["database"], "host": DB_CONFIG["host"], "tables": {}}

    conn = connect()
    try:
        print(f"\n=== Perfilado incc @ {DB_CONFIG['host']}:{DB_CONFIG['port']} / {DB_CONFIG['database']} ===\n")

        for table, desc in RELEVANT_TABLES.items():
            if not table_exists(conn, table):
                print(f"[!] Tabla ausente: {table}")
                report["tables"][table] = {"exists": False}
                continue

            total = row_count(conn, table)
            all_cols = list_columns(conn, table)
            entry: dict[str, Any] = {
                "exists": True,
                "desc": desc,
                "rows": total,
                "n_columns": len(all_cols),
                "columns": [] ,
                "profiles": [],
            }
            print(f"### {table}  ({total:,} filas, {len(all_cols)} columnas)")
            print(f"    {desc}")

            if args.full_columns:
                entry["columns"] = all_cols
                for c in all_cols:
                    print(f"      - {c['name']}: {c['type']}")

            for column, kind in CANDIDATE_COLUMNS.get(table, []):
                if not column_exists(conn, table, column):
                    print(f"      [!] columna candidata ausente: {column}")
                    entry["profiles"].append({"column": column, "exists": False})
                    continue
                stats = profile_column(conn, table, column, kind, total)
                entry["profiles"].append(stats)
                extra = {k: v for k, v in stats.items() if k not in {"column", "kind"}}
                print(f"      · {column} [{kind}]: {extra}")

            report["tables"][table] = entry
            print()

        base = mortality_base_rate(conn)
        report["mortality_target"] = base
        if base:
            print("### Target mortalidad (flow_procedimientocardiologia, egreso válido)")
            print(f"    {base}\n")
    finally:
        conn.close()

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2, default=str)
        print(f"Perfil escrito en {args.json_out}")


if __name__ == "__main__":
    main()
