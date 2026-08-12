"""Fix KPI cards where optional sede/facturacion clauses were inserted
right after a bare WHERE (invalid SQL when the optional clause is active).

Moves the [[AND ... {{sede}} ...]] / [[AND ... {{facturacion}} ...]] block
to the end of the WHERE clause (before GROUP BY / ORDER BY / LIMIT).

Run: python scripts/fix_kpi_filter_where.py
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

BASE = "http://190.64.90.170:8810"
USER = "gervasiojaviergarcia@gmail.com"
PASSWORD = "proyecto2026"
DASHBOARD_IDS = [10, 11, 12, 13, 14, 7, 8]

CLAUSE_RE = re.compile(
    r"\n?\s*\[\[AND \(\(\{\{sede\}\}.*?\]\]\s*"
    r"\n?\s*\[\[AND \(\(\{\{facturacion\}\}.*?\]\]\s*",
    re.IGNORECASE | re.DOTALL,
)
BAD_WHERE_RE = re.compile(r"WHERE\s*(\n\s*)+\[\[AND", re.IGNORECASE)


def api(method: str, path: str, session: str | None = None, body: dict | None = None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if session:
        req.add_header("X-Metabase-Session", session)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        print(f"  HTTP {exc.code}: {exc.read().decode()[:300]}")
        raise


def fix_sql(sql: str) -> str | None:
    if not BAD_WHERE_RE.search(sql):
        return None
    m = CLAUSE_RE.search(sql)
    if not m:
        return None
    clauses = m.group(0).strip("\n")
    without = CLAUSE_RE.sub("\n", sql, count=1)

    # Insert before GROUP BY / HAVING / ORDER BY / LIMIT / trailing semicolon block
    insert_at = None
    for pat in (
        r"\n\s*GROUP\s+BY\b",
        r"\n\s*HAVING\b",
        r"\n\s*ORDER\s+BY\b",
        r"\n\s*LIMIT\b",
    ):
        mm = re.search(pat, without, re.IGNORECASE)
        if mm:
            insert_at = mm.start()
            break
    if insert_at is None:
        # before final semicolon if any
        mm = re.search(r";\s*$", without)
        insert_at = mm.start() if mm else len(without)

    fixed = without[:insert_at].rstrip() + "\n      " + clauses + "\n" + without[insert_at:].lstrip("\n")
    # Ensure WHERE still has a real predicate first (no leading AND after WHERE)
    if BAD_WHERE_RE.search(fixed):
        raise RuntimeError("fix failed: still broken AFTER WHERE")
    return fixed


def main() -> None:
    session = api("POST", "/api/session", body={"username": USER, "password": PASSWORD})["id"]
    print("login ok")
    fixed_ids = []

    for did in DASHBOARD_IDS:
        dash = api("GET", f"/api/dashboard/{did}", session=session)
        for dc in dash.get("dashcards") or []:
            cid = dc.get("card_id")
            if not cid:
                continue
            card = api("GET", f"/api/card/{cid}", session=session)
            dq = card.get("dataset_query") or {}
            stages = dq.get("stages") or []
            if not stages or "native" not in stages[0]:
                continue
            sql = stages[0].get("native") or ""
            if "{{sede}}" not in sql:
                continue
            new_sql = fix_sql(sql)
            if not new_sql:
                continue
            stages[0]["native"] = new_sql
            api(
                "PUT",
                f"/api/card/{cid}",
                session=session,
                body={
                    "name": card["name"],
                    "dataset_query": dq,
                    "display": card.get("display"),
                    "visualization_settings": card.get("visualization_settings") or {},
                },
            )
            print(f"  fixed card {cid} | {card.get('name', '')[:60]}")
            fixed_ids.append(cid)

            # smoke test with sede=SMI
            res = api(
                "POST",
                f"/api/card/{cid}/query",
                session=session,
                body={
                    "parameters": [
                        {
                            "type": "category",
                            "target": ["variable", ["template-tag", "sede"]],
                            "value": "SMI",
                        }
                    ]
                },
            )
            status = res.get("status")
            nrows = len((res.get("data") or {}).get("rows") or [])
            err = (res.get("error") or "")[:120]
            print(f"    query sede=SMI -> status={status} rows={nrows} err={err}")

    print(f"\ndone, fixed {len(fixed_ids)} cards: {fixed_ids}")


if __name__ == "__main__":
    main()
