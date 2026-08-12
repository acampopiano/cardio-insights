"""Post-backup Metabase KPI improvements:

1. Extend sede/facturacion filters to remaining viable cards
2. Align Hemodinamia Resumen scalar grid (4 x size_6)
3. Shorten Actos centros/medicos tables (SP-backed; can't add sede)

Run: python scripts/improve_kpi_metabase.py
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

CLAUSES_F = """
      [[AND (({{sede}} = 'SMI' AND COALESCE(f.Hbritanico, 0) = 0) OR ({{sede}} = 'Britanico' AND f.Hbritanico = 1))]]
      [[AND (({{facturacion}} = 'FNR' AND f.CodDestinoFact = 3) OR ({{facturacion}} = 'Otro' AND COALESCE(f.CodDestinoFact, 0) <> 3))]]
"""


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


def ensure_tags(tags: dict) -> dict:
    tags = dict(tags or {})
    for name, display in (("sede", "Sede"), ("facturacion", "Facturacion")):
        if name not in tags:
            tags[name] = {
                "id": str(uuid.uuid4()),
                "name": name,
                "display-name": display,
                "type": "text",
                "required": False,
            }
    return tags


def put_card(session: str, card: dict, sql: str, tags: dict) -> None:
    dq = card["dataset_query"]
    dq["stages"][0]["native"] = sql
    dq["stages"][0]["template-tags"] = tags
    api(
        "PUT",
        f"/api/card/{card['id']}",
        session=session,
        body={
            "name": card["name"],
            "dataset_query": dq,
            "display": card.get("display"),
            "visualization_settings": card.get("visualization_settings") or {},
            "description": card.get("description"),
        },
    )


def map_filters_on_dashboard(session: str, dash_id: int, card_ids: set[int]) -> None:
    dash = api("GET", f"/api/dashboard/{dash_id}", session=session)
    sede_id = next(p["id"] for p in dash["parameters"] if p.get("slug") == "sede")
    fact_id = next(p["id"] for p in dash["parameters"] if p.get("slug") == "facturacion")
    new_dcs = []
    for dc in dash.get("dashcards") or []:
        mappings = list(dc.get("parameter_mappings") or [])
        cid = dc.get("card_id")
        if cid and int(cid) in card_ids:
            mappings = [
                m
                for m in mappings
                if "sede" not in str(m.get("target")) and "facturacion" not in str(m.get("target"))
            ]
            mappings.append(
                {"parameter_id": sede_id, "card_id": cid, "target": ["variable", ["template-tag", "sede"]]}
            )
            mappings.append(
                {
                    "parameter_id": fact_id,
                    "card_id": cid,
                    "target": ["variable", ["template-tag", "facturacion"]],
                }
            )
        new_dcs.append(
            {
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
            }
        )
    api(
        "PUT",
        f"/api/dashboard/{dash_id}",
        session=session,
        body={
            "parameters": dash.get("parameters"),
            "dashcards": new_dcs,
            "tabs": dash.get("tabs") or [],
            "enable_embedding": dash.get("enable_embedding"),
            "embedding_params": dash.get("embedding_params"),
        },
    )


def insert_after_year_or_where(sql: str, clauses: str) -> str:
    if "{{sede}}" in sql:
        return sql
    lines = sql.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if re.search(r"\{\{(?:anio|Anio)\}\}", line):
            lines.insert(i + 1, clauses)
            return "".join(lines)
    # before GROUP BY
    joined = "".join(lines)
    m = re.search(r"\n\s*GROUP\s+BY\b", joined, re.I)
    if m:
        return joined[: m.start()].rstrip() + "\n" + clauses + "\n" + joined[m.start() :].lstrip("\n")
    m = re.search(r";\s*$", joined)
    at = m.start() if m else len(joined)
    return joined[:at].rstrip() + "\n" + clauses + "\n" + joined[at:]


def extend_filters(session: str) -> None:
    print("\n== extend filters ==")
    patched: dict[int, set[int]] = {}

    # 393: already has f alias + Anio
    card = api("GET", "/api/card/393", session=session)
    sql = card["dataset_query"]["stages"][0]["native"]
    tags = ensure_tags(card["dataset_query"]["stages"][0].get("template-tags"))
    put_card(session, card, insert_after_year_or_where(sql, CLAUSES_F), tags)
    patched.setdefault(13, set()).add(393)
    print("  patched 393 internacion año")

    # 389: subquery selects limited cols — rewrite to include Hbritanico/CodDestinoFact
    card = api("GET", "/api/card/389", session=session)
    new_sql = """SELECT 
    ms.Tipo AS Sector,
	SUM(m.Estadia) / COUNT(DISTINCT f.Cod) AS Promedio
