"""Crea el dashboard plano de Mortalidad (30 días) en Metabase.

Cards:
  - Scalars: tasa y conteo 30d cirugía / PTCA (año seleccionado)
  - Series: tasa 30d por año (cirugía y PTCA)
  - Tabla: causas de muerte (año de fallecimiento)
  - Tabla: causas en muertes 30d post-cirugía (año del acto)

Filtros: año (requerido en cards con acto), sede y facturación opcionales
(vía flow_coordina). Embedding habilitado.

Run: python scripts/create_mortality_dashboard.py
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid

BASE = "http://190.64.90.170:8810"
USER = "gervasiojaviergarcia@gmail.com"
PASSWORD = "proyecto2026"
DATABASE_ID = 2
COLLECTION_ID = 4

YEAR_PARAM_ID = "17e28864"
SEDE_PARAM_ID = "f1sede01"
FACT_PARAM_ID = "f1fact01"
YEAR_PARAM_SLUG = "seleccionar_a%C3%B1o"

SEDE_CLAUSE = (
    "[[AND (({{sede}} = 'SMI' AND COALESCE(f.Hbritanico, 0) = 0) "
    "OR ({{sede}} = 'Britanico' AND f.Hbritanico = 1))]]"
)
FACT_CLAUSE = (
    "[[AND (({{facturacion}} = 'FNR' AND f.CodDestinoFact = 3) "
    "OR ({{facturacion}} = 'Otro' AND COALESCE(f.CodDestinoFact, 0) <> 3))]]"
)

DEATH_30D = (
    "sf.Fecha > '1900-01-01' AND DATEDIFF(sf.Fecha, f.FechaRealizado) BETWEEN 0 AND 30"
)


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
        print(f"  HTTP {exc.code} on {method} {path}: {exc.read().decode()[:600]}")
        raise


def tag_text(name: str, display: str, required: bool = False, default=None) -> dict:
    tag: dict = {
        "id": str(uuid.uuid4()),
        "name": name,
        "display-name": display,
        "type": "text",
        "required": required,
    }
    if default is not None:
        tag["default"] = default
    return tag


def tags_acto() -> dict:
    return {
        "anio": tag_text("anio", "Anio", required=True, default=["2025"]),
        "sede": tag_text("sede", "Sede", required=False),
        "facturacion": tag_text("facturacion", "Facturacion", required=False),
    }


def tags_year_only() -> dict:
    return {"anio": tag_text("anio", "Anio", required=True, default=["2025"])}


def tags_series() -> dict:
    return {
        "sede": tag_text("sede", "Sede", required=False),
        "facturacion": tag_text("facturacion", "Facturacion", required=False),
    }


def create_card(
    session: str,
    *,
    name: str,
    sql: str,
    display: str,
    template_tags: dict,
    viz: dict | None = None,
) -> int:
    body = {
        "name": name,
        "display": display,
        "visualization_settings": viz or {},
        "collection_id": COLLECTION_ID,
        "dataset_query": {
            "database": DATABASE_ID,
            "type": "native",
            "native": {"query": sql, "template-tags": template_tags},
        },
    }
    card = api("POST", "/api/card", session=session, body=body)
    print(f"  card {card['id']}: {name}")
    return int(card["id"])


def mapping(param_id: str, card_id: int, tag: str) -> dict:
    return {
        "parameter_id": param_id,
        "card_id": card_id,
        "target": ["variable", ["template-tag", tag]],
    }


def dashcard(
    card_id: int,
    *,
    row: int,
    col: int,
    size_x: int,
    size_y: int,
    maps: list[dict],
) -> dict:
    return {
        "id": -card_id,  # negative = new dashcard
        "card_id": card_id,
        "row": row,
        "col": col,
        "size_x": size_x,
        "size_y": size_y,
        "parameter_mappings": maps,
        "visualization_settings": {},
    }


def surgery_rate_sql(year_filter: bool) -> str:
    year = "AND YEAR(f.FechaRealizado) = {{anio}}" if year_filter else ""
    return f"""
SELECT ROUND(
  100.0 * SUM(CASE WHEN {DEATH_30D} THEN 1 ELSE 0 END)
  / NULLIF(COUNT(*), 0), 2
) AS mortalidad_30d_pct
FROM dat_cirugia d
JOIN flow_coordina f ON f.Cod = d.CodCoordina
LEFT JOIN sqlsalud_fallece sf
  ON sf.NroHistoria = f.CodPac AND sf.NroHistoria > 0
