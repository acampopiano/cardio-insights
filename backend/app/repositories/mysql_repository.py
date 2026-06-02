from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from app.core.config import get_settings
from app.core.kpi_registry import kpi_registry
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
        kpis: list[dict[str, str]] = [
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
        ]

        for item in kpi_registry.list_all():
            if any(existing.get("key") == item.key for existing in kpis):
                continue
            kpis.append(
                {
                    "key": item.key,
                    "label": item.label,
                    "unit": "valor",
                    "description": item.description,
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
        }

        series: list[dict[str, Any]] = []
        for requested_key in kpi_keys:
            normalized_key = alias_map.get(requested_key, requested_key)
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
            else:
                dynamic_kpi = kpi_registry.get(normalized_key)
                if dynamic_kpi is None:
                    continue

                sql_query = (
                    dynamic_kpi.sql_query_template
                    .replace("{period_expr}", period_realizado)
                    .replace("{date_clause}", self._date_clause("f.FechaRealizado", filters))
                )
                rows = self._execute(sql_query)
                points = [
                    {
                        "period": str(row["period"]),
                        "value": float(row["value"] or 0),
                    }
                    for row in rows
                ]
                series.append({"kpi_key": requested_key, "points": points})
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
