# Plan de trabajo - Consultas naturales (NL2KPI)

## Objetivo

Permitir que un usuario pregunte en lenguaje natural y el backend traduzca esa pregunta a una consulta estructurada sobre:

- /api/v1/kpis/query
- /api/v1/analytics/query

## Alcance MVP (entregable obligatorio)

1. Endpoint nuevo:

- POST /api/v1/natural-query/run

2. Funcionalidades:

- Deteccion de intencion (trend/ranking).
- Deteccion de metrica aproximada por palabras clave.
- Deteccion simple de granularidad (day/week/month).
- Deteccion basica de rango temporal (ano explicito o "este ano").
- Ejecucion real contra servicios existentes.
- Respuesta con payload traducido + supuestos + resultado.

3. Fuera de alcance MVP:

- LLM en produccion.
- Extraccion avanzada de entidades clinicas.
- Desambiguacion conversacional multi-turno.

## Flujo tecnico

1. Question (texto)
2. Planner NL (reglas)
3. Payload estructurado
4. Llamada a KPI o Analytics service
5. Respuesta explicable

## Mapa inicial de intenciones

- trend: tendencia temporal de una metrica.
- ranking: top/ranking por dimension (periodo en MVP).

## Mapa inicial de metricas (heuristico)

- espera/demora -> avg_wait_days
- mortal/fallec -> mortality_egreso_pct
- particip + ptca -> ptca_share_pct
- ptca -> ptca_volume
- cirug -> surgery_volume
- reinterv -> reintervenciones_mensual
- hemodinam -> hemodinamia_volumen_mensual
- centro -> centros_que_envian_pacientes

## Criterios de aceptacion

- Devuelve 200 para al menos 2 tipos de consulta (trend/ranking).
- Incluye payload traducido para trazabilidad.
- Incluye supuestos para transparencia.
- Tiene tests automaticos basicos.

## Siguientes mejoras

1. Tabla de sinonimos configurable en JSON.
2. Deteccion de periodos tipo "ultimo trimestre".
3. Respuesta narrativa en lenguaje natural.
4. Modo asistido con aclaraciones cuando hay ambiguedad.
