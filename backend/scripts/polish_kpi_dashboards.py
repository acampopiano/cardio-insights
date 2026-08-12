"""Visual polish for KPI Metabase dashboards:

1. Strip ' - Duplicar' from card names; clarify Total Cirugias acumulado vs año.
2. Remove redundant text header dashcards and shift layout up.
3. Split Hemodinamia (id 7) into Resumen + Evolucion (flat categories).

Run: python scripts/polish_kpi_dashboards.py
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

BASE = "http://190.64.90.170:8810"
USER = "gervasiojaviergarcia@gmail.com"
PASSWORD = "proyecto2026"
YEAR_PARAM_SLUG = "seleccionar_a%C3%B1o"

EMBEDDED_DASHBOARDS = [10, 11, 12, 13, 14, 7, 8]

# card_id -> preferred clean name (after stripping Duplicar)
RENAMES = {
    358: "Total Cirugías (hasta año seleccionado)",
    376: "Total Cirugías (año seleccionado)",
    295: "Total Angioplastias (hasta año)",
    282: "Total Cirugías (hasta año)",
    388: "Edad promedio Cirugía (año seleccionado)",
    415: "Procedimientos más frecuentes (Top 10)",
    416: "Diagnósticos más frecuentes (Top 10)",
    399: "Observaciones más comunes (Top 10)",
    419: "Ecografías por año",
    411: "Ecografías por tipo",
    371: "Cirugías por año",
}


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


def clean_name(name: str) -> str:
    name = re.sub(r"\s*-\s*Duplicar\s*$", "", name, flags=re.IGNORECASE).strip()
    name = re.sub(r"\s{2,}", " ", name)
    return name


def rename_cards(session: str) -> None:
    print("\n== rename cards ==")
    seen: set[int] = set()
    for did in EMBEDDED_DASHBOARDS:
        dash = api("GET", f"/api/dashboard/{did}", session=session)
        for dc in dash.get("dashcards") or []:
            cid = dc.get("card_id")
            card = dc.get("card") or {}
            if not cid or cid in seen:
                continue
            seen.add(cid)
            old = card.get("name") or ""
            new = RENAMES.get(cid) or clean_name(old)
            if new == old:
                continue
            full = api("GET", f"/api/card/{cid}", session=session)
            api(
                "PUT",
                f"/api/card/{cid}",
                session=session,
                body={
                    "name": new,
                    "dataset_query": full["dataset_query"],
                    "display": full.get("display"),
                    "visualization_settings": full.get("visualization_settings") or {},
                    "description": full.get("description"),
                },
            )
            print(f"  {cid}: {old!r} -> {new!r}")


def remove_text_headers(session: str) -> None:
    print("\n== remove text headers + shift ==")
    for did in EMBEDDED_DASHBOARDS:
        dash = api("GET", f"/api/dashboard/{did}", session=session)
        cards = dash.get("dashcards") or []
        text_headers = [
            dc
            for dc in cards
            if not dc.get("card_id")
            and (dc.get("size_y") or 0) <= 2
            and (dc.get("row") or 0) == 0
        ]
        if not text_headers:
            print(f"  dash {did}: no text header")
            continue

        header_ids = {dc["id"] for dc in text_headers}
        shift = max(dc.get("size_y") or 1 for dc in text_headers)
        kept = []
        for dc in cards:
            if dc["id"] in header_ids:
                continue
            row = dc.get("row") or 0
            if row >= shift:
                row = row - shift
            kept.append({
                "id": dc["id"],
                "card_id": dc.get("card_id"),
                "row": row,
                "col": dc["col"],
                "size_x": dc["size_x"],
                "size_y": dc["size_y"],
                "series": dc.get("series") or [],
                "parameter_mappings": dc.get("parameter_mappings") or [],
                "visualization_settings": dc.get("visualization_settings") or {},
                "dashboard_tab_id": dc.get("dashboard_tab_id"),
            })
        api(
            "PUT",
            f"/api/dashboard/{did}",
            session=session,
            body={
                "parameters": dash.get("parameters") or [],
                "dashcards": kept,
                "tabs": dash.get("tabs") or [],
                "enable_embedding": dash.get("enable_embedding"),
                "embedding_params": dash.get("embedding_params"),
            },
        )
        print(f"  dash {did}: removed {len(text_headers)} header(s), shifted by {shift}")


def split_hemodinamia(session: str) -> dict[str, int]:
    print("\n== split Hemodinamia ==")
    source_id = 7
    src = api("GET", f"/api/dashboard/{source_id}", session=session)
    collection_id = src.get("collection_id")
    parameters = src.get("parameters") or []
    embedding_params = src.get("embedding_params") or {
        YEAR_PARAM_SLUG: "enabled",
        "sede": "enabled",
        "facturacion": "enabled",
    }

    sections = [
        {
            "name": "Cardio Insights - Hemodinamia - Resumen",
            "row_min": 0,
            "row_max": 26,  # scalars + map/pie + stent table
        },
        {
            "name": "Cardio Insights - Hemodinamia - Evolucion",
            "row_min": 27,
            "row_max": None,  # yearly series
        },
    ]
    results: dict[str, int] = {}

    for section in sections:
        name = section["name"]
        row_min = section["row_min"]
        row_max = section["row_max"]
        print(f"  -> {name} rows {row_min}..{row_max if row_max is not None else 'inf'}")

        copy = api(
            "POST",
            f"/api/dashboard/{source_id}/copy",
            session=session,
            body={"name": name, "collection_id": collection_id, "is_deep_copy": True},
        )
        new_id = copy["id"]
        full = api("GET", f"/api/dashboard/{new_id}", session=session)

        def in_range(row: int) -> bool:
            if row < row_min:
                return False
            if row_max is not None and row > row_max:
                return False
            return True

        keep = [dc for dc in full.get("dashcards") or [] if in_range(int(dc.get("row") or 0))]
        if not keep:
            raise RuntimeError(f"no cards for {name}")
        offset = min(int(dc.get("row") or 0) for dc in keep)
        new_dashcards = [
            {
                "id": dc["id"],
                "card_id": dc.get("card_id"),
                "row": int(dc.get("row") or 0) - offset,
                "col": dc["col"],
                "size_x": dc["size_x"],
                "size_y": dc["size_y"],
                "series": dc.get("series") or [],
                "parameter_mappings": dc.get("parameter_mappings") or [],
                "visualization_settings": dc.get("visualization_settings") or {},
                "dashboard_tab_id": None,
            }
            for dc in keep
        ]
        # Also strip text headers in the copy if present at row 0 after normalize
        new_dashcards = [
            dc
            for dc in new_dashcards
            if dc.get("card_id")
            or not (
                (dc.get("row") or 0) == 0
                and (dc.get("size_y") or 0) <= 2
                and not dc.get("card_id")
            )
        ]
        # If we removed a header at row 0, shift again
        if new_dashcards and all((dc.get("row") or 0) > 0 for dc in new_dashcards if dc.get("card_id")):
            # keep as-is if mixed; only shift if min row > 0 among remaining
            min_r = min(int(dc.get("row") or 0) for dc in new_dashcards)
            if min_r > 0:
                for dc in new_dashcards:
                    dc["row"] = int(dc["row"]) - min_r

        api(
            "PUT",
            f"/api/dashboard/{new_id}",
            session=session,
            body={
                "parameters": parameters,
                "dashcards": new_dashcards,
                "tabs": [],
                "enable_embedding": True,
                "embedding_params": embedding_params,
            },
        )
        print(f"     id={new_id} cards={len(new_dashcards)}")
        results[name] = new_id

    return results


def main() -> None:
    session = api("POST", "/api/session", body={"username": USER, "password": PASSWORD})["id"]
    print("login ok")
    # Split first while Hemodinamia (7) still has the original row layout.
    hemo = split_hemodinamia(session)
    all_dash = EMBEDDED_DASHBOARDS + list(hemo.values())
    # Rename (also strips '- Duplicar' that deep-copy may reintroduce).
    print("\n== rename cards ==")
    seen: set[int] = set()
    for did in all_dash:
        dash = api("GET", f"/api/dashboard/{did}", session=session)
        for dc in dash.get("dashcards") or []:
            cid = dc.get("card_id")
            card = dc.get("card") or {}
            if not cid or cid in seen:
                continue
            seen.add(int(cid))
            old = card.get("name") or ""
            new = RENAMES.get(int(cid)) or clean_name(old)
            if new == old:
                continue
            full = api("GET", f"/api/card/{cid}", session=session)
            api(
                "PUT",
                f"/api/card/{cid}",
                session=session,
                body={
                    "name": new,
                    "dataset_query": full["dataset_query"],
                    "display": full.get("display"),
                    "visualization_settings": full.get("visualization_settings") or {},
                    "description": full.get("description"),
                },
            )
            print(f"  {cid}: {old!r} -> {new!r}")

    print("\n== remove text headers + shift ==")
    for did in all_dash:
        dash = api("GET", f"/api/dashboard/{did}", session=session)
        cards = dash.get("dashcards") or []
        text_headers = [
            dc
            for dc in cards
            if not dc.get("card_id")
            and (dc.get("size_y") or 0) <= 2
            and (dc.get("row") or 0) == 0
        ]
        if not text_headers:
            print(f"  dash {did}: no text header")
            continue
        header_ids = {dc["id"] for dc in text_headers}
        shift = max(dc.get("size_y") or 1 for dc in text_headers)
        kept = []
        for dc in cards:
            if dc["id"] in header_ids:
                continue
            row = dc.get("row") or 0
            if row >= shift:
                row = row - shift
            kept.append({
                "id": dc["id"],
                "card_id": dc.get("card_id"),
                "row": row,
                "col": dc["col"],
                "size_x": dc["size_x"],
                "size_y": dc["size_y"],
                "series": dc.get("series") or [],
                "parameter_mappings": dc.get("parameter_mappings") or [],
                "visualization_settings": dc.get("visualization_settings") or {},
                "dashboard_tab_id": dc.get("dashboard_tab_id"),
            })
        api(
            "PUT",
            f"/api/dashboard/{did}",
            session=session,
            body={
                "parameters": dash.get("parameters") or [],
                "dashcards": kept,
                "tabs": dash.get("tabs") or [],
                "enable_embedding": True if did in hemo.values() else dash.get("enable_embedding"),
                "embedding_params": dash.get("embedding_params"),
            },
        )
        print(f"  dash {did}: removed {len(text_headers)} header(s), shifted by {shift}")

    print("\n=== HEMO MAPPING ===")
    print(json.dumps(hemo, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
