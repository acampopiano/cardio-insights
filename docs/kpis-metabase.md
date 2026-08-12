# KPIs (dashboards de Metabase embebidos)

La sección **KPIs** muestra los indicadores clínicos del INCC embebiendo dashboards de
**Metabase** dentro del frontend. Las categorías son **cards planas de primer nivel**
(sin sub-navegación anidada): cada card abre un dashboard independiente, más corto, para
reducir el scroll anidado típico de embeds densos.

La integración usa **Static Embedding** de Metabase: el backend firma un **JWT** con la
*embedding secret key* y devuelve una URL `/embed/dashboard/{token}` que el frontend usa
como `src` de un `<iframe>`. Ni la secret key ni las credenciales de Metabase se exponen
nunca al navegador.

---

## Cómo funciona (flujo)

```
Usuario abre KPIs y elige una categoría (card)
        │
        ▼
1) Frontend pide el token:  GET /api/v1/metabase/embed-token?dashboard_id=<id>   (requiere login)
        │
        ▼
2) Backend firma un JWT (HS256) con METABASE_SECRET_KEY:
   { resource: { dashboard: <id> }, params: {}, exp: now + TTL }
   y arma la URL:  {METABASE_SITE_URL}/embed/dashboard/{token}#bordered=false&titled=false&background=false&downloads=true
        │
        ▼
3) Frontend renderiza un <iframe> a casi pantalla completa (solo header de app + barra Volver)
        │
        ├── el token expira: el frontend lo renueva solo ~60s antes de expirar (expires_in)
        ▼
Metabase valida el JWT y sirve el dashboard embebido (solo lectura)
```

Cada categoría corresponde a un `dashboard_id` distinto. El token se pide **de forma
perezosa** al abrir una card. `titled=false` evita duplicar el título (ya está en el header
de la app) y gana espacio vertical.

---

## Archivos

Backend:

- `backend/app/api/v1/metabase.py` — endpoint `GET /api/v1/metabase/embed-token`.
- `backend/app/core/config.py` — settings `METABASE_*`.
- `backend/scripts/split_metabase_dashboard.py` — crea los dashboards por tab a partir del
  original multi-tab (id 2 → 5/6/7/8).
- `backend/scripts/split_kpi_sections.py` — parte Actos (5) y Cirugía (6) en secciones más
  cortas por rango de `row` del layout (ids 10–14).
- `backend/scripts/polish_kpi_dashboards.py` — pulido visual: quita “- Duplicar”, aclara
  totales acumulado vs año, elimina encabezados de texto redundantes y parte Hemodinamia
  (7 → 15 Resumen + 16 Evolución).
- `backend/scripts/backup_metabase_kpis.py` — respaldo JSON de dashboards/cards.
- `backend/scripts/create_mortality_dashboard.py` — crea el dashboard plano **Mortalidad** (id 17)
  con tasas/conteos 30d cirugía/PTCA, series anuales y causas (`sqlsalud_fallece`).

Frontend:

- `frontend/src/routes/KpisPage.tsx` — grilla plana de cards + embed casi fullscreen.
- `frontend/src/features/metabase/metabaseApi.ts` — cliente HTTP.
- `frontend/src/lib/navigation.ts` — `/kpis` disponible.

---

## Categorías planas (mapeo actual)

Origen histórico: dashboard **"Cardio Insights - KPI" (id 2)** con tabs → dashboards 5–8
(una tab cada uno). Luego Actos y Cirugía se partieron por densidad:

| Card (label en la UI) | Dashboard Metabase | id |
| --- | --- | --- |
| Actos · Volumen y origen | Cardio Insights - Actos - Volumen y origen | 10 |
| Actos · Por procedimiento | Cardio Insights - Actos - Por procedimiento | 11 |
| Cirugía · Indicadores | Cardio Insights - Cirugia - Indicadores | 12 |
| Cirugía · Pacientes y reintervenciones | Cardio Insights - Cirugia - Pacientes y reintervenciones | 13 |
| Cirugía · Perfil clínico | Cardio Insights - Cirugia - Perfil clinico | 14 |
| Hemodinamia · Resumen | Cardio Insights - Hemodinamia - Resumen | 15 |
| Hemodinamia · Evolución | Cardio Insights - Hemodinamia - Evolucion | 16 |
| Factores de Riesgo - Complicaciones | Cardio Insights - Factores de Riesgo | 8 |
| Mortalidad | Cardio Insights - Mortalidad | 17 |

Los ids están en `CATEGORIES` (`KpisPage.tsx`). Quedan intactos: **id 2** (original con tabs),
los “padre” **5** y **6** (Actos/Cirugía completos) y **7** (Hemodinamia completa; ya no se
embebe en la UI).

Criterio de producto: **sin anidar**. Nombres compuestos (`Actos · …`) agrupan mentalmente
sin una pantalla intermedia de subcategorías.

Cada dashboard embebible tiene:

- `enable_embedding = true`
- filtros habilitados en el embed (`embedding_params`):
  - **Seleccionar año** (`seleccionar_a%C3%B1o`) — obligatorio en la mayoría de las cards
  - **Sede** (`sede`) — valores `SMI` | `Britanico` (opcional; `Hbritanico` 0/1)
  - **Facturacion** (`facturacion`) — valores `FNR` | `Otro` (opcional; `CodDestinoFact = 3` / `<> 3`)

Los filtros de sede/facturación usan cláusulas opcionales de Metabase (`[[AND ...]]`):
si no se eligen, la consulta queda igual que antes. Están cableados en las preguntas que
usan `flow_coordina` / `sqlflow_coordina` (~42 cards).

**No aplican** (a propósito o por límite técnico) a:

- Stored procedures (`CALL ActosPorMes` / `MedicosPorMes`) — no se puede inyectar sede sin reescribir el SP
- La tabla pivot “Dónde se realizó / a quién se factura” (ya cruza sede × facturación)
- Tops clínicos de perfil (diagnósticos/procedimientos/obs) sin join estable a sede en la query actual
- Stent con/sin droga (tabla de stock, sin `flow_coordina`)

Script: `backend/scripts/add_kpi_filters.py` (base) y `improve_kpi_metabase.py` (extensiones).

> Requisito: Static embedding habilitado en Metabase Admin → Embedding.

### UX del embed

- Iframe a `h-[calc(100vh-3.5rem)]` (casi todo el viewport; solo el header de la app).
- Barra compacta Volver / título / Actualizar; sin `max-w-6xl`.
- Un solo scroll relevante: el del contenido de Metabase dentro del iframe.

---

## Configuración (`backend/.env`)

```env
METABASE_SITE_URL=http://190.64.90.170:8810
METABASE_SECRET_KEY=<secret-de-embedding>
METABASE_DEFAULT_DASHBOARD_ID=2
```

- `metabase_embed_token_ttl_seconds` (default `3600` en `config.py`): vida del token.
- Si la secret queda en `change-me`, el endpoint responde **503**.

---

## Regenerar dashboards

### 1) Por tab (desde el original id 2)

```bash
cd backend
python scripts/split_metabase_dashboard.py
```

Crea/recrea las copias por tab (hoy: 5 Actos, 6 Cirugía, 7 Hemodinamia, 8 Factores).

### 2) Por sección (Actos y Cirugía densos)

```bash
cd backend
python scripts/split_kpi_sections.py
```

Deep-copy de 5 y 6, recorta por rangos de `row`, normaliza el layout a row 0, habilita
embedding e imprime el mapeo `nombre → id`. Actualizar `CATEGORIES` si los ids cambian.

Rangos actuales en el script:

- Actos: rows `0–37` (volumen/origen) y `38+` (por procedimiento)
- Cirugía: `0–16` (indicadores), `17–40` (pacientes/reintervenciones), `41+` (perfil)

> Si se edita el original (id 2) o los padres (5/6), hay que regenerar en cascada y
> actualizar los ids en el frontend. Las copias **no** se sincronizan solas.

---

## Respaldo (antes de experimentos)

Antes de tocar filtros o layouts en Metabase, conviene un dump local:

```bash
cd backend
python scripts/backup_metabase_kpis.py
```

Guarda en `backend/metabase-backups/<timestamp>/`:

- `manifest.json` — índice de dashboards/cards
- `dashboards/{id}.json` — definición completa (layout, params, embedding)
- `cards/{id}.json` — preguntas (SQL / dataset_query)

Dashboards incluidos por defecto: **2, 5–8, 10–17**. El archivo `metabase-backups/LATEST.txt`
apunta al backup más reciente.

> No es un restore one-click (los ids cambian al recrear). Sirve para comparar,
> recuperar SQL y reconstruir dashboards vía API o a mano si algo sale mal.

---

## Agregar / cambiar una categoría

1. Dashboard en Metabase con `enable_embedding = true` (sin tabs).
2. Anotar su `id`.
3. Entrada en `CATEGORIES` (`KpisPage.tsx`): `dashboardId`, `label`, `description`, `icon`.

El backend no requiere cambios: firma cualquier `dashboard_id`.

---

## Probar

1. Backend (`:8000`) y frontend (`:5173`) levantados.
2. Login → **KPIs** → elegir una card (ej. “Actos · Volumen y origen”).
3. Debe verse a casi pantalla completa, sin título duplicado de Metabase, y con menos scroll
   que el dashboard completo de Actos.

---

## Seguridad y limitaciones

- Embed requiere login de la app; secret key solo en backend.
- Static embedding = solo lectura.
- URL de Metabase en **HTTP**: en HTTPS del frontend puede haber mixed content.
- Sin auto-altura del iframe (cross-origin); se prioriza viewport completo + dashboards cortos.
- Copias no sincronizadas con el original: ver “Regenerar dashboards”.