WHERE f.Realizado = 255
  AND f.FechaRealizado > '1900-01-01'
  {year}
  {SEDE_CLAUSE}
  {FACT_CLAUSE}
""".strip()


def surgery_count_sql() -> str:
    return f"""
SELECT SUM(CASE WHEN {DEATH_30D} THEN 1 ELSE 0 END) AS muertes_30d
FROM dat_cirugia d
JOIN flow_coordina f ON f.Cod = d.CodCoordina
LEFT JOIN sqlsalud_fallece sf
  ON sf.NroHistoria = f.CodPac AND sf.NroHistoria > 0
WHERE f.Realizado = 255
  AND f.FechaRealizado > '1900-01-01'
  AND YEAR(f.FechaRealizado) = {{{{anio}}}}
  {SEDE_CLAUSE}
  {FACT_CLAUSE}
""".strip()


def ptca_rate_sql(year_filter: bool) -> str:
    year = "AND YEAR(f.FechaRealizado) = {{anio}}" if year_filter else ""
    return f"""
SELECT ROUND(
  100.0 * SUM(CASE WHEN {DEATH_30D} THEN 1 ELSE 0 END)
  / NULLIF(COUNT(*), 0), 2
) AS mortalidad_30d_pct
FROM call_ptcamaster c
JOIN flow_coordina f ON f.Cod = c.CodCoordina
LEFT JOIN sqlsalud_fallece sf
  ON sf.NroHistoria = f.CodPac AND sf.NroHistoria > 0
WHERE f.Realizado = 255
  AND f.FechaRealizado > '1900-01-01'
  {year}
  {SEDE_CLAUSE}
  {FACT_CLAUSE}
""".strip()


def ptca_count_sql() -> str:
    return f"""
SELECT SUM(CASE WHEN {DEATH_30D} THEN 1 ELSE 0 END) AS muertes_30d
FROM call_ptcamaster c
JOIN flow_coordina f ON f.Cod = c.CodCoordina
LEFT JOIN sqlsalud_fallece sf
  ON sf.NroHistoria = f.CodPac AND sf.NroHistoria > 0
WHERE f.Realizado = 255
  AND f.FechaRealizado > '1900-01-01'
  AND YEAR(f.FechaRealizado) = {{{{anio}}}}
  {SEDE_CLAUSE}
  {FACT_CLAUSE}
""".strip()


def surgery_series_sql() -> str:
    return f"""
SELECT YEAR(f.FechaRealizado) AS anio,
  ROUND(
    100.0 * SUM(CASE WHEN {DEATH_30D} THEN 1 ELSE 0 END)
    / NULLIF(COUNT(*), 0), 2
  ) AS mortalidad_30d_pct
FROM dat_cirugia d
JOIN flow_coordina f ON f.Cod = d.CodCoordina
LEFT JOIN sqlsalud_fallece sf
  ON sf.NroHistoria = f.CodPac AND sf.NroHistoria > 0
WHERE f.Realizado = 255
  AND f.FechaRealizado > '1900-01-01'
  {SEDE_CLAUSE}
  {FACT_CLAUSE}
GROUP BY YEAR(f.FechaRealizado)
ORDER BY anio
""".strip()


def ptca_series_sql() -> str:
    return f"""
SELECT YEAR(f.FechaRealizado) AS anio,
  ROUND(
    100.0 * SUM(CASE WHEN {DEATH_30D} THEN 1 ELSE 0 END)
    / NULLIF(COUNT(*), 0), 2
  ) AS mortalidad_30d_pct
FROM call_ptcamaster c
JOIN flow_coordina f ON f.Cod = c.CodCoordina
LEFT JOIN sqlsalud_fallece sf
  ON sf.NroHistoria = f.CodPac AND sf.NroHistoria > 0
WHERE f.Realizado = 255
  AND f.FechaRealizado > '1900-01-01'
  {SEDE_CLAUSE}
  {FACT_CLAUSE}
GROUP BY YEAR(f.FechaRealizado)
ORDER BY anio
""".strip()


def causas_sql() -> str:
    return """
