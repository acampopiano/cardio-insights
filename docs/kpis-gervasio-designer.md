# KPIs Gervasio - Version mejorada para KPI Designer

Fecha: 2026-05-15
Objetivo: convertir las KPIs propuestas a formato compatible con KPI Designer y dejar una guia de uso paso a paso.

## 1) Regla clave de compatibilidad

En KPI Designer, la SQL debe devolver exactamente:

- period
- value

Si la consulta devuelve centro, tipo_acto, sexo u otras columnas extra, no sirve directo para KPI Designer. En esos casos hay que convertirla a una metrica agregada por periodo (por ejemplo top, promedio, porcentaje, total).

Ademas:

- Usar flow_coordina (no sqlflow_coordina ni flow_coordiana).
- Usar placeholders para que el backend aplique filtros y granularidad:
  - {period_expr}
  - {date_clause}

## 2) Catalogo recomendado (listo para crear)

## KPI 1 - centros_que_envian_pacientes

Que mide:

- Total de actos realizados que vienen de centros asistenciales con cobertura registrada.

Para que sirve:

- Seguir tendencia de derivacion externa por mes/semana/dia.

SQL:

```sql
SELECT
  {period_expr} AS period,
  COUNT(*) AS value
FROM flow_coordina f
INNER JOIN stk_cartera stk ON stk.CodPacFichaCubre = f.CodSeguroCoo
WHERE f.Realizado = 255
  AND f.CodSeguroCoo > 0
  {date_clause}
GROUP BY {period_expr}
ORDER BY period
```

## KPI 2 - top_centro_por_periodo

Que mide:

- Cantidad de actos del centro lider en cada periodo.

Para que sirve:

- Detectar concentracion de demanda por centro derivador.

SQL:

```sql
SELECT
  t.period AS period,
  MAX(t.total_actos) AS value
FROM (
  SELECT
    {period_expr} AS period,
    f.CodSeguroCoo AS centro_cod,
    COUNT(*) AS total_actos
  FROM flow_coordina f
  INNER JOIN stk_cartera stk ON stk.CodPacFichaCubre = f.CodSeguroCoo
  WHERE f.Realizado = 255
    AND f.CodSeguroCoo > 0
    {date_clause}
  GROUP BY {period_expr}, f.CodSeguroCoo
) t
GROUP BY t.period
ORDER BY t.period
```

## KPI 3 - volumen_mensual_total

Que mide:

- Volumen total de actividad realizada.

Para que sirve:

- KPI base de produccion asistencial.

SQL:

```sql
SELECT
  {period_expr} AS period,
  COUNT(*) AS value
FROM flow_coordina f
WHERE f.Realizado = 255
  AND f.FechaRealizado > '1900-01-01'
  {date_clause}
GROUP BY {period_expr}
ORDER BY period
```

## KPI 4 - volumen_cirugias_mensual

Que mide:

- Cirugias realizadas por periodo (motivos quirurgicos 105/109/120).

Para que sirve:

- Seguimiento de carga quirurgica.

SQL:

```sql
SELECT
  {period_expr} AS period,
  COUNT(*) AS value
FROM flow_coordina f
WHERE f.Realizado = 255
  AND f.CodCoordinaReglaMotivo IN (105, 109, 120)
  AND f.FechaRealizado > '1900-01-01'
  {date_clause}
GROUP BY {period_expr}
ORDER BY period
```

## KPI 5 - reintervenciones_mensual

Que mide:

- Cantidad de actos base que tuvieron al menos una reintervencion posterior.

Para que sirve:

- Seguimiento de casos que requirieron nueva intervencion.

SQL:

```sql
SELECT
  {period_expr} AS period,
  COUNT(DISTINCT f.Cod) AS value
FROM flow_coordina f
INNER JOIN flow_coordina ff
  ON ff.CodActo = f.Cod
 AND ff.FechaRealizado > f.FechaRealizado
 AND ff.Realizado = 255
WHERE f.Realizado = 255
  AND f.CodCoordinaReglaMotivo IN (105, 109, 120)
  AND f.FechaRealizado > '1900-01-01'
  {date_clause}
GROUP BY {period_expr}
ORDER BY period
```

