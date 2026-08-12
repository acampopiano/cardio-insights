"""One-off script: split the multi-tab "Cardio Insights - KPI" dashboard (id=2)
into one standalone embeddable dashboard per tab, so each KPI category can be
embedded without showing the other tabs.

Metabase static embedding has no way to hide the tab bar, and the source
dashboard uses "dashboard questions" (internal to the dashboard) that cannot be
shared to another dashboard. So we deep-copy the whole dashboard per tab, then
strip it down to a single tab (tabs=[] -> no tab bar) and enable embedding.

Run: python scripts/split_metabase_dashboard.py
"""
import json
import urllib.request
import urllib.error

BASE = "http://190.64.90.170:8810"
USER = "gervasiojaviergarcia@gmail.com"
PASSWORD = "proyecto2026"
SOURCE_DASHBOARD_ID = 2
YEAR_PARAM_SLUG = "seleccionar_a%C3%B1o"

# nombre de la tab en el dashboard origen -> nombre del nuevo dashboard
TABS = {
    "Actos": "Cardio Insights - Actos",
    "Indicadores Cirugía": "Cardio Insights - Indicadores Cirugia",
    "Indicadores Hemodinamia": "Cardio Insights - Indicadores Hemodinamia",
    "Factores de Riesgo - Complicaciones": "Cardio Insights - Factores de Riesgo",
}


def api(method: str, path: str, session: str | None = None, body: dict | None = None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if session:
        req.add_header("X-Metabase-Session", session)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        print(f"  HTTP {exc.code} on {method} {path}: {exc.read().decode()[:300]}")
        raise


def main():
    session = api("POST", "/api/session", body={"username": USER, "password": PASSWORD})["id"]
    print("login ok")

    src = api("GET", f"/api/dashboard/{SOURCE_DASHBOARD_ID}", session=session)
    collection_id = src.get("collection_id")

    results = {}
    for tab_name, new_name in TABS.items():
        print(f"\n== {tab_name} -> {new_name} ==")

        copy = api("POST", f"/api/dashboard/{SOURCE_DASHBOARD_ID}/copy", session=session,
                   body={"name": new_name, "collection_id": collection_id, "is_deep_copy": True})
        new_id = copy["id"]
        print(f"  deep copy created id={new_id}")

        full = api("GET", f"/api/dashboard/{new_id}", session=session)
        tab = next((t for t in full.get("tabs", []) if t["name"] == tab_name), None)
        if tab is None:
            raise RuntimeError(f"tab '{tab_name}' no encontrada en la copia {new_id}")

        keep = [dc for dc in full["dashcards"] if dc.get("dashboard_tab_id") == tab["id"]]
        new_dashcards = [{
            "id": dc["id"],
            "card_id": dc.get("card_id"),
            "row": dc["row"], "col": dc["col"],
            "size_x": dc["size_x"], "size_y": dc["size_y"],
            "series": dc.get("series", []),
            "parameter_mappings": dc.get("parameter_mappings", []),
            "visualization_settings": dc.get("visualization_settings", {}),
            "dashboard_tab_id": None,
        } for dc in keep]

        api("PUT", f"/api/dashboard/{new_id}", session=session, body={
            "dashcards": new_dashcards,
            "tabs": [],
            "enable_embedding": True,
            "embedding_params": {YEAR_PARAM_SLUG: "enabled"},
        })
        print(f"  trimmed to {len(new_dashcards)} dashcards, tabs removed, embedding enabled")
        results[tab_name] = {"id": new_id, "name": new_name}

    print("\n=== RESULT MAPPING ===")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
