from typing import Any

from app.core.security import get_password_hash
from app.repositories.interfaces import AnalyticsRepository, AuthRepository


class MockRepository(AuthRepository, AnalyticsRepository):
    def __init__(self) -> None:
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

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
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
                        {"value": "last_30_days", "label": "Ultimos 30 dias"},
                        {"value": "last_90_days", "label": "Ultimos 90 dias"},
                        {"value": "year_to_date", "label": "Ano en curso"},
                    ],
                },
                {
                    "key": "surgery_type",
                    "label": "Tipo de cirugia",
                    "options": [
                        {"value": "CABG", "label": "Bypass coronario (CABG)"},
                        {"value": "VALVE", "label": "Reemplazo valvular"},
                        {"value": "CONGENITAL", "label": "Cardiopatia congenita"},
                    ],
                },
                {
                    "key": "risk_level",
                    "label": "Riesgo preoperatorio",
                    "options": [
                        {"value": "low", "label": "Bajo"},
                        {"value": "medium", "label": "Medio"},
                        {"value": "high", "label": "Alto"},
                    ],
                },
            ]
        }

    def get_kpis_catalog(self) -> dict[str, Any]:
        return {
            "kpis": [
                {
                    "key": "mortality_30d",
                    "label": "Mortalidad a 30 dias",
                    "unit": "%",
                    "description": "Porcentaje de pacientes fallecidos dentro de 30 dias",
                },
                {
                    "key": "icu_los_avg",
                    "label": "Estadia promedio UCI",
                    "unit": "dias",
                    "description": "Promedio de dias de internacion en UCI",
                },
                {
                    "key": "readmission_30d",
                    "label": "Reingreso a 30 dias",
                    "unit": "%",
                    "description": "Pacientes readmitidos en los 30 dias posteriores",
                },
                {
                    "key": "surgery_volume",
                    "label": "Volumen de cirugias",
                    "unit": "casos",
                    "description": "Total de cirugias realizadas en el periodo",
                },
            ]
        }

    def get_dashboard_summary(self) -> dict[str, Any]:
        return {
            "cards": [
                {
                    "key": "surgery_volume",
                    "label": "Cirugias (mes)",
                    "value": 214,
                    "unit": "casos",
                    "delta": 8.4,
                },
                {
                    "key": "mortality_30d",
                    "label": "Mortalidad 30d",
                    "value": 2.1,
                    "unit": "%",
                    "delta": -0.4,
                },
                {
                    "key": "icu_los_avg",
                    "label": "Estadia UCI",
                    "value": 3.8,
                    "unit": "dias",
                    "delta": -0.2,
                },
                {
                    "key": "readmission_30d",
                    "label": "Reingresos 30d",
                    "value": 5.7,
                    "unit": "%",
                    "delta": 0.6,
                },
            ]
        }

    def get_dashboard_charts(self) -> dict[str, Any]:
        return {
            "charts": [
                {
                    "chart_id": "mortality_trend",
                    "title": "Tendencia de mortalidad 30d",
                    "chart_type": "line",
                    "series": [
                        {
                            "key": "mortality_30d",
                            "label": "Mortalidad 30d",
                            "points": [
                                {"x": "2025-11", "y": 2.4},
                                {"x": "2025-12", "y": 2.3},
                                {"x": "2026-01", "y": 2.2},
                                {"x": "2026-02", "y": 2.1},
                                {"x": "2026-03", "y": 2.0},
                            ],
                        }
                    ],
                },
                {
                    "chart_id": "surgery_by_type",
                    "title": "Volumen por tipo de cirugia",
                    "chart_type": "bar",
                    "series": [
                        {
                            "key": "surgery_volume",
                            "label": "Cirugias",
                            "points": [
                                {"x": "CABG", "y": 96},
                                {"x": "VALVE", "y": 72},
                                {"x": "CONGENITAL", "y": 46},
                            ],
                        }
                    ],
                },
            ]
        }

    def get_dashboard_table(self) -> dict[str, Any]:
        rows = [
            {
                "values": {
                    "patient_group": "CABG - Bajo riesgo",
                    "cases": 48,
                    "mortality_30d": 1.2,
                    "icu_los_avg": 3.1,
                }
            },
            {
                "values": {
                    "patient_group": "CABG - Alto riesgo",
                    "cases": 22,
                    "mortality_30d": 4.8,
                    "icu_los_avg": 5.4,
                }
            },
            {
                "values": {
                    "patient_group": "VALVE - Medio riesgo",
                    "cases": 37,
                    "mortality_30d": 2.4,
                    "icu_los_avg": 3.6,
                }
            },
        ]
        return {
            "columns": [
                {"key": "patient_group", "label": "Grupo"},
                {"key": "cases", "label": "Casos"},
                {"key": "mortality_30d", "label": "Mortalidad 30d (%)"},
                {"key": "icu_los_avg", "label": "UCI prom. (dias)"},
            ],
            "rows": rows,
            "total": len(rows),
        }

    def query_kpis(self, payload: dict[str, Any]) -> dict[str, Any]:
        kpi_keys = payload.get("kpi_keys", [])
        base_series = {
            "mortality_30d": [2.4, 2.3, 2.2, 2.1, 2.0],
            "icu_los_avg": [4.1, 4.0, 3.9, 3.8, 3.8],
            "readmission_30d": [6.1, 6.0, 5.9, 5.8, 5.7],
            "surgery_volume": [180, 192, 201, 208, 214],
        }
        periods = ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03"]

        series: list[dict[str, Any]] = []
        for key in kpi_keys:
            values = base_series.get(key)
            if not values:
                continue
            points = [{"period": period, "value": value} for period, value in zip(periods, values)]
            series.append({"kpi_key": key, "points": points})

        return {"series": series}
