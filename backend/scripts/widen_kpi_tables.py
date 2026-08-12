"""Widen narrow Metabase table cards to full grid width (24) to reduce
spurious horizontal scrollbars in embedded KPIs.

Run: python scripts/widen_kpi_tables.py
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

BASE = "http://190.64.90.170:8810"
USER = "gervasiojaviergarcia@gmail.com"
PASSWORD = "proyecto2026"

# dashboard_id -> list of (dashcard_id, row, col, size_x, size_y)
# Only the cards we reposition/resize; others are kept as-is from GET.
LAYOUTS: dict[int, list[dict]] = {
    # Cirugia · Perfil clinico: stack Top 10 tables full-width
    14: [
        {"id": 525, "row": 0, "col": 0, "size_x": 24, "size_y": 7},   # Diagnosticos
        {"id": 526, "row": 7, "col": 0, "size_x": 24, "size_y": 7},   # Procedimientos
        {"id": 527, "row": 14, "col": 0, "size_x": 24, "size_y": 7},  # Observaciones
        {"id": 520, "row": 21, "col": 0, "size_x": 24, "size_y": 7},  # Ecografias año
        {"id": 528, "row": 28, "col": 0, "size_x": 24, "size_y": 7},  # Ecografias tipo
    ],
    # Cirugia · Pacientes: stack the 3 narrow tables full-width
    13: [
        {"id": 485, "row": 0, "col": 0, "size_x": 12, "size_y": 10},
        {"id": 499, "row": 0, "col": 12, "size_x": 12, "size_y": 10},
        # reintervenciones table stays full width wherever it is - keep from GET
        {"id": 489, "row": 16, "col": 0, "size_x": 8, "size_y": 3},
        {"id": 488, "row": 16, "col": 8, "size_x": 8, "size_y": 3},
        {"id": 487, "row": 16, "col": 16, "size_x": 8, "size_y": 3},
        {"id": 486, "row": 19, "col": 0, "size_x": 24, "size_y": 5},  # Edad promedio
        {"id": 501, "row": 24, "col": 0, "size_x": 24, "size_y": 5},  # Estadia año
        {"id": 502, "row": 29, "col": 0, "size_x": 24, "size_y": 5},  # Estadia 35
    ],
    # Actos · Volumen: stack the two top tables full-width
    10: [
        {"id": 440, "row": 1, "col": 0, "size_x": 24, "size_y": 9},   # Total Actos
        {"id": 443, "row": 10, "col": 0, "size_x": 24, "size_y": 9},  # Donde / factura
        {"id": 441, "row": 19, "col": 0, "size_x": 12, "size_y": 9},  # Mapa
        {"id": 439, "row": 19, "col": 12, "size_x": 12, "size_y": 9}, # Pie
        {"id": 444, "row": 28, "col": 0, "size_x": 24, "size_y": 10}, # Centros
        {"id": 442, "row": 38, "col": 0, "size_x": 24, "size_y": 9},  # Medicos
    ],
    # Factores de Riesgo: widen the 15-wide complicaciones table
    8: [
        {"id": 412, "row": 12, "col": 0, "size_x": 24, "size_y": 4},
    ],
}


def api(method: str, path: str, session: str | None = None, body: dict | None = None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if session:
        req.add_header("X-Metabase-Session", session)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        print(f"  HTTP {exc.code} on {method} {path}: {exc.read().decode()[:400]}")
        raise


def main() -> None:
    session = api("POST", "/api/session", body={"username": USER, "password": PASSWORD})["id"]
    print("login ok")

    for dash_id, overrides in LAYOUTS.items():
        full = api("GET", f"/api/dashboard/{dash_id}", session=session)
        by_id = {o["id"]: o for o in overrides}
        print(f"\n== dashboard {dash_id}: {full.get('name')} ==")

        new_dashcards = []
        for dc in full.get("dashcards", []):
            o = by_id.get(dc["id"])
            new_dashcards.append({
                "id": dc["id"],
                "card_id": dc.get("card_id"),
                "row": o["row"] if o else dc["row"],
                "col": o["col"] if o else dc["col"],
                "size_x": o["size_x"] if o else dc["size_x"],
                "size_y": o["size_y"] if o else dc["size_y"],
                "series": dc.get("series", []),
                "parameter_mappings": dc.get("parameter_mappings", []),
                "visualization_settings": dc.get("visualization_settings", {}),
                "dashboard_tab_id": dc.get("dashboard_tab_id"),
            })
            if o:
                print(f"  resized id={dc['id']} -> {o['size_x']}x{o['size_y']} at r{o['row']}c{o['col']}")

        api("PUT", f"/api/dashboard/{dash_id}", session=session, body={
            "dashcards": new_dashcards,
            "tabs": full.get("tabs") or [],
        })
        print("  saved")

    print("\ndone")


if __name__ == "__main__":
    main()