FROM (
    SELECT Cod, FechaRealizado, Realizado, CodCoordinaReglaMotivo, Hbritanico, CodDestinoFact
    FROM flow_coordina
    WHERE Realizado = 255
      AND CodCoordinaReglaMotivo IN (105, 109, 120)
    ORDER BY FechaRealizado DESC
    LIMIT 35
) f
INNER JOIN flow_coordinamapeo m 
    ON f.Cod = m.CodCoordina
INNER JOIN use_plantacontenido pc 
    ON m.IdPlantaContenido = pc.k_id
INNER JOIN use_plantacontenido pc2 
    ON pc2.k_id = pc.IdContenido
INNER JOIN use_plantacontenido pc3 
    ON pc3.k_id = pc2.IdContenido
INNER JOIN mapeosector ms 
    ON pc2.k_id = ms.IdPlantaContenido
WHERE 1=1
""" + CLAUSES_F + """
GROUP BY ms.Tipo
ORDER BY ms.Tipo;
"""
    tags = ensure_tags({})
    put_card(session, card, new_sql, tags)
    patched.setdefault(13, set()).add(389)
    print("  patched 389 internacion ultimos 35")

    for did, ids in patched.items():
        map_filters_on_dashboard(session, did, ids)
        print(f"  mapped dash {did}: {sorted(ids)}")

    # smoke 393
    res = api(
        "POST",
        "/api/card/393/query",
        session=session,
        body={
            "parameters": [
                {"type": "category", "target": ["variable", ["template-tag", "Anio"]], "value": "2025"},
                {"type": "category", "target": ["variable", ["template-tag", "sede"]], "value": "SMI"},
            ]
        },
    )
    print(f"  393 smoke status={res.get('status')} err={(res.get('error') or '')[:120]}")
    res = api(
        "POST",
        "/api/card/389/query",
        session=session,
        body={
            "parameters": [
                {"type": "category", "target": ["variable", ["template-tag", "sede"]], "value": "SMI"},
            ]
        },
    )
    print(f"  389 smoke status={res.get('status')} err={(res.get('error') or '')[:120]}")


def fix_274_clean(session: str) -> None:
    """Rewrite PTCA risk card cleanly with join + optional filters."""
    card = api("GET", "/api/card/274", session=session)
    sql = """SELECT 
