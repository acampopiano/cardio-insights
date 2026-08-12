"""Add optional Metabase filters Sede + Facturacion to KPI dashboards.

- sede: SMI | Britanico  (Hbritanico 0/1)
- facturacion: FNR | Otro  (CodDestinoFact = 3 / <> 3)

Uses Metabase optional clauses [[AND ... {{var}} ...]] so leaving a filter
empty does not change the query. Skips stored-proc cards and the Actos pivot
table that already cross-tabs those dimensions.

Run: python scripts/add_kpi_filters.py
"""
from __future__ import annotations

import json
import re
import uuid
import urllib.error
import urllib.request

BASE = "http://190.64.90.170:8810"
USER = "gervasiojaviergarcia@gmail.com"
PASSWORD = "proyecto2026"

# Dashboards currently embedded in the app
DASHBOARD_IDS = [10, 11, 12, 13, 14, 7, 8]

PARAM_SEDE = {
    "id": "f1sede01",
    "name": "Sede",
    "slug": "sede",
    "type": "string/=",
    "sectionId": "string",
    "values_query_type": "list",
    "values_source_type": "static-list",
    "values_source_config": {"values": ["SMI", "Britanico"]},
}
PARAM_FACT = {
    "id": "f1fact01",
    "name": "Facturacion",
    "slug": "facturacion",
    "type": "string/=",
    "sectionId": "string",
    "values_query_type": "list",
    "values_source_type": "static-list",
    "values_source_config": {"values": ["FNR", "Otro"]},
}

YEAR_PARAM_SLUG = "seleccionar_a%C3%B1o"


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


def get_native(dq: dict) -> tuple[str | None, dict, str]:
    """Return (sql, template_tags, format) where format is stages|legacy|none."""
    if not dq:
        return None, {}, "none"
    stages = dq.get("stages") or []
    if stages and isinstance(stages[0], dict) and "native" in stages[0]:
        return stages[0].get("native"), stages[0].get("template-tags") or {}, "stages"
    native = dq.get("native")
    if isinstance(native, dict):
        return native.get("query"), native.get("template-tags") or {}, "legacy"
    return None, {}, "none"


def set_native(dq: dict, sql: str, tags: dict, fmt: str) -> dict:
    dq = json.loads(json.dumps(dq))  # deep copy
    if fmt == "stages":
        dq["stages"][0]["native"] = sql
        dq["stages"][0]["template-tags"] = tags
    elif fmt == "legacy":
        dq.setdefault("native", {})
        dq["native"]["query"] = sql
        dq["native"]["template-tags"] = tags
    return dq


