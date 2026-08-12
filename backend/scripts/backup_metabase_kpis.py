"""Backup Metabase KPI dashboards + their cards to local JSON.

Creates a timestamped folder under backend/metabase-backups/ with:
  - manifest.json  (ids, names, card counts)
  - dashboards/{id}.json
  - cards/{id}.json

Restore is not fully automatic (Metabase IDs change on recreate), but the dump
is enough to recreate questions/dashboards or compare diffs after experiments.

Run: python scripts/backup_metabase_kpis.py
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "http://190.64.90.170:8810"
USER = "gervasiojaviergarcia@gmail.com"
PASSWORD = "proyecto2026"

# Original + parents + flat KPI sections currently embedded in the app.
DASHBOARD_IDS = [2, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17]

OUT_ROOT = Path(__file__).resolve().parents[1] / "metabase-backups"


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
        print(f"  HTTP {exc.code} on {method} {path}: {exc.read().decode()[:300]}")
        raise


def main() -> None:
    session = api("POST", "/api/session", body={"username": USER, "password": PASSWORD})["id"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = OUT_ROOT / stamp
    dash_dir = out_dir / "dashboards"
    card_dir = out_dir / "cards"
    dash_dir.mkdir(parents=True, exist_ok=True)
    card_dir.mkdir(parents=True, exist_ok=True)

    print(f"backup -> {out_dir}")

    card_ids: set[int] = set()
    manifest_dashboards = []

    for dash_id in DASHBOARD_IDS:
        print(f"  dashboard {dash_id}...")
        dash = api("GET", f"/api/dashboard/{dash_id}", session=session)
        (dash_dir / f"{dash_id}.json").write_text(
            json.dumps(dash, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        for dc in dash.get("dashcards") or []:
            cid = dc.get("card_id")
            if cid:
                card_ids.add(int(cid))
            # series cards also count
            for s in dc.get("series") or []:
                if isinstance(s, dict) and s.get("id"):
                    card_ids.add(int(s["id"]))
                elif isinstance(s, int):
                    card_ids.add(s)
        manifest_dashboards.append({
            "id": dash_id,
            "name": dash.get("name"),
            "enable_embedding": dash.get("enable_embedding"),
            "parameters": [
                {"id": p.get("id"), "name": p.get("name"), "slug": p.get("slug"), "type": p.get("type")}
                for p in (dash.get("parameters") or [])
            ],
            "embedding_params": dash.get("embedding_params"),
            "dashcard_count": len(dash.get("dashcards") or []),
            "card_ids": sorted(
                int(dc["card_id"]) for dc in (dash.get("dashcards") or []) if dc.get("card_id")
            ),
        })

    print(f"  fetching {len(card_ids)} cards...")
    for cid in sorted(card_ids):
        card = api("GET", f"/api/card/{cid}", session=session)
        (card_dir / f"{cid}.json").write_text(
            json.dumps(card, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    manifest = {
        "created_at": stamp,
        "metabase_site": BASE,
        "dashboard_ids": DASHBOARD_IDS,
        "dashboards": manifest_dashboards,
        "card_count": len(card_ids),
        "card_ids": sorted(card_ids),
        "notes": (
            "Full JSON dump of KPI-related dashboards and cards. "
            "To roll back after experiments, recreate from these definitions "
            "or restore card SQL/dataset_query and dashboard layout/params manually via API."
        ),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # Convenience pointer to latest backup
    (OUT_ROOT / "LATEST.txt").write_text(stamp + "\n", encoding="utf-8")

    print(f"\ndone: {len(manifest_dashboards)} dashboards, {len(card_ids)} cards")
    print(f"path: {out_dir}")


if __name__ == "__main__":
    main()
