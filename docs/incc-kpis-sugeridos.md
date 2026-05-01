# INCC - Propuesta de KPIs y consultas SQL (base real)

Fecha de analisis: 2026-04-28
Base analizada: incc (MySQL local)

## 1) Hallazgos rapidos del modelo

Tablas clinicas con mejor potencial para dashboard:

- flow_coordina: 217999 episodios (nucleo operativo)
- dat_cirugia: 2745 cirugias, join 1:1 por CodCoordina -> flow_coordina.Cod
- call_ptcamaster: 24317 procedimientos PTCA, join por CodCoordina -> flow_coordina.Cod
- pvd_master: 14600 registros (formulario perioperatorio), join por CodFlow -> flow_coordina.Cod
- pac_ficha: 84968 pacientes, join por flow_coordina.CodPac -> pac_ficha.Cod
- salud_coordina + salud_paciente: 50325 y join consistente por CodCoordina / IdPaciente
- flow_procedimientocardiologia: 130671 actos con egreso/fallece

Ventana temporal util observada:

- flow_coordina.FechaRealizado: 1900-01-01 a 2026-03-10
- Muchos valores centinela en 1900-01-01, -99 y 255

## 2) Reglas de limpieza (obligatorias)

Aplicar estas reglas en cualquier consulta KPI:

1. Fechas validas: fecha > '1900-01-01'
2. Campos numericos con sentinela: excluir -99
3. Flags tinyint con 255: tratar como sin dato/NA
4. Para tiempos de espera: excluir negativos (errores de carga)

Ejemplos de filtros:

- FechaRealizado > '1900-01-01'
- POestadiaUCI >= 0
- IPfallece IN (0,1)
- DATEDIFF(FechaRealizado, FechaCoordina) >= 0

## 3) KPIs prioritarios (MVP dashboard)

Estos KPI tienen alta factibilidad con joins estables.

## KPI 1 - Volumen mensual de actividad total

```sql
SELECT
  DATE_FORMAT(f.FechaRealizado, '%Y-%m') AS periodo,
  COUNT(*) AS total_actos
FROM flow_coordina f
WHERE f.FechaRealizado > '1900-01-01'
GROUP BY 1
ORDER BY 1;
```

## KPI 2 - Volumen mensual de cirugias

```sql
SELECT
  DATE_FORMAT(f.FechaRealizado, '%Y-%m') AS periodo,
  COUNT(*) AS total_cirugias
FROM dat_cirugia d
JOIN flow_coordina f ON f.Cod = d.CodCoordina
WHERE f.FechaRealizado > '1900-01-01'
GROUP BY 1
ORDER BY 1;
```

## KPI 3 - Volumen mensual de PTCA

```sql
SELECT
  DATE_FORMAT(f.FechaRealizado, '%Y-%m') AS periodo,
  COUNT(*) AS total_ptca
FROM call_ptcamaster c
JOIN flow_coordina f ON f.Cod = c.CodCoordina
WHERE f.FechaRealizado > '1900-01-01'
GROUP BY 1
ORDER BY 1;
```

## KPI 4 - Tiempo de espera coordinado -> realizado

```sql
SELECT
  DATE_FORMAT(f.FechaRealizado, '%Y-%m') AS periodo,
  AVG(DATEDIFF(f.FechaRealizado, f.FechaCoordina)) AS espera_promedio_dias,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY DATEDIFF(f.FechaRealizado, f.FechaCoordina)) OVER (PARTITION BY DATE_FORMAT(f.FechaRealizado, '%Y-%m')) AS espera_mediana_dias
FROM flow_coordina f
WHERE f.FechaRealizado > '1900-01-01'
  AND f.FechaCoordina > '1900-01-01'
  AND DATEDIFF(f.FechaRealizado, f.FechaCoordina) >= 0
GROUP BY 1
ORDER BY 1;
```

Nota: si la version MySQL no soporta PERCENTILE_CONT, dejar solo promedio o calcular mediana con subconsulta.

## KPI 5 - % egreso con fallecimiento registrado (procedimiento cardiologia)

```sql
SELECT
  YEAR(p.FechaEgreso) AS anio,
  MONTH(p.FechaEgreso) AS mes,
  COUNT(*) AS egresos,
  SUM(CASE WHEN p.FechaFallece > '1900-01-01' THEN 1 ELSE 0 END) AS fallecidos,
  ROUND(100.0 * SUM(CASE WHEN p.FechaFallece > '1900-01-01' THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_fallecidos
FROM flow_procedimientocardiologia p
WHERE p.FechaEgreso > '1900-01-01'
GROUP BY 1,2
ORDER BY 1,2;
```

## KPI 6 - Estadia UCI postoperatoria (cirugia)

