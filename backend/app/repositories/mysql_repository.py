from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from app.core.config import get_settings
from app.core.kpi_registry import DynamicKpi, kpi_registry
from app.core.security import get_password_hash
from app.repositories.interfaces import AnalyticsRepository, AuthRepository


class MySQLRepository(AuthRepository, AnalyticsRepository):
    def __init__(self) -> None:
        settings = get_settings()
        self._db_config = {
            "host": settings.mysql_host,
            "port": settings.mysql_port,
            "user": settings.mysql_user,
            "password": settings.mysql_password,
            "database": settings.mysql_database,
            "cursorclass": DictCursor,
            "autocommit": True,
        }
        self._users = [
            {
                "id": 1,
                "username": "clinician",
                "full_name": "Dr. Ana Pereira",
                "role": "clinician",
                "permissions": ["dashboard:read", "kpis:query"],
                "hashed_password": get_password_hash("Demo1234!"),
            },
            {
                "id": 2,
                "username": "admin",
                "full_name": "Admin INCC",
                "role": "admin",
                "permissions": ["dashboard:read", "kpis:query", "users:manage"],
                "hashed_password": get_password_hash("Admin1234!"),
            },
        ]
        self._ensure_dynamic_kpi_table()

    def _ensure_dynamic_kpi_table(self) -> None:
        """Crea tabla de KPIs dinamicos si no existe para persistencia runtime."""
        try:
            self._execute(
                """
                CREATE TABLE IF NOT EXISTS cardio_dynamic_kpis (
                    kpi_key VARCHAR(120) PRIMARY KEY,
                    label VARCHAR(255) NOT NULL,
                    description TEXT NOT NULL,
                    sql_query_template LONGTEXT NOT NULL,
                    default_granularity VARCHAR(16) NOT NULL DEFAULT 'month',
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
                """
            )
        except Exception:
            # Si el usuario no tiene permisos DDL, mantenemos funcionamiento en memoria.
            return

    def upsert_dynamic_kpi(self, item: DynamicKpi) -> None:
        """Inserta o actualiza un KPI dinamico en la tabla de persistencia."""
        self._execute(
            """
            INSERT INTO cardio_dynamic_kpis
                (kpi_key, label, description, sql_query_template, default_granularity, is_active)
            VALUES
                (%s, %s, %s, %s, %s, 1)
            ON DUPLICATE KEY UPDATE
                label = VALUES(label),
                description = VALUES(description),
                sql_query_template = VALUES(sql_query_template),
                default_granularity = VALUES(default_granularity),
                is_active = 1
            """,
            (
                item.key,
                item.label,
                item.description,
                item.sql_query_template,
                item.default_granularity,
            ),
        )

    def deactivate_dynamic_kpi(self, key: str) -> None:
        """Marca un KPI dinamico como inactivo para rollback/depuracion."""
        self._execute(
            """
            UPDATE cardio_dynamic_kpis
            SET is_active = 0
            WHERE kpi_key = %s
            """,
            (key,),
        )

    def _dynamic_kpis_by_key(self) -> dict[str, DynamicKpi]:
        """Retorna KPIs dinamicos activos combinando BD (persistente) y memoria (runtime)."""
        result: dict[str, DynamicKpi] = {}

        try:
            rows = self._execute(
                """
                SELECT kpi_key, label, description, sql_query_template, default_granularity
                FROM cardio_dynamic_kpis
                WHERE is_active = 1
                """
            )
            for row in rows:
                key = str(row.get("kpi_key") or "").strip()
                if not key:
                    continue
                result[key] = DynamicKpi(
                    key=key,
                    label=str(row.get("label") or key),
                    description=str(row.get("description") or ""),
                    sql_query_template=str(row.get("sql_query_template") or ""),
                    default_granularity=str(row.get("default_granularity") or "month"),
                )
        except Exception:
            pass

        for item in kpi_registry.list_all():
            result[item.key] = item

        return result

    def _execute(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        conn = pymysql.connect(**self._db_config)
        try:
            with conn.cursor() as cursor:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                return list(cursor.fetchall())
        finally:
            conn.close()

    @staticmethod
    def _first_filter_value(filters: list[dict[str, Any]], keys: list[str]) -> str | None:
        key_set = {key.lower() for key in keys}
        for item in filters:
            filter_key = str(item.get("key") or "").lower()
            if filter_key not in key_set:
                continue
            values = item.get("values") or []
            if not values:
                continue
            return str(values[0]).strip()
        return None

    @staticmethod
    def _valid_iso_date(value: str | None) -> bool:
        if value is None or len(value) != 10:
            return False
        yyyy, mm, dd = value[0:4], value[5:7], value[8:10]
        return value[4] == "-" and value[7] == "-" and yyyy.isdigit() and mm.isdigit() and dd.isdigit()

    def _date_clause(self, column_name: str, filters: list[dict[str, Any]]) -> str:
        date_from = self._first_filter_value(filters, ["date_from", "from", "start_date"])
        date_to = self._first_filter_value(filters, ["date_to", "to", "end_date"])
        clauses: list[str] = []

        if self._valid_iso_date(date_from):
            clauses.append(f"{column_name} >= '{date_from}'")
        if self._valid_iso_date(date_to):
            clauses.append(f"{column_name} <= '{date_to}'")

        if not clauses:
            return ""
        return " AND " + " AND ".join(clauses)

    @staticmethod
    def _normalize_act_type(filters: list[dict[str, Any]]) -> str:
        act_type = "all"
        for item in filters:
            if str(item.get("key") or "").lower() != "act_type":
                continue
            values = item.get("values") or []
            if not values:
                continue
            normalized = str(values[0]).strip().lower()
            if normalized in {"all", "surgery", "ptca"}:
                act_type = normalized
        return act_type

    def _period_expr(self, column_name: str, granularity: str) -> str:
        if granularity == "day":
            return f"DATE_FORMAT({column_name}, '%Y-%m-%d')"
        if granularity == "week":
            return f"DATE_FORMAT({column_name}, '%x-W%v')"
        return f"DATE_FORMAT({column_name}, '%Y-%m')"

    def _cube_dimension_expr(self, dimension: str, date_column: str, granularity: str) -> str:
        normalized = dimension.lower()
        if normalized == "year":
            return f"DATE_FORMAT({date_column}, '%Y')"
        if normalized == "quarter":
            return f"CONCAT('T', QUARTER({date_column}))"
        if normalized == "month":
            return f"DATE_FORMAT({date_column}, '%m')"
        if normalized == "granularity":
            return f"'{granularity}'"
        return self._period_expr(date_column, granularity)

    @staticmethod
    def _cube_period_dimension_expr(period_column: str, dimension: str, granularity: str) -> str:
        """Dimension expression when source rows already expose a `period` string."""
        normalized = dimension.lower()
        if normalized == "period":
            return period_column
        if normalized == "year":
            return f"SUBSTRING({period_column}, 1, 4)"
        if normalized == "quarter":
            if granularity == "week":
                return (
                    f"CONCAT('T', CEIL(CAST(SUBSTRING_INDEX({period_column}, 'W', -1) AS UNSIGNED) / 13))"
                )
            return f"CONCAT('T', CEIL(CAST(SUBSTRING({period_column}, 6, 2) AS UNSIGNED) / 3))"
        if normalized == "month":
            if granularity == "week":
                return "'-'"
            return f"SUBSTRING({period_column}, 6, 2)"
        if normalized == "granularity":
            return f"'{granularity}'"
        return period_column

    @staticmethod
    def _infer_dynamic_date_column(sql_template: str) -> str:
        """Infiere columna de fecha para placeholders dinamicos segun alias detectados en SQL."""
        sql_lower = sql_template.lower()
        candidates = [
            ("p.fechaegreso", "p.FechaEgreso"),
            ("p.fecharealizado", "p.FechaRealizado"),
            ("f.fechaegreso", "f.FechaEgreso"),
            ("f.fecharealizado", "f.FechaRealizado"),
            ("fechaegreso", "p.FechaEgreso"),
            ("fecharealizado", "f.FechaRealizado"),
        ]
        for needle, resolved in candidates:
            if needle in sql_lower:
                return resolved
        return "f.FechaRealizado"

    def _monthly_surgery_volume(self, limit: int = 12) -> list[dict[str, Any]]:
        rows = self._execute(
            f"""
            SELECT DATE_FORMAT(f.FechaRealizado, '%Y-%m') AS period,
                   COUNT(*) AS value
            FROM dat_cirugia d
            JOIN flow_coordina f ON f.Cod = d.CodCoordina
            WHERE f.FechaRealizado > '1900-01-01'
            GROUP BY DATE_FORMAT(f.FechaRealizado, '%Y-%m')
            ORDER BY period DESC
            LIMIT {limit}
            """
        )
        rows.reverse()
        return rows

    def _monthly_ptca_volume(self, limit: int = 12) -> list[dict[str, Any]]:
        rows = self._execute(
            f"""
            SELECT DATE_FORMAT(f.FechaRealizado, '%Y-%m') AS period,
                   COUNT(*) AS value
            FROM call_ptcamaster c
            JOIN flow_coordina f ON f.Cod = c.CodCoordina
            WHERE f.FechaRealizado > '1900-01-01'
            GROUP BY DATE_FORMAT(f.FechaRealizado, '%Y-%m')
            ORDER BY period DESC
            LIMIT {limit}
            """
        )
        rows.reverse()
        return rows

    def _monthly_mortality_pct(self, limit: int = 12) -> list[dict[str, Any]]:
        rows = self._execute(
            f"""
            SELECT DATE_FORMAT(p.FechaEgreso, '%Y-%m') AS period,
                   ROUND(
                        100.0 * SUM(CASE WHEN p.FechaFallece > '1900-01-01' THEN 1 ELSE 0 END)
                        / NULLIF(COUNT(*), 0),
                        2
                   ) AS value
            FROM flow_procedimientocardiologia p
            WHERE p.FechaEgreso > '1900-01-01'
            GROUP BY DATE_FORMAT(p.FechaEgreso, '%Y-%m')
            ORDER BY period DESC
            LIMIT {limit}
            """
        )
        rows.reverse()
        return rows

    def _monthly_wait_days(self, limit: int = 12) -> list[dict[str, Any]]:
        rows = self._execute(
            f"""
            SELECT DATE_FORMAT(f.FechaRealizado, '%Y-%m') AS period,
                   ROUND(AVG(DATEDIFF(f.FechaRealizado, f.FechaCoordina)), 2) AS value
            FROM flow_coordina f
            WHERE f.FechaRealizado > '1900-01-01'
              AND f.FechaCoordina > '1900-01-01'
              AND DATEDIFF(f.FechaRealizado, f.FechaCoordina) >= 0
            GROUP BY DATE_FORMAT(f.FechaRealizado, '%Y-%m')
            ORDER BY period DESC
            LIMIT {limit}
            """
        )
        rows.reverse()
        return rows

    def _latest_value(self, series: list[dict[str, Any]]) -> float:
        if not series:
            return 0.0
        return float(series[-1].get("value") or 0.0)

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        rows = self._execute(
            """
            SELECT u.k_id AS id,
                   u.Alias AS username,
                   TRIM(CONCAT(IFNULL(u.Noms, ''), ' ', IFNULL(u.Apes, ''))) AS full_name,
                   COALESCE(t.Descr, 'user') AS role,
                   u.Clave AS password_plain,
                   u.MD5text AS password_md5,
                   u.IdTipo AS role_id
            FROM use_usuarios u
            LEFT JOIN use_usuariostipo t ON t.k_id = u.IdTipo
            WHERE u.Alias = %s
              AND IFNULL(u.Activo, 0) = 1
              AND IFNULL(u.k_del, 0) = 0
            LIMIT 1
            """,
            (username,),
        )
        if rows:
            user = rows[0]
            permission_rows = self._execute(
                """
                SELECT DISTINCT COALESCE(pa.Descr, p.Descr, 'dashboard:read') AS permission
                FROM use_permiso p
                LEFT JOIN use_permisoaccion pa ON pa.k_id = p.IdPermisoAccion
                WHERE p.IdUsuario = %s
                  AND IFNULL(p.Si, 0) = 1
                  AND IFNULL(p.k_del, 0) = 0
                """,
                (user["id"],),
            )
            permissions = [
                str(row["permission"]).strip().lower().replace(" ", "_")
                for row in permission_rows
                if row.get("permission")
            ]
            if not permissions:
                permissions = ["dashboard:read", "kpis:query"]

            return {
                "id": int(user["id"]),
                "username": str(user["username"]),
                "full_name": str(user.get("full_name") or user["username"]),
                "role": str(user.get("role") or "user"),
                "permissions": permissions,
                "password_plain": user.get("password_plain"),
                "password_md5": user.get("password_md5"),
            }

        for user in self._users:
            if user["username"] == username:
                return user
        return None

    def get_filters(self) -> dict[str, Any]:
        return {
            "filters": [
                {
                    "key": "period",
                    "label": "Periodo",
                    "options": [
                        {"value": "day", "label": "Diario"},
                        {"value": "week", "label": "Semanal"},
                        {"value": "month", "label": "Mensual"},
                    ],
                },
                {
                    "key": "metric_group",
                    "label": "Grupo KPI",
                    "options": [
                        {"value": "activity", "label": "Actividad"},
                        {"value": "surgery", "label": "Cirugia"},
                        {"value": "ptca", "label": "PTCA"},
                        {"value": "outcomes", "label": "Desenlaces"},
                    ],
                },
                {
                    "key": "act_type",
                    "label": "Tipo de acto",
                    "options": [
                        {"value": "all", "label": "Todos"},
                        {"value": "surgery", "label": "Cirugia"},
                        {"value": "ptca", "label": "PTCA"},
                    ],
                },
                {
                    "key": "date_from",
                    "label": "Fecha desde",
                    "options": [],
                },
                {
                    "key": "date_to",
                    "label": "Fecha hasta",
                    "options": [],
                },
            ]
        }

    def get_kpis_catalog(self) -> dict[str, Any]:
        kpis = [
                {
                    "key": "surgery_volume",
                    "label": "Volumen de cirugias",
                    "unit": "casos",
                    "description": "Cantidad de cirugias por periodo",
                },
                {
                    "key": "ptca_volume",
                    "label": "Volumen de PTCA",
                    "unit": "casos",
                    "description": "Cantidad de procedimientos PTCA por periodo",
                },
                {
                    "key": "mortality_egreso_pct",
                    "label": "Fallecidos al egreso",
                    "unit": "%",
                    "description": "Porcentaje de egresos con fallecimiento registrado",
                },
                {
                    "key": "avg_wait_days",
                    "label": "Espera coordina->realizado",
                    "unit": "dias",
                    "description": "Promedio de dias entre coordinacion y acto realizado",
                },
                {
                    "key": "icu_los_avg",
                    "label": "Estadia promedio UCI",
                    "unit": "dias",
                    "description": "Promedio de estadia UCI en cirugia con datos validos",
                },
                {
                    "key": "ptca_share_pct",
                    "label": "Participacion PTCA",
                    "unit": "%",
                    "description": "Porcentaje de PTCA sobre el total de actividad (PTCA + cirugias)",
                },
            ]

        for dynamic_kpi in self._dynamic_kpis_by_key().values():
            if any(item.get("key") == dynamic_kpi.key for item in kpis):
                continue
            kpis.append(
                {
                    "key": dynamic_kpi.key,
                    "label": dynamic_kpi.label,
                    "unit": "valor",
                    "description": dynamic_kpi.description,
                }
            )

        return {"kpis": kpis}

    def get_dashboard_summary(self) -> dict[str, Any]:
        surgery_series = self._monthly_surgery_volume(limit=2)
        ptca_series = self._monthly_ptca_volume(limit=2)
        mortality_series = self._monthly_mortality_pct(limit=2)
        wait_series = self._monthly_wait_days(limit=2)

        icu_rows = self._execute(
            """
            SELECT ROUND(AVG(d.POestadiaUCI), 2) AS value
            FROM dat_cirugia d
            JOIN flow_coordina f ON f.Cod = d.CodCoordina
            WHERE f.FechaRealizado > '1900-01-01'
              AND d.POestadiaUCI >= 0
            """
        )
        icu_value = float((icu_rows[0].get("value") if icu_rows else 0) or 0)

        def delta(series: list[dict[str, Any]]) -> float | None:
            if len(series) < 2:
                return None
            prev = float(series[-2].get("value") or 0)
            curr = float(series[-1].get("value") or 0)
            if prev == 0:
                return None
            return round(((curr - prev) / prev) * 100.0, 2)

        return {
            "cards": [
                {
                    "key": "surgery_volume",
                    "label": "Cirugias (ultimo mes)",
                    "value": int(self._latest_value(surgery_series)),
                    "unit": "casos",
                    "delta": delta(surgery_series),
                },
                {
                    "key": "ptca_volume",
                    "label": "PTCA (ultimo mes)",
                    "value": int(self._latest_value(ptca_series)),
                    "unit": "casos",
                    "delta": delta(ptca_series),
                },
                {
                    "key": "mortality_egreso_pct",
                    "label": "Fallecidos al egreso",
                    "value": round(self._latest_value(mortality_series), 2),
                    "unit": "%",
                    "delta": delta(mortality_series),
                },
                {
                    "key": "avg_wait_days",
                    "label": "Espera promedio",
                    "value": round(self._latest_value(wait_series), 2),
                    "unit": "dias",
                    "delta": delta(wait_series),
                },
                {
                    "key": "icu_los_avg",
                    "label": "Estadia UCI",
                    "value": icu_value,
                    "unit": "dias",
                    "delta": None,
                },
            ]
        }

    def get_dashboard_charts(self) -> dict[str, Any]:
        surgery_series = self._monthly_surgery_volume(limit=12)
        ptca_series = self._monthly_ptca_volume(limit=12)
        mortality_series = self._monthly_mortality_pct(limit=12)
        wait_series = self._monthly_wait_days(limit=12)

        return {
            "charts": [
                {
                    "chart_id": "activity_monthly",
                    "title": "Actividad mensual",
                    "chart_type": "line",
                    "series": [
                        {
                            "key": "surgery_volume",
                            "label": "Cirugias",
                            "points": [{"x": row["period"], "y": float(row["value"])} for row in surgery_series],
                        },
                        {
                            "key": "ptca_volume",
                            "label": "PTCA",
                            "points": [{"x": row["period"], "y": float(row["value"])} for row in ptca_series],
                        },
                    ],
                },
                {
                    "chart_id": "outcomes_monthly",
                    "title": "Desenlaces y espera",
                    "chart_type": "line",
                    "series": [
                        {
                            "key": "mortality_egreso_pct",
                            "label": "Fallecidos al egreso (%)",
                            "points": [{"x": row["period"], "y": float(row["value"])} for row in mortality_series],
                        },
                        {
                            "key": "avg_wait_days",
                            "label": "Espera (dias)",
                            "points": [{"x": row["period"], "y": float(row["value"])} for row in wait_series],
                        },
                    ],
                },
            ]
        }

    def get_dashboard_table(self) -> dict[str, Any]:
        rows = self._execute(
            """
            SELECT DATE_FORMAT(f.FechaRealizado, '%Y-%m') AS period,
                   COUNT(DISTINCT d.k_id) AS surgeries,
                   COUNT(DISTINCT c.Cod) AS ptca,
                   ROUND(AVG(CASE WHEN d.POestadiaUCI >= 0 THEN d.POestadiaUCI END), 2) AS icu_los_avg,
                   ROUND(AVG(CASE
                       WHEN f.FechaCoordina > '1900-01-01'
                        AND DATEDIFF(f.FechaRealizado, f.FechaCoordina) >= 0
                       THEN DATEDIFF(f.FechaRealizado, f.FechaCoordina)
                   END), 2) AS avg_wait_days
            FROM flow_coordina f
            LEFT JOIN dat_cirugia d ON d.CodCoordina = f.Cod
            LEFT JOIN call_ptcamaster c ON c.CodCoordina = f.Cod
            WHERE f.FechaRealizado > '1900-01-01'
            GROUP BY DATE_FORMAT(f.FechaRealizado, '%Y-%m')
            ORDER BY period DESC
            LIMIT 12
            """
        )
        rows.reverse()

        return {
            "columns": [
                {"key": "period", "label": "Periodo"},
                {"key": "surgeries", "label": "Cirugias"},
                {"key": "ptca", "label": "PTCA"},
                {"key": "icu_los_avg", "label": "UCI prom. (dias)"},
                {"key": "avg_wait_days", "label": "Espera prom. (dias)"},
            ],
            "rows": [
                {
                    "values": {
                        "period": row["period"],
                        "surgeries": int(row["surgeries"] or 0),
                        "ptca": int(row["ptca"] or 0),
                        "icu_los_avg": float(row["icu_los_avg"] or 0),
                        "avg_wait_days": float(row["avg_wait_days"] or 0),
                    }
                }
                for row in rows
            ],
            "total": len(rows),
        }

    def query_analytics(self, payload: dict[str, Any]) -> dict[str, Any]:
        widget_type = str(payload.get("widget_type") or "table").lower()
        filters = payload.get("filters", [])
        granularity = str(payload.get("granularity") or "month").lower()
        if granularity not in {"day", "week", "month"}:
            granularity = "month"
        limit = int(payload.get("limit") or 10)
        if limit < 1:
            limit = 1
        if limit > 100:
            limit = 100

        if widget_type == "cube":
            metric_key = str(payload.get("metric_key") or "surgery_volume").lower()
            row_dimension = str(payload.get("row_dimension") or "period").lower()
            column_dimension = str(payload.get("column_dimension") or "quarter").lower()
            aggregation = str(payload.get("aggregation") or "sum").lower()
            if aggregation not in {"sum", "avg", "min", "max"}:
                aggregation = "sum"
            dynamic_kpi = self._dynamic_kpis_by_key().get(metric_key)

            if metric_key == "mortality_egreso_pct":
                date_column = "p.FechaEgreso"
                row_expr = self._cube_dimension_expr(row_dimension, date_column, granularity)
                col_expr = self._cube_dimension_expr(column_dimension, date_column, granularity)
                date_filter = self._date_clause(date_column, filters)
                rows = self._execute(
                    f"""
                    SELECT {row_expr} AS row_key,
                           {col_expr} AS column_key,
                           ROUND(
                                100.0 * SUM(CASE WHEN p.FechaFallece > '1900-01-01' THEN 1 ELSE 0 END)
                                / NULLIF(COUNT(*), 0),
                                2
                           ) AS value
                    FROM flow_procedimientocardiologia p
                    WHERE p.FechaEgreso > '1900-01-01'{date_filter}
                    GROUP BY {row_expr}, {col_expr}
                    ORDER BY row_key, column_key
                    LIMIT {limit}
                    """
                )
            elif dynamic_kpi is not None:
                dynamic_sql = dynamic_kpi.sql_query_template.strip().rstrip(";")
                if "{period_expr}" in dynamic_sql or "{date_clause}" in dynamic_sql:
                    date_column_dynamic = self._infer_dynamic_date_column(dynamic_sql)
                    period_expr_dynamic = self._period_expr(date_column_dynamic, granularity)
                    date_clause_dynamic = self._date_clause(date_column_dynamic, filters)
                    dynamic_sql = (
                        dynamic_sql
                        .replace("{period_expr}", period_expr_dynamic)
                        .replace("{date_clause}", date_clause_dynamic)
                    )

                row_expr = self._cube_period_dimension_expr("src.period", row_dimension, granularity)
                col_expr = self._cube_period_dimension_expr("src.period", column_dimension, granularity)
                aggregate_fn = aggregation.upper()
                value_expr = f"ROUND({aggregate_fn}(src.value), 2)"

                rows = self._execute(
                    f"""
                    SELECT {row_expr} AS row_key,
                           {col_expr} AS column_key,
                           {value_expr} AS value
                    FROM ({dynamic_sql}) src
                    GROUP BY {row_expr}, {col_expr}
                    ORDER BY row_key, column_key
                    LIMIT {limit}
                    """
                )
            else:
                date_column = "f.FechaRealizado"
                row_expr = self._cube_dimension_expr(row_dimension, date_column, granularity)
                col_expr = self._cube_dimension_expr(column_dimension, date_column, granularity)
                date_filter = self._date_clause(date_column, filters)

                metric_expr_map = {
                    "surgery_volume": "COUNT(DISTINCT d.k_id)",
                    "ptca_volume": "COUNT(DISTINCT c.Cod)",
                    "avg_wait_days": "CASE WHEN f.FechaCoordina > '1900-01-01' AND DATEDIFF(f.FechaRealizado, f.FechaCoordina) >= 0 THEN DATEDIFF(f.FechaRealizado, f.FechaCoordina) END",
                    "ptca_share_pct": "100.0 * COUNT(DISTINCT c.Cod) / NULLIF(COUNT(DISTINCT d.k_id) + COUNT(DISTINCT c.Cod), 0)",
                }
                if metric_key not in metric_expr_map:
                    metric_key = "surgery_volume"
                metric_expr = metric_expr_map[metric_key]

                aggregate_fn = aggregation.upper()
                if metric_key in {"surgery_volume", "ptca_volume", "ptca_share_pct"}:
                    aggregate_fn = ""

                if aggregate_fn:
                    value_expr = f"ROUND({aggregate_fn}({metric_expr}), 2)"
                else:
                    value_expr = f"ROUND({metric_expr}, 2)"

                rows = self._execute(
                    f"""
                    SELECT {row_expr} AS row_key,
                           {col_expr} AS column_key,
                           {value_expr} AS value
                    FROM flow_coordina f
                    LEFT JOIN dat_cirugia d ON d.CodCoordina = f.Cod
                    LEFT JOIN call_ptcamaster c ON c.CodCoordina = f.Cod
                    WHERE f.FechaRealizado > '1900-01-01'{date_filter}
                    GROUP BY {row_expr}, {col_expr}
                    ORDER BY row_key, column_key
                    LIMIT {limit}
                    """
                )

            formatted_rows = [
                {
                    "row_key": str(row.get("row_key") or "-"),
                    "column_key": str(row.get("column_key") or "-"),
                    "value": float(row.get("value") or 0),
                }
                for row in rows
            ]
            return {
                "widget_type": "cube",
                "title": "Cubo analitico por dimensiones",
                "columns": [
                    {"key": "row_key", "label": row_dimension},
                    {"key": "column_key", "label": column_dimension},
                    {"key": "value", "label": metric_key},
                ],
                "rows": formatted_rows,
                "meta": {
                    "granularity": granularity,
                    "limit": limit,
                    "metric_key": metric_key,
                    "row_dimension": row_dimension,
                    "column_dimension": column_dimension,
                    "aggregation": aggregation,
                    "query_preview": f"SELECT {row_dimension}, {column_dimension}, {aggregation.upper()}({metric_key}) AS value FROM source GROUP BY {row_dimension}, {column_dimension}",
                },
            }

        if widget_type == "ranking":
            metric_key = str(payload.get("metric_key") or "surgery_volume").lower()
            if metric_key == "ptca_volume":
                date_expr = self._period_expr("f.FechaRealizado", granularity)
                date_filter = self._date_clause("f.FechaRealizado", filters)
                rows = self._execute(
                    f"""
                    SELECT {date_expr} AS label,
                           COUNT(*) AS value
                    FROM call_ptcamaster c
                    JOIN flow_coordina f ON f.Cod = c.CodCoordina
                    WHERE f.FechaRealizado > '1900-01-01'{date_filter}
                    GROUP BY {date_expr}
                    ORDER BY value DESC
                    LIMIT {limit}
                    """
                )
            elif metric_key == "mortality_egreso_pct":
                date_expr = self._period_expr("p.FechaEgreso", granularity)
                date_filter = self._date_clause("p.FechaEgreso", filters)
                rows = self._execute(
                    f"""
                    SELECT {date_expr} AS label,
                           ROUND(
                                100.0 * SUM(CASE WHEN p.FechaFallece > '1900-01-01' THEN 1 ELSE 0 END)
                                / NULLIF(COUNT(*), 0),
                                2
                           ) AS value
                    FROM flow_procedimientocardiologia p
                    WHERE p.FechaEgreso > '1900-01-01'{date_filter}
                    GROUP BY {date_expr}
                    ORDER BY value DESC
                    LIMIT {limit}
                    """
                )
            else:
                metric_key = "surgery_volume"
                date_expr = self._period_expr("f.FechaRealizado", granularity)
                date_filter = self._date_clause("f.FechaRealizado", filters)
                rows = self._execute(
                    f"""
                    SELECT {date_expr} AS label,
                           COUNT(*) AS value
                    FROM dat_cirugia d
                    JOIN flow_coordina f ON f.Cod = d.CodCoordina
                    WHERE f.FechaRealizado > '1900-01-01'{date_filter}
                    GROUP BY {date_expr}
                    ORDER BY value DESC
                    LIMIT {limit}
                    """
                )

            formatted_rows = [
                {
                    "rank": idx,
                    "label": str(row.get("label") or "-"),
                    "value": float(row.get("value") or 0),
                }
                for idx, row in enumerate(rows, start=1)
            ]
            return {
                "widget_type": "ranking",
                "title": "Ranking por periodo",
                "columns": [
                    {"key": "rank", "label": "Posicion"},
                    {"key": "label", "label": "Periodo"},
                    {"key": "value", "label": "Valor"},
                ],
                "rows": formatted_rows,
                "meta": {
                    "metric_key": metric_key,
                    "granularity": granularity,
                    "limit": limit,
                },
            }

        date_expr = self._period_expr("f.FechaRealizado", granularity)
        date_filter = self._date_clause("f.FechaRealizado", filters)
        rows = self._execute(
            f"""
            SELECT {date_expr} AS period,
                   COUNT(DISTINCT d.k_id) AS surgeries,
                   COUNT(DISTINCT c.Cod) AS ptca,
                   ROUND(AVG(CASE WHEN d.POestadiaUCI >= 0 THEN d.POestadiaUCI END), 2) AS icu_los_avg,
                   ROUND(AVG(CASE
                       WHEN f.FechaCoordina > '1900-01-01'
                        AND DATEDIFF(f.FechaRealizado, f.FechaCoordina) >= 0
                       THEN DATEDIFF(f.FechaRealizado, f.FechaCoordina)
                   END), 2) AS avg_wait_days,
                    ROUND(
                        100.0 * COUNT(DISTINCT c.Cod)
                        / NULLIF(COUNT(DISTINCT d.k_id) + COUNT(DISTINCT c.Cod), 0),
                        2
                    ) AS ptca_share_pct
            FROM flow_coordina f
            LEFT JOIN dat_cirugia d ON d.CodCoordina = f.Cod
            LEFT JOIN call_ptcamaster c ON c.CodCoordina = f.Cod
            WHERE f.FechaRealizado > '1900-01-01'{date_filter}
            GROUP BY {date_expr}
            ORDER BY period DESC
            LIMIT {limit}
            """
        )

        rows.reverse()
        formatted_rows = [
            {
                "period": str(row.get("period") or "-"),
                "surgeries": int(row.get("surgeries") or 0),
                "ptca": int(row.get("ptca") or 0),
                "icu_los_avg": float(row.get("icu_los_avg") or 0),
                "avg_wait_days": float(row.get("avg_wait_days") or 0),
                "ptca_share_pct": float(row.get("ptca_share_pct") or 0),
            }
            for row in rows
        ]
        return {
            "widget_type": "table",
            "title": "Tabla enriquecida por periodo",
            "columns": [
                {"key": "period", "label": "Periodo"},
                {"key": "surgeries", "label": "Cirugias"},
                {"key": "ptca", "label": "PTCA"},
                {"key": "icu_los_avg", "label": "UCI prom. (dias)"},
                {"key": "avg_wait_days", "label": "Espera prom. (dias)"},
                {"key": "ptca_share_pct", "label": "Participacion PTCA (%)"},
            ],
            "rows": formatted_rows,
            "meta": {
                "granularity": granularity,
                "limit": limit,
            },
        }

    def query_kpis(self, payload: dict[str, Any]) -> dict[str, Any]:
        kpi_keys = payload.get("kpi_keys", [])
        filters = payload.get("filters", [])
        granularity = str(payload.get("granularity") or "month").lower()
        if granularity not in {"day", "week", "month"}:
            granularity = "month"
        act_type = self._normalize_act_type(filters)

        period_realizado = self._period_expr("f.FechaRealizado", granularity)
        period_egreso = self._period_expr("p.FechaEgreso", granularity)

        alias_map = {
            "surgery_volume": "surgery_volume",
            "ptca_volume": "ptca_volume",
            "avg_wait_days": "avg_wait_days",
            "mortality_egreso_pct": "mortality_egreso_pct",
            "icu_los_avg": "icu_los_avg",
            "mortality_30d": "mortality_30d",
            "readmission_30d": "readmission_30d", 
            "ptca_share_pct": "ptca_share_pct",
        }

        dynamic_kpis = self._dynamic_kpis_by_key()

        series: list[dict[str, Any]] = []
        for requested_key in kpi_keys:
            normalized_key = alias_map.get(requested_key, requested_key)
            dynamic_kpi = dynamic_kpis.get(normalized_key)
            if dynamic_kpi is not None:
                dynamic_sql = dynamic_kpi.sql_query_template
                if "{period_expr}" in dynamic_sql or "{date_clause}" in dynamic_sql:
                    date_column_dynamic = self._infer_dynamic_date_column(dynamic_sql)
                    period_expr_dynamic = self._period_expr(date_column_dynamic, granularity)
                    date_clause_dynamic = self._date_clause(date_column_dynamic, filters)
                    dynamic_sql = (
                        dynamic_sql
                        .replace("{period_expr}", period_expr_dynamic)
                        .replace("{date_clause}", date_clause_dynamic)
                    )
                rows = self._execute(dynamic_sql)
                points = [
                    {
                        "period": str(row["period"]),
                        "value": float(row["value"] or 0),
                    }
                    for row in rows
                ]
                series.append({"kpi_key": requested_key, "points": points})
                continue

            if normalized_key == "readmission_30d":
                series.append({"kpi_key": requested_key, "points": []})
                continue

            if act_type == "surgery" and normalized_key == "ptca_volume":
                series.append({"kpi_key": requested_key, "points": []})
                continue
            if act_type == "ptca" and normalized_key in {"surgery_volume", "icu_los_avg"}:
                series.append({"kpi_key": requested_key, "points": []})
                continue

            if normalized_key == "surgery_volume":
                extra_where = self._date_clause("f.FechaRealizado", filters)
                query = f"""
                    SELECT {period_realizado} AS period, COUNT(*) AS value
                    FROM dat_cirugia d
                    JOIN flow_coordina f ON f.Cod = d.CodCoordina
                    WHERE f.FechaRealizado > '1900-01-01'{extra_where}
                    GROUP BY {period_realizado}
                    ORDER BY period
                """
            elif normalized_key == "ptca_volume":
                extra_where = self._date_clause("f.FechaRealizado", filters)
                query = f"""
                    SELECT {period_realizado} AS period, COUNT(*) AS value
                    FROM call_ptcamaster c
                    JOIN flow_coordina f ON f.Cod = c.CodCoordina
                    WHERE f.FechaRealizado > '1900-01-01'{extra_where}
                    GROUP BY {period_realizado}
                    ORDER BY period
                """
            elif normalized_key == "avg_wait_days":
                extra_where = self._date_clause("f.FechaRealizado", filters)
                join_clause = ""
                if act_type == "surgery":
                    join_clause = " JOIN dat_cirugia d ON d.CodCoordina = f.Cod "
                elif act_type == "ptca":
                    join_clause = " JOIN call_ptcamaster c ON c.CodCoordina = f.Cod "
                query = f"""
                    SELECT {period_realizado} AS period,
                           ROUND(AVG(DATEDIFF(f.FechaRealizado, f.FechaCoordina)), 2) AS value
                    FROM flow_coordina f
                    {join_clause}
                    WHERE f.FechaRealizado > '1900-01-01'
                      AND f.FechaCoordina > '1900-01-01'
                      AND DATEDIFF(f.FechaRealizado, f.FechaCoordina) >= 0{extra_where}
                    GROUP BY {period_realizado}
                    ORDER BY period
                """
            elif normalized_key in {"mortality_egreso_pct", "mortality_30d"}:
                extra_where = self._date_clause("p.FechaEgreso", filters)
                query = f"""
                    SELECT {period_egreso} AS period,
                           ROUND(
                                100.0 * SUM(CASE WHEN p.FechaFallece > '1900-01-01' THEN 1 ELSE 0 END)
                                / NULLIF(COUNT(*), 0),
                                2
                           ) AS value
                    FROM flow_procedimientocardiologia p
                    WHERE p.FechaEgreso > '1900-01-01'{extra_where}
                    GROUP BY {period_egreso}
                    ORDER BY period
                """
            elif normalized_key == "icu_los_avg":
                extra_where = self._date_clause("f.FechaRealizado", filters)
                query = f"""
                    SELECT {period_realizado} AS period,
                           ROUND(AVG(d.POestadiaUCI), 2) AS value
                    FROM dat_cirugia d
                    JOIN flow_coordina f ON f.Cod = d.CodCoordina
                    WHERE f.FechaRealizado > '1900-01-01'
                      AND d.POestadiaUCI >= 0{extra_where}
                    GROUP BY {period_realizado}
                    ORDER BY period
                """
            elif normalized_key == "ptca_share_pct":
                extra_where = self._date_clause("f.FechaRealizado", filters)
                query = f"""
                    SELECT {period_realizado} AS period,
                           ROUND(
                                100.0 * COUNT(DISTINCT c.Cod)
                                / NULLIF(COUNT(DISTINCT d.k_id) + COUNT(DISTINCT c.Cod), 0),
                                2
                           ) AS value
                    FROM flow_coordina f
                    LEFT JOIN dat_cirugia d ON d.CodCoordina = f.Cod
                    LEFT JOIN call_ptcamaster c ON c.CodCoordina = f.Cod
                    WHERE f.FechaRealizado > '1900-01-01'{extra_where}
                    GROUP BY {period_realizado}
                    ORDER BY period
                """
            else:
                continue

            rows = self._execute(query)
            points = [
                {
                    "period": str(row["period"]),
                    "value": float(row["value"] or 0),
                }
                for row in rows
            ]
            series.append({"kpi_key": requested_key, "points": points})

        return {"series": series}