def detect_alias(sql: str) -> str | None:
    m = re.search(
        r"\bFROM\s+(sqlflow_coordina|flow_coordina)\s+(?:AS\s+)?([A-Za-z_][\w]*)",
        sql,
        re.IGNORECASE,
    )
    if m:
        alias = m.group(2)
        # avoid catching WHERE/JOIN keywords as alias if malformed
        if alias.lower() not in {"where", "join", "left", "right", "inner", "outer", "on", "group", "order", "limit"}:
            return alias
    m = re.search(r"\bFROM\s+(sqlflow_coordina|flow_coordina)\b", sql, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def should_skip(sql: str, card_name: str) -> str | None:
    if re.search(r"\bCALL\s+", sql, re.IGNORECASE):
        return "stored procedure"
    # Pivot that already cross-tabs sede x facturacion
    if "Hbritanico" in sql and "CodDestinoFact" in sql and "SMI_FNR" in sql:
        return "pivot sede x facturacion"
    if "Donde se realizo el Acto" in (card_name or ""):
        return "pivot card by name"
    if not re.search(r"\b(sqlflow_coordina|flow_coordina)\b", sql, re.IGNORECASE):
        return "no flow_coordina"
    return None


def filter_clauses(alias: str) -> str:
    a = alias
    return (
        f"\n      [[AND (({{{{sede}}}} = 'SMI' AND COALESCE({a}.Hbritanico, 0) = 0)"
        f" OR ({{{{sede}}}} = 'Britanico' AND {a}.Hbritanico = 1))]]"
        f"\n      [[AND (({{{{facturacion}}}} = 'FNR' AND {a}.CodDestinoFact = 3)"
        f" OR ({{{{facturacion}}}} = 'Otro' AND COALESCE({a}.CodDestinoFact, 0) <> 3))]]"
    )


def ensure_tags(tags: dict) -> dict:
    tags = dict(tags)
    if "sede" not in tags:
        tags["sede"] = {
            "id": str(uuid.uuid4()),
            "name": "sede",
            "display-name": "Sede",
            "type": "text",
            "required": False,
        }
    if "facturacion" not in tags:
        tags["facturacion"] = {
            "id": str(uuid.uuid4()),
            "name": "facturacion",
            "display-name": "Facturacion",
            "type": "text",
            "required": False,
        }
    return tags


def inject_filters(sql: str, alias: str) -> str:
    if "{{sede}}" in sql and "{{facturacion}}" in sql:
        return sql  # already patched
    clauses = filter_clauses(alias)

    # Prefer inserting right after the year template-tag usage
    year_pat = re.compile(r".*\{\{(?:anio|Anio)\}\}.*", re.IGNORECASE)
    lines = sql.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if year_pat.search(line):
            lines.insert(i + 1, clauses + "\n")
            return "".join(lines)

    # Otherwise append at end of WHERE (before GROUP BY / ORDER BY / LIMIT),
    # NEVER right after a bare WHERE — that yields invalid `WHERE AND ...`
    # when the optional clause is active.
    joined = "".join(lines)
    insert_at = None
    for pat in (
        r"\n\s*GROUP\s+BY\b",
        r"\n\s*HAVING\b",
        r"\n\s*ORDER\s+BY\b",
        r"\n\s*LIMIT\b",
    ):
        mm = re.search(pat, joined, re.IGNORECASE)
        if mm:
            insert_at = mm.start()
            break
    if insert_at is None:
        mm = re.search(r";\s*$", joined)
        insert_at = mm.start() if mm else len(joined)
    return joined[:insert_at].rstrip() + "\n" + clauses + "\n" + joined[insert_at:].lstrip("\n")



def update_card(session: str, card_id: int) -> bool:
    card = api("GET", f"/api/card/{card_id}", session=session)
    name = card.get("name") or ""
    dq = card.get("dataset_query") or {}
    sql, tags, fmt = get_native(dq)
    if not sql or fmt == "none":
        print(f"    skip {card_id}: no native SQL")
        return False
    reason = should_skip(sql, name)
    if reason:
        print(f"    skip {card_id}: {reason} | {name[:50]}")
        return False
    alias = detect_alias(sql)
    if not alias:
        print(f"    skip {card_id}: alias not detected | {name[:50]}")
        return False

    new_sql = inject_filters(sql, alias)
    new_tags = ensure_tags(tags)
    new_dq = set_native(dq, new_sql, new_tags, fmt)

    # Minimal PUT payload Metabase accepts
    payload = {
        "name": card["name"],
        "dataset_query": new_dq,
        "display": card.get("display"),
        "visualization_settings": card.get("visualization_settings") or {},
    }
    if card.get("description") is not None:
        payload["description"] = card["description"]
    api("PUT", f"/api/card/{card_id}", session=session, body=payload)
    print(f"    patched {card_id} alias={alias} | {name[:55]}")
    return True


def update_dashboard(session: str, dash_id: int, patched_card_ids: set[int]) -> None:
    dash = api("GET", f"/api/dashboard/{dash_id}", session=session)
    print(f"\n== dashboard {dash_id}: {dash.get('name')} ==")

    params = list(dash.get("parameters") or [])
    # upsert sede/facturacion params
    by_slug = {p.get("slug"): p for p in params}
    if "sede" not in by_slug:
        params.append(PARAM_SEDE)
    else:
        # refresh static list / type
        for i, p in enumerate(params):
            if p.get("slug") == "sede":
                params[i] = {**p, **{k: v for k, v in PARAM_SEDE.items() if k != "id"}, "id": p["id"]}
    if "facturacion" not in by_slug:
        params.append(PARAM_FACT)
    else:
        for i, p in enumerate(params):
            if p.get("slug") == "facturacion":
                params[i] = {**p, **{k: v for k, v in PARAM_FACT.items() if k != "id"}, "id": p["id"]}

    sede_id = next(p["id"] for p in params if p.get("slug") == "sede")
    fact_id = next(p["id"] for p in params if p.get("slug") == "facturacion")

    # Patch cards first, collect which succeeded
    local_patched: set[int] = set()
    for dc in dash.get("dashcards") or []:
        cid = dc.get("card_id")
        if not cid:
            continue
        if update_card(session, int(cid)):
            local_patched.add(int(cid))
            patched_card_ids.add(int(cid))

    # Rebuild dashcards with parameter_mappings
    new_dashcards = []
    for dc in dash.get("dashcards") or []:
        cid = dc.get("card_id")
        mappings = list(dc.get("parameter_mappings") or [])
        if cid and int(cid) in local_patched:
            # remove old sede/fact mappings then add
            mappings = [
                m for m in mappings
                if not (
                    isinstance(m.get("target"), list)
                    and len(m["target"]) >= 2
                    and (
                        (isinstance(m["target"][1], list) and m["target"][1][-1] in ("sede", "facturacion"))
                        or (isinstance(m["target"][1], dict) and "sede" in str(m["target"][1]))
                    )
                )
            ]
            mappings.append({
                "parameter_id": sede_id,
                "card_id": cid,
                "target": ["variable", ["template-tag", "sede"]],
            })
            mappings.append({
                "parameter_id": fact_id,
                "card_id": cid,
                "target": ["variable", ["template-tag", "facturacion"]],
            })

        new_dashcards.append({
            "id": dc["id"],
            "card_id": cid,
            "row": dc["row"],
            "col": dc["col"],
            "size_x": dc["size_x"],
            "size_y": dc["size_y"],
            "series": dc.get("series") or [],
            "parameter_mappings": mappings,
            "visualization_settings": dc.get("visualization_settings") or {},
            "dashboard_tab_id": dc.get("dashboard_tab_id"),
        })

    embedding_params = dict(dash.get("embedding_params") or {})
    embedding_params[YEAR_PARAM_SLUG] = "enabled"
    embedding_params["sede"] = "enabled"
    embedding_params["facturacion"] = "enabled"

    api("PUT", f"/api/dashboard/{dash_id}", session=session, body={
        "parameters": params,
        "dashcards": new_dashcards,
        "tabs": dash.get("tabs") or [],
        "enable_embedding": True,
        "embedding_params": embedding_params,
    })
    print(f"  dashboard saved; patched_cards={len(local_patched)}")


def main() -> None:
    session = api("POST", "/api/session", body={"username": USER, "password": PASSWORD})["id"]
    print("login ok")
    patched: set[int] = set()
    for did in DASHBOARD_IDS:
        update_dashboard(session, did, patched)
    print(f"\nTOTAL patched cards: {len(patched)}")
    print(sorted(patched))


if __name__ == "__main__":
    main()