SELECT COALESCE(NULLIF(TRIM(sf.Tipo), ''), 'Sin identificar') AS causa,
  COUNT(*) AS total
FROM sqlsalud_fallece sf
WHERE sf.Fecha > '1900-01-01'
  AND sf.NroHistoria > 0
  AND YEAR(sf.Fecha) = {{anio}}
GROUP BY causa
ORDER BY total DESC
""".strip()


def causas_post_cirugia_sql() -> str:
    return f"""
SELECT COALESCE(NULLIF(TRIM(sf.Tipo), ''), 'Sin identificar') AS causa,
  COUNT(*) AS total
FROM dat_cirugia d
JOIN flow_coordina f ON f.Cod = d.CodCoordina
JOIN sqlsalud_fallece sf
  ON sf.NroHistoria = f.CodPac AND sf.NroHistoria > 0
WHERE f.Realizado = 255
  AND f.FechaRealizado > '1900-01-01'
  AND YEAR(f.FechaRealizado) = {{{{anio}}}}
  AND {DEATH_30D}
  {SEDE_CLAUSE}
  {FACT_CLAUSE}
GROUP BY causa
ORDER BY total DESC
""".strip()


def main() -> None:
    session = api("POST", "/api/session", body={"username": USER, "password": PASSWORD})["id"]
    print("login ok")

    print("\n== creating cards ==")
    c_surg_rate = create_card(
        session,
        name="Mortalidad cirugía 30d % (año seleccionado)",
        sql=surgery_rate_sql(True),
        display="scalar",
        template_tags=tags_acto(),
        viz={"scalar.field": "mortalidad_30d_pct"},
    )
    c_surg_n = create_card(
        session,
        name="Muertes cirugía 30d (año seleccionado)",
        sql=surgery_count_sql(),
        display="scalar",
        template_tags=tags_acto(),
    )
    c_ptca_rate = create_card(
        session,
        name="Mortalidad PTCA 30d % (año seleccionado)",
        sql=ptca_rate_sql(True),
        display="scalar",
        template_tags=tags_acto(),
        viz={"scalar.field": "mortalidad_30d_pct"},
    )
    c_ptca_n = create_card(
        session,
        name="Muertes PTCA 30d (año seleccionado)",
        sql=ptca_count_sql(),
        display="scalar",
        template_tags=tags_acto(),
    )
    c_surg_series = create_card(
        session,
        name="Mortalidad cirugía 30d % por año",
        sql=surgery_series_sql(),
        display="line",
        template_tags=tags_series(),
        viz={
            "graph.dimensions": ["anio"],
            "graph.metrics": ["mortalidad_30d_pct"],
            "graph.x_axis.title_text": "Año",
            "graph.y_axis.title_text": "% mortalidad 30d",
        },
    )
    c_ptca_series = create_card(
        session,
        name="Mortalidad PTCA 30d % por año",
        sql=ptca_series_sql(),
        display="line",
        template_tags=tags_series(),
        viz={
            "graph.dimensions": ["anio"],
            "graph.metrics": ["mortalidad_30d_pct"],
            "graph.x_axis.title_text": "Año",
            "graph.y_axis.title_text": "% mortalidad 30d",
        },
    )
    c_causas = create_card(
        session,
        name="Todas las muertes del año · por causa",
        sql=causas_sql(),
        display="pie",
        template_tags=tags_year_only(),
        viz={
            "pie.dimension": "causa",
            "pie.metric": "total",
            "pie.show_legend": True,
            "pie.show_labels": True,
            "pie.percent_visibility": "inside",
            "pie.slice_threshold": 0,
            "series_settings": {
                "Cardíaca": {"color": "#DC2626"},
                "Sin Identificar": {"color": "#94A3B8"},
                "Otras": {"color": "#64748B"},
                "Neurológica": {"color": "#7C3AED"},
                "Renal": {"color": "#2563EB"},
                "Vascular": {"color": "#EA580C"},
                "Sepsis": {"color": "#CA8A04"},
                "Pulmonar": {"color": "#0891B2"},
                "Hemorragia": {"color": "#BE123C"},
                "Tumor": {"color": "#4F46E5"},
                "Suicidio": {"color": "#57534E"},
            },
        },
    )
    c_causas_cir = create_card(
        session,
        name="Solo muertes 30d post-cirugía · por causa",
        sql=causas_post_cirugia_sql(),
        display="row",
        template_tags=tags_acto(),
        viz={
            "graph.dimensions": ["causa"],
            "graph.metrics": ["total"],
            "graph.colors": ["#0F766E"],
            "graph.x_axis.title_text": "fallecidos",
            "graph.y_axis.title_text": "",
            "graph.show_values": True,
            "series_settings": {"total": {"color": "#0F766E", "title": "fallecidos"}},
        },
    )

    parameters = [
        {
            "slug": YEAR_PARAM_SLUG,
            "values_query_type": "list",
            "default": ["2025"],
            "name": "Seleccionar año",
            "type": "string/=",
            "sectionId": "string",
            "values_source_type": "static-list",
            "id": YEAR_PARAM_ID,
            "values_source_config": {
                "values": [[str(y)] for y in range(2025, 2004, -1)]
            },
        },
        {
            "id": SEDE_PARAM_ID,
            "name": "Sede",
            "slug": "sede",
            "type": "string/=",
            "sectionId": "string",
            "values_query_type": "list",
            "values_source_type": "static-list",
            "values_source_config": {"values": ["SMI", "Britanico"]},
        },
        {
            "id": FACT_PARAM_ID,
            "name": "Facturacion",
            "slug": "facturacion",
            "type": "string/=",
            "sectionId": "string",
            "values_query_type": "list",
            "values_source_type": "static-list",
            "values_source_config": {"values": ["FNR", "Otro"]},
        },
    ]

    def maps_acto(cid: int) -> list[dict]:
        return [
            mapping(YEAR_PARAM_ID, cid, "anio"),
            mapping(SEDE_PARAM_ID, cid, "sede"),
            mapping(FACT_PARAM_ID, cid, "facturacion"),
        ]

    def maps_series(cid: int) -> list[dict]:
        return [
            mapping(SEDE_PARAM_ID, cid, "sede"),
            mapping(FACT_PARAM_ID, cid, "facturacion"),
        ]

    def maps_year(cid: int) -> list[dict]:
        return [mapping(YEAR_PARAM_ID, cid, "anio")]

    dashcards = [
        dashcard(c_surg_rate, row=0, col=0, size_x=6, size_y=4, maps=maps_acto(c_surg_rate)),
        dashcard(c_surg_n, row=0, col=6, size_x=6, size_y=4, maps=maps_acto(c_surg_n)),
        dashcard(c_ptca_rate, row=0, col=12, size_x=6, size_y=4, maps=maps_acto(c_ptca_rate)),
        dashcard(c_ptca_n, row=0, col=18, size_x=6, size_y=4, maps=maps_acto(c_ptca_n)),
        dashcard(c_surg_series, row=4, col=0, size_x=12, size_y=8, maps=maps_series(c_surg_series)),
        dashcard(c_ptca_series, row=4, col=12, size_x=12, size_y=8, maps=maps_series(c_ptca_series)),
        dashcard(c_causas, row=12, col=0, size_x=12, size_y=8, maps=maps_year(c_causas)),
        dashcard(
            c_causas_cir, row=12, col=12, size_x=12, size_y=8, maps=maps_acto(c_causas_cir)
        ),
    ]

    print("\n== creating dashboard ==")
    dash = api(
        "POST",
        "/api/dashboard",
        session=session,
        body={
            "name": "Cardio Insights - Mortalidad",
            "description": (
                "Mortalidad a 30 días post-acto (cirugía y PTCA) vía sqlsalud_fallece, "
                "más desglose por causa."
            ),
            "collection_id": COLLECTION_ID,
            "parameters": parameters,
        },
    )
    dash_id = int(dash["id"])
    print(f"  dashboard id={dash_id}")

    api(
        "PUT",
        f"/api/dashboard/{dash_id}",
        session=session,
        body={
            "parameters": parameters,
            "dashcards": dashcards,
            "enable_embedding": True,
            "embedding_params": {
                YEAR_PARAM_SLUG: "enabled",
                "sede": "enabled",
                "facturacion": "enabled",
            },
        },
    )
    print("  layout + embedding ok")
    print(f"\nDONE dashboard_id={dash_id}")
    print("Actualizar CATEGORIES en KpisPage.tsx con este id.")


if __name__ == "__main__":
    main()
