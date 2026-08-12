"""Partir dashboards densos de KPIs en vistas más cortas (categorías planas).

Parte Actos (id 5) en 2 y Cirugía (id 6) en 3, por rangos de `row` del layout.
Cada resultado es un dashboard independiente con embedding habilitado (sin tabs).

Hemodinamia (7) y Factores de Riesgo (8) no se tocan.

Run: python scripts/split_kpi_sections.py
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

BASE = "http://190.64.90.170:8810"
USER = "gervasiojaviergarcia@gmail.com"
PASSWORD = "proyecto2026"
YEAR_PARAM_SLUG = "seleccionar_a%C3%B1o"

# source_dashboard_id -> lista de (nombre, predicado sobre row)
SPLITS: list[dict] = [
    {
        "source_id": 5,
        "sections": [
            {
                "name": "Cardio Insights - Actos - Volumen y origen",
                "row_min": 0,
                "row_max": 37,  # inclusive
            },
            {
                "name": "Cardio Insights - Actos - Por procedimiento",
                "row_min": 38,
                "row_max": None,
            },
        ],
    },
    {
        "source_id": 6,
        "sections": [
            {
                "name": "Cardio Insights - Cirugia - Indicadores",
                "row_min": 0,
                "row_max": 16,
            },
            {
                "name": "Cardio Insights - Cirugia - Pacientes y reintervenciones",
                "row_min": 17,
                "row_max": 40,
            },
            {
                "name": "Cardio Insights - Cirugia - Perfil clinico",
                "row_min": 41,
                "row_max": None,
            },
        ],
    },
]


def api(method: str, path: str, session: str | None = None, body: dict | None = None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if session:
        req.add_header("X-Metabase-Session", session)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        print(f"  HTTP {exc.code} on {method} {path}: {exc.read().decode()[:400]}")
        raise


def row_in_range(row: int, row_min: int, row_max: int | None) -> bool:
    if row < row_min:
        return False
    if row_max is not None and row > row_max:
        return False
    return True


def main() -> None:
    session = api("POST", "/api/session", body={"username": USER, "password": PASSWORD})["id"]
    print("login ok")

    results: dict[str, dict] = {}

    for split in SPLITS:
        source_id = split["source_id"]
        src = api("GET", f"/api/dashboard/{source_id}", session=session)
        collection_id = src.get("collection_id")
        parameters = src.get("parameters", [])
        print(f"\n== source dashboard {source_id}: {src.get('name')} ==")

        for section in split["sections"]:
            name = section["name"]
            row_min = section["row_min"]
            row_max = section["row_max"]
            print(f"\n  -> {name} (rows {row_min}..{row_max if row_max is not None else 'inf'})")

            copy = api(
                "POST",
                f"/api/dashboard/{source_id}/copy",
                session=session,
                body={"name": name, "collection_id": collection_id, "is_deep_copy": True},
            )
            new_id = copy["id"]
            print(f"     deep copy id={new_id}")

            full = api("GET", f"/api/dashboard/{new_id}", session=session)
            keep = [
                dc
                for dc in full.get("dashcards", [])
                if row_in_range(int(dc.get("row") or 0), row_min, row_max)
            ]
            if not keep:
                raise RuntimeError(f"no dashcards matched for {name}")

            # Normalizar layout para que empiece en row 0.
            offset = min(int(dc.get("row") or 0) for dc in keep)
            new_dashcards = [
                {
                    "id": dc["id"],
                    "card_id": dc.get("card_id"),
                    "row": int(dc.get("row") or 0) - offset,
                    "col": dc["col"],
                    "size_x": dc["size_x"],
                    "size_y": dc["size_y"],
                    "series": dc.get("series", []),
                    "parameter_mappings": dc.get("parameter_mappings", []),
                    "visualization_settings": dc.get("visualization_settings", {}),
                    "dashboard_tab_id": None,
                }
                for dc in keep
            ]

            api(
                "PUT",
                f"/api/dashboard/{new_id}",
                session=session,
                body={
                    "parameters": parameters,
                    "dashcards": new_dashcards,
                    "tabs": [],
                    "enable_embedding": True,
                    "embedding_params": {YEAR_PARAM_SLUG: "enabled"},
                },
            )
            print(f"     trimmed to {len(new_dashcards)} dashcards, embedding enabled")
            results[name] = {"id": new_id, "source_id": source_id, "cards": len(new_dashcards)}

    print("\n=== RESULT MAPPING ===")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