AVG(`call_ptcamaster`.FRhipertension / 255.0) * 100 AS Hipertencion,
AVG(`call_ptcamaster`.FRtabaco / 255.0) * 100 AS Fumador_Actual,
AVG(CASE WHEN `call_ptcamaster`.FRtabacoTipo = 1 THEN 1 ELSE 0 END) * 100 AS Fumador,
AVG(CASE WHEN `call_ptcamaster`.FRtabacoTipo = 2 THEN 1 ELSE 0 END) * 100 AS ExFumador,
AVG(`call_ptcamaster`.FRdiabetes / 255.0) * 100 AS Diabetes,
AVG(CASE WHEN `call_ptcamaster`.FRdiabetesTipo = 1 THEN 1 ELSE 0 END) * 100 AS Diabetes_TipoI,
AVG(CASE WHEN `call_ptcamaster`.FRdiabetesTipo = 2 THEN 1 ELSE 0 END) * 100 AS Diabetes_TipoII,
AVG(`call_ptcamaster`.FRimc) * 100 AS IMC,
AVG(`call_ptcamaster`.FRpeso) * 100 AS Peso,
AVG(`call_ptcamaster`.FRtalla) * 100 AS Talla,
AVG(`call_ptcamaster`.FRhomocisteina / 255.0) * 100 AS Homocisteina,
AVG(`call_ptcamaster`.FRstress / 255.0) * 100 AS Stress,
AVG(`call_ptcamaster`.FRsedentario / 255.0) * 100 AS Sedentario,
AVG(`call_ptcamaster`.FRobesidad / 255.0) * 100 AS Obesidad,
AVG(`call_ptcamaster`.FRanteFam / 255.0) * 100 AS Antecedente_Familiar,
AVG(`call_ptcamaster`.FRanteFamCoro / 255.0) * 100 AS Antecedente_Familiar_Coronario,
AVG(`call_ptcamaster`.FRanteFamMS / 255.0) * 100 AS Antecedente_Familiar_Muerte_Subita
FROM `call_ptcamaster`
JOIN flow_coordina f ON f.Cod = `call_ptcamaster`.CodCoordina
WHERE 1=1
""" + CLAUSES_F
    # preserve any remaining columns from original if longer — keep original body after last AVG line by reading backup
    # For safety, use original SQL and only inject join+where if SELECT already complete
    orig = card["dataset_query"]["stages"][0]["native"]
    if "FROM" in orig.upper() and "call_ptcamaster" in orig:
        # use original SELECT list
        select_part = orig
        # strip existing FROM onward
        select_part = re.split(r"\bFROM\b", orig, maxsplit=1, flags=re.I)[0].rstrip()
        sql = (
            select_part
            + "\nFROM `call_ptcamaster`\n"
            + "JOIN flow_coordina f ON f.Cod = `call_ptcamaster`.CodCoordina\n"
            + "WHERE 1=1\n"
            + CLAUSES_F
        )
    put_card(session, card, sql, ensure_tags({}))
    map_filters_on_dashboard(session, 8, {274})
    # smoke
    res = api(
        "POST",
        "/api/card/274/query",
        session=session,
        body={
            "parameters": [
                {"type": "category", "target": ["variable", ["template-tag", "sede"]], "value": "SMI"}
            ]
        },
    )
    print(f"  274 clean status={res.get('status')} err={(res.get('error') or '')[:120]}")


def fix_pvd_cards(session: str) -> None:
    """Add flow_coordina join via CodFlow for surgery risk/complications cards."""
    print("\n== pvd cards ==")
    for cid, dash_id in [(271, 8), (275, 8), (288, 8)]:
        card = api("GET", f"/api/card/{cid}", session=session)
        orig = card["dataset_query"]["stages"][0]["native"]
        if "{{sede}}" in orig:
            print(f"  {cid} already has sede")
            continue
        if "JOIN flow_coordina" in orig:
            sql = insert_after_year_or_where(orig, CLAUSES_F)
        else:
            # insert join after sqlpvd_master / pvd joins, before WHERE or at end
            if re.search(r"\bWHERE\b", orig, re.I):
                sql = re.sub(
                    r"(\bWHERE\b)",
                    "\nJOIN flow_coordina f ON f.Cod = m.CodFlow\nWHERE",
                    orig,
                    count=1,
                    flags=re.I,
                )
                # ensure alias m exists
                if not re.search(r"\bsqlpvd_master\s+m\b|\bpvd_master\s+m\b", sql, re.I):
                    # try CodFlow from first table
                    sql = re.sub(
                        r"JOIN flow_coordina f ON f\.Cod = m\.CodFlow",
                        "JOIN flow_coordina f ON f.Cod = sqlpvd_master.CodFlow"
                        if "sqlpvd_master" in orig and " m " not in orig
                        else "JOIN flow_coordina f ON f.Cod = m.CodFlow",
                        sql,
                        count=1,
                    )
                sql = insert_after_year_or_where(sql, CLAUSES_F)
            else:
                sql = (
                    orig.rstrip().rstrip(";")
                    + "\nJOIN flow_coordina f ON f.Cod = m.CodFlow\nWHERE 1=1\n"
                    + CLAUSES_F
                )
        # Fix alias: cards use `sqlpvd_master m` 
        if "sqlpvd_master m" in sql or "sqlpvd_master m" in orig or re.search(r"sqlpvd_master\s+m\b", orig):
            sql = sql.replace("f.Cod = sqlpvd_master.CodFlow", "f.Cod = m.CodFlow")
        put_card(session, card, sql, ensure_tags(card["dataset_query"]["stages"][0].get("template-tags")))
        res = api(
            "POST",
            f"/api/card/{cid}/query",
            session=session,
            body={
                "parameters": [
                    {"type": "category", "target": ["variable", ["template-tag", "sede"]], "value": "SMI"}
                ]
            },
        )
        print(f"  {cid} status={res.get('status')} err={(res.get('error') or '')[:150]}")
        if res.get("status") == "completed":
            map_filters_on_dashboard(session, dash_id, {cid})


def align_hemo_scalars(session: str) -> None:
    print("\n== hemo scalar grid ==")
    dash = api("GET", "/api/dashboard/15", session=session)
    # 4 columns of width 6: positions 0,6,12,18
    # Row0 hasta: cat, angio, marca, tavi
    # Row3 año: cat, angio, marca, tavi
    by_card = {}
    for dc in dash["dashcards"]:
        c = dc.get("card") or {}
        name = c.get("name") or ""
        by_card[c.get("id")] = dc
        print(" ", c.get("id"), name)

    layout = {
        # hasta año
        422: (0, 0, 6, 3),   # Cateterismos hasta
        430: (0, 6, 6, 3),   # Angio hasta
        426: (0, 12, 6, 3),  # Marca hasta
        434: (0, 18, 6, 3),  # TAVI hasta
        # año
        428: (3, 0, 6, 3),
        427: (3, 6, 6, 3),
        431: (3, 12, 6, 3),
        433: (3, 18, 6, 3),
        # map/pie stay, shift up because we removed gap rows 3 and 9 intermediate
        421: (6, 0, 12, 10),
        432: (6, 12, 12, 10),
        425: (16, 0, 24, 4),
    }
    new_dcs = []
    for dc in dash["dashcards"]:
        cid = dc.get("card_id")
        if cid in layout:
            r, c, sx, sy = layout[cid]
            row, col, size_x, size_y = r, c, sx, sy
        else:
            row, col, size_x, size_y = dc["row"], dc["col"], dc["size_x"], dc["size_y"]
        new_dcs.append(
            {
                "id": dc["id"],
                "card_id": cid,
                "row": row,
                "col": col,
                "size_x": size_x,
                "size_y": size_y,
                "series": dc.get("series") or [],
                "parameter_mappings": dc.get("parameter_mappings") or [],
                "visualization_settings": dc.get("visualization_settings") or {},
                "dashboard_tab_id": dc.get("dashboard_tab_id"),
            }
        )
    api(
        "PUT",
        "/api/dashboard/15",
        session=session,
        body={
            "parameters": dash.get("parameters"),
            "dashcards": new_dcs,
            "tabs": [],
            "enable_embedding": True,
            "embedding_params": dash.get("embedding_params"),
        },
    )
    print("  dash 15 layout updated to 4x6 scalar grid")


def shorten_actos_tables(session: str) -> None:
    print("\n== actos table heights ==")
    dash = api("GET", "/api/dashboard/10", session=session)
    # card ids 340 centros, 336 medicos — reduce size_y
    shrink = {340: 7, 336: 7}
    new_dcs = []
    for dc in dash["dashcards"]:
        cid = dc.get("card_id")
        sy = shrink.get(cid, dc["size_y"])
        new_dcs.append(
            {
                "id": dc["id"],
                "card_id": cid,
                "row": dc["row"],
                "col": dc["col"],
                "size_x": dc["size_x"],
                "size_y": sy,
                "series": dc.get("series") or [],
                "parameter_mappings": dc.get("parameter_mappings") or [],
                "visualization_settings": dc.get("visualization_settings") or {},
                "dashboard_tab_id": dc.get("dashboard_tab_id"),
            }
        )
    # compact vertical gaps after shrink — optional leave as-is for safety
    api(
        "PUT",
        "/api/dashboard/10",
        session=session,
        body={
            "parameters": dash.get("parameters"),
            "dashcards": new_dcs,
            "tabs": [],
            "enable_embedding": True,
            "embedding_params": dash.get("embedding_params"),
        },
    )
    print("  shortened centros/medicos table heights")


def main() -> None:
    session = api("POST", "/api/session", body={"username": USER, "password": PASSWORD})["id"]
    print("login ok")
    extend_filters(session)
    fix_274_clean(session)
    fix_pvd_cards(session)
    align_hemo_scalars(session)
    shorten_actos_tables(session)
    print("\ndone")


if __name__ == "__main__":
    main()