```sql
SELECT
  DATE_FORMAT(f.FechaRealizado, '%Y-%m') AS periodo,
  COUNT(*) AS n,
  ROUND(AVG(d.POestadiaUCI), 2) AS uci_promedio_dias,
  MAX(d.POestadiaUCI) AS uci_max_dias
FROM dat_cirugia d
JOIN flow_coordina f ON f.Cod = d.CodCoordina
WHERE f.FechaRealizado > '1900-01-01'
  AND d.POestadiaUCI >= 0
GROUP BY 1
ORDER BY 1;
```

## KPI 7 - Complicaciones seleccionadas postoperatorias

```sql
SELECT
  DATE_FORMAT(f.FechaRealizado, '%Y-%m') AS periodo,
  COUNT(*) AS total,
  SUM(CASE WHEN d.CIOstroke = 1 THEN 1 ELSE 0 END) AS stroke,
  SUM(CASE WHEN d.CIOsepsis = 1 THEN 1 ELSE 0 END) AS sepsis,
  SUM(CASE WHEN d.CIOfallaRenalAguda = 1 THEN 1 ELSE 0 END) AS falla_renal_aguda
FROM dat_cirugia d
JOIN flow_coordina f ON f.Cod = d.CodCoordina
WHERE f.FechaRealizado > '1900-01-01'
GROUP BY 1
ORDER BY 1;
```

## KPI 8 - Perfil demografico quirurgico

```sql
SELECT
  DATE_FORMAT(f.FechaRealizado, '%Y-%m') AS periodo,
  ROUND(AVG(TIMESTAMPDIFF(YEAR, p.FecNace, f.FechaRealizado)), 1) AS edad_promedio,
  SUM(CASE WHEN TIMESTAMPDIFF(YEAR, p.FecNace, f.FechaRealizado) >= 75 THEN 1 ELSE 0 END) AS mayores_75,
  SUM(CASE WHEN p.CodSexo = 1 THEN 1 ELSE 0 END) AS sexo_1,
  SUM(CASE WHEN p.CodSexo = 2 THEN 1 ELSE 0 END) AS sexo_2
FROM dat_cirugia d
JOIN flow_coordina f ON f.Cod = d.CodCoordina
JOIN pac_ficha p ON p.Cod = f.CodPac
WHERE f.FechaRealizado > '1900-01-01'
  AND p.FecNace > '1900-01-01'
GROUP BY 1
ORDER BY 1;
```

## 4) KPI de calidad de dato (mostrar en panel tecnico)

Muy recomendable para no sacar conclusiones incorrectas.

## DQ 1 - % fechas centinela en actividad

```sql
SELECT
  ROUND(100.0 * SUM(CASE WHEN FechaRealizado <= '1900-01-01' OR FechaRealizado IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_fechas_invalidas
FROM flow_coordina;
```

## DQ 2 - % sentinela -99 en estadia UCI

```sql
SELECT
  ROUND(100.0 * SUM(CASE WHEN POestadiaUCI = -99 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_uci_sentinel
FROM dat_cirugia;
```

## DQ 3 - % sentinela 255 en flags PTCA

```sql
SELECT
  ROUND(100.0 * SUM(CASE WHEN IPfallece = 255 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ipfallece_sentinel,
  ROUND(100.0 * SUM(CASE WHEN PPfallece = 255 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ppfallece_sentinel,
  ROUND(100.0 * SUM(CASE WHEN IPnoEfectivo = 255 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_ipnoefectivo_sentinel
FROM call_ptcamaster;
```

## 5) Tareas concretas para tu companero de datos

Sprint 1 (2-3 dias):

1. Crear vista vw_kpi_actividad_mensual desde flow_coordina.
2. Crear vista vw_kpi_cirugia_mensual desde dat_cirugia + flow_coordina.
3. Crear vista vw_kpi_ptca_mensual desde call_ptcamaster + flow_coordina.
4. Crear vista vw_kpi_tiempo_espera con limpieza de negativos.
5. Crear vista vw_kpi_mortalidad_egreso desde flow_procedimientocardiologia.

Sprint 2 (2-3 dias):

1. Crear vistas de complicaciones (stroke/sepsis/renal).
2. Crear vistas demograficas (edad/sexo).
3. Crear vistas de calidad de dato.
4. Documentar diccionario de codigos (0/1/2/255/-99) por campo.

## 6) Contrato JSON sugerido para backend/frontend

```json
{
  "kpi_key": "surgery_volume",
  "period": "2026-02",
  "value": 22,
  "unit": "casos",
  "quality": {
    "source": "dat_cirugia+flow_coordina",
    "valid_records": 22,
    "dropped_records": 0
  }
}
```

## 7) Nota importante

En esta base hay mezcla de tablas historicas, administrativas y clinicas. Para el dashboard MVP conviene centrarse primero en:

- flow_coordina
- dat_cirugia
- call_ptcamaster
- flow_procedimientocardiologia
- pac_ficha

Con eso ya se puede entregar un dashboard solido y luego iterar.