## KPI 6 - hemodinamia_volumen_mensual

Que mide:

- Total de actos de hemodinamia por periodo.

Para que sirve:

- Monitorear actividad del sector hemodinamia.

SQL:

```sql
SELECT
  {period_expr} AS period,
  COUNT(*) AS value
FROM flow_coordina f
WHERE f.Realizado = 255
  AND f.sTecnica = 'He'
  AND f.FechaRealizado > '1900-01-01'
  {date_clause}
GROUP BY {period_expr}
ORDER BY period
```

## KPI 7 - hemodinamia_top_tipo_por_periodo

Que mide:

- Cantidad del tipo de acto de hemodinamia mas frecuente por periodo.

Para que sirve:

- Ver picos de un subtipo dominante sin romper la regla period/value.

SQL:

```sql
SELECT
  t.period AS period,
  MAX(t.total_tipo) AS value
FROM (
  SELECT
    {period_expr} AS period,
    COALESCE(f.sTecnicaDetalle, 'SIN_DETALLE') AS tipo_acto,
    COUNT(*) AS total_tipo
  FROM flow_coordina f
  WHERE f.Realizado = 255
    AND f.sTecnica = 'He'
    AND f.FechaRealizado > '1900-01-01'
    {date_clause}
  GROUP BY {period_expr}, COALESCE(f.sTecnicaDetalle, 'SIN_DETALLE')
) t
GROUP BY t.period
ORDER BY t.period
```

## KPI 8 - espera_tramite_a_autorizacion_dias

Que mide:

- Dias promedio entre inicio de tramite y fin de tramite/autorizacion.

Para que sirve:

- Medir eficiencia administrativa previa al acto.

SQL:

```sql
SELECT
  {period_expr} AS period,
  ROUND(AVG(DATEDIFF(f.FechaFinTramite, f.FechaInputTramite)), 2) AS value
FROM flow_coordina f
WHERE f.Realizado = 255
  AND f.Autorizado = 255
  AND DATE_FORMAT(f.FechaInput, '%Y%m') > 200412
  AND f.FechaInputTramite > '1900-01-01'
  AND f.FechaFinTramite > '1900-01-01'
  AND DATEDIFF(f.FechaFinTramite, f.FechaInputTramite) > 0
  {date_clause}
GROUP BY {period_expr}
ORDER BY period
```

## KPI 9 - espera_autorizacion_a_realizado_dias

Que mide:

- Dias promedio desde autorizacion hasta realizacion del acto.

Para que sirve:

- Medir demora operativa post autorizacion.

SQL:

```sql
SELECT
  {period_expr} AS period,
  ROUND(AVG(DATEDIFF(f.FechaRealizado, f.FechaFinTramite)), 2) AS value
FROM flow_coordina f
WHERE f.Realizado = 255
  AND f.Autorizado = 255
  AND DATE_FORMAT(f.FechaInput, '%Y%m') > 200412
  AND f.FechaFinTramite > '1900-01-01'
  AND f.FechaRealizado > '1900-01-01'
  AND DATEDIFF(f.FechaRealizado, f.FechaFinTramite) > 0
  {date_clause}
GROUP BY {period_expr}
ORDER BY period
```

## KPI 10 - pct_complicaciones_cirugia

Que mide:

- Porcentaje de cirugias con complicaciones registradas.

Para que sirve:

- Vigilar tendencia de seguridad clinica.

SQL:

```sql
SELECT
  CONCAT(SUBSTRING(CAST(m.FecActoYM AS CHAR), 1, 4), '-', SUBSTRING(CAST(m.FecActoYM AS CHAR), 5, 2)) AS period,
  ROUND(
    (SUM(CASE WHEN q.Complica IN (1, 255) THEN 1 ELSE 0 END) * 100.0) / NULLIF(COUNT(*), 0),
    2
  ) AS value
FROM pvd_master m
INNER JOIN pvd_masterqq q ON q.CodPVD = m.Cod
WHERE m.FecActoYM > 200412
GROUP BY period
ORDER BY period
```

## KPI 11 - pct_stroke_postop

Que mide:

- Porcentaje mensual de stroke postoperatorio.

Para que sirve:

- Seguimiento puntual de una complicacion critica.

SQL:

```sql
SELECT
  CONCAT(SUBSTRING(CAST(m.FecActoYM AS CHAR), 1, 4), '-', SUBSTRING(CAST(m.FecActoYM AS CHAR), 5, 2)) AS period,
  ROUND(AVG(q.Stroke / 255.0) * 100, 2) AS value
FROM pvd_master m
INNER JOIN pvd_masterqq q ON q.CodPVD = m.Cod
WHERE m.FecActoYM > 200412
GROUP BY period
ORDER BY period
```

## KPI 12 - edad_promedio_quirurgica

Que mide:

- Edad promedio de pacientes quirurgicos por periodo.

Para que sirve:

- Caracterizar evolucion de perfil etario.

SQL:

```sql
SELECT
  {period_expr} AS period,
  ROUND(AVG(fc.EdadCoo), 2) AS value
FROM flow_coordina fc
WHERE fc.Realizado = 255
  AND fc.EdadCoo > 0
  AND fc.FechaRealizado > '1900-01-01'
  {date_clause}
GROUP BY {period_expr}
ORDER BY period
```

## 3) KPIs que conviene partir en varias metricas

Estas propuestas no son una sola KPI period/value, conviene dividirlas:

- Factores de riesgo preoperatorios: crear 1 KPI por factor (ejemplo: pct_diabetes, pct_hipertension, pct_obesidad).
- Complicaciones detalladas: crear 1 KPI por complicacion clave (stroke, sepsis, falla_renal_aguda).
- Perfil demografico por sexo: crear una KPI por sexo o llevarlo a analytics/ranking, no a KPI Designer base.

## 4) Paso a paso: crear y validar en UI Designer

URL:

- http://localhost:8000/api/v1/kpi-designer/ui

Flujo recomendado (nuevo, un solo paso):

1. Levantar backend y loguearse en Swagger para obtener token.
2. Abrir UI Designer y pegar token JWT.
3. Elegir tipo de KPI y opcionalmente usar Aplicar plantilla.
4. Completar nombre, descripcion, granularidad y SQL.
5. Click en Crear KPI (genera + valida + registra).
6. Revisar en la salida:
   - success = true
   - persisted_in_db = true (si estas en mysql)
   - validation.points_found > 0
   - query_result_preview.sample_points con datos

Con esto NO necesitas copiar/pegar manual a register ni a kpis/query para validar.

## 5) Si igual quieres probar por API en kpis/query

Usar este body (JSON valido, sin coma final):

```json
{
  "kpi_keys": ["volumen_mensual_total"],
  "granularity": "month",
  "filters": [
    { "key": "date_from", "values": ["2025-01-01"] },
    { "key": "date_to", "values": ["2026-12-31"] }
  ]
}
```

Errores comunes de 422:

- Usar kpi_key en lugar de kpi_keys.
- Dejar coma al final del JSON.
- values como string en vez de lista.
- Ejecutar en endpoint incorrecto (analytics/query en vez de kpis/query).

## 6) Recomendacion operativa para documentacion del proyecto

Para cada KPI agregar siempre:

- Nombre funcional.
- KPI key tecnica.
- Definicion de negocio (1 linea).
- SQL fuente.
- Unidad (casos, dias, %, etc.).
- Fecha minima de validez (ejemplo: > 200412).
- Supuestos y exclusiones (sentinelas 1900-01-01, 255, negativos).
