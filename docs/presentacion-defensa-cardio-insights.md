# Cardio Insights — Presentación de defensa

Plataforma de inteligencia de datos para análisis de procedimientos cardiovasculares  
Instituto Nacional de Cirugía Cardíaca  
Universidad ORT Uruguay — Facultad de Ingeniería — Licenciatura en Sistemas  

Andrés Campopiano · Diego Caraballo · Gervasio García  
Tutora: Ing. Mariel Feder Szafir  
2026

Uso: simulacro / defensa final. Producto presentado como cerrado. Audiencia que no conoce el proyecto.  
Versión extendida (~28 slides).

---

## Slide 1 — Portada

**Cardio Insights**  
Plataforma de inteligencia de datos para análisis de procedimientos cardiovasculares

Instituto Nacional de Cirugía Cardíaca  
Universidad ORT Uruguay – Facultad de Ingeniería  
Licenciatura en Sistemas

Andrés Campopiano · Diego Caraballo · Gervasio García  
Tutora: Ing. Mariel Feder Szafir  
2026

---

## Slide 2 — El equipo

Andrés Campopiano · Diego Caraballo · Gervasio García  
Tutora: Ing. Mariel Feder Szafir  
Cliente: Instituto Nacional de Cirugía Cardíaca

Frentes de trabajo (completar quién lideró cada uno):

- Aplicación web (React / TypeScript)
- Backend, APIs, seguridad y datos
- KPIs, Metabase y validación de indicadores
- Módulo predictivo
- Chat analítico / LLM Gateway

Trabajo colaborativo, con revisión cruzada (PRs) y validación con tutora y referentes del INCC.

---

## Slide 3 — Agenda

1. Cliente, problema y decisiones que apoya
2. Relevamiento y requerimientos
3. Producto y arquitectura
4. KPIs, predictivo y chat
5. Seguridad, calidad y riesgos
6. Resultados y demostración

---

## Slide 4 — El cliente

Instituto Nacional de Cirugía Cardíaca (INCC)

- IMAE, diagnóstico y tratamiento cardiovascular
- Prestador del FNR y ámbito privado
- Activo principal: base histórica MySQL desde 2005
- Más de 80.000 procedimientos
- Actividad, tiempos de espera, procedencia, sectores, complicaciones, factores de riesgo, mortalidad

---

## Slide 5 — El problema

La institución tiene los datos; no tiene un acceso ágil para quienes los necesitan.

- Médicos y gestión dependen de SQL, exportaciones y perfiles técnicos
- Eso retrasa preguntas frecuentes y deja el análisis en pocas personas
- Cardio Insights es un **sistema de apoyo a la toma de decisiones**
- Organiza, consulta y visualiza
- **No reemplaza el criterio médico**

---

## Slide 6 — Qué decisiones apoya

- Volumen y evolución de la actividad quirúrgica y de hemodinamia
- Tiempos de espera y procedencia de pacientes
- Ranking de centros que derivan
- Distribución por tipo de procedimiento, sector y período
- Seguimiento de factores de riesgo, complicaciones y mortalidad
- Exploración de riesgo con modelos interpretables, como **insumo de análisis**, no como indicación clínica

Usuarios: médicos, gestión/administración, informática/soporte.

---

## Slide 7 — Cómo se llegó a la solución

- Relevamiento con referentes del INCC
- Análisis de la base
- Consultas de negocio frecuentes
- Validación incremental de indicadores

Pedidos de la institución:

- Consultar sin SQL
- Ver tableros en una app web interna
- Sin costo de licencia relevante
- Uso interno y datos sensibles

El equipo propuso, y el producto incluye: consulta en lenguaje natural controlada y módulo predictivo de apoyo.

Metabase, FastAPI y el LLM Gateway son **decisiones de diseño**, no requerimientos del cliente.

---

## Slide 8 — Requerimientos funcionales

| Código | Requerimiento | Origen |
|---|---|---|
| RF01 | Consultar indicadores sin conocer la base | INCC |
| RF02 | Visualizar dashboards (tendencias, rankings, acumulados) | INCC |
| RF03 | Filtrar por período y dimensiones | INCC |
| RF04 | Ver los reportes **dentro** de la aplicación web | INCC |
| RF05 | Acceso autenticado, uso interno | INCC |
| RF06 | Consulta en lenguaje natural **controlada** | Propuesta del equipo |
| RF07 | Estimaciones predictivas de apoyo e investigación | Propuesta del equipo |
| RF08 | Ver metodología y limitaciones de los modelos | Propuesta del equipo |

Metabase, el Gateway y los artefactos de entrenamiento **no** son RF del cliente: son medios de implementación.

---

## Slide 9 — Requerimientos no funcionales

| Atributo | Criterio verificable |
|---|---|
| Usabilidad | Usuarios no técnicos consultan sin SQL ni estructura de la base |
| Seguridad | JWT, roles, MySQL de solo lectura, LLM sin SQL libre |
| Confidencialidad | Ofuscación/anonimización en desarrollo; acceso restringido en producción |
| Integridad | KPIs contrastados con SQL de referencia, dentro de tolerancias |
| Transparencia | Predictivo con metodología, métricas y disclaimer |
| Mantenibilidad | Separación frontend / backend / BI / predictivo / Gateway |
| Operabilidad | Despliegue reproducible (contenedores, variables de entorno, health checks) |
| Performance | Consultas frecuentes sobre volumen histórico, con pruebas de latencia |

Restricción de producto: sin costo de licencia relevante para esta etapa.

---

## Slide 10 — El producto

Plataforma web interna, con autenticación y roles.

1. **KPIs y dashboards** — indicadores clínicos y operativos embebidos, con filtros
2. **Análisis predictivo** — estimación de riesgo con metodología y limitaciones visibles
3. **Chat analítico** — pregunta en lenguaje natural; el sistema interpreta y ejecuta solo lo autorizado

Una sola entrada para el usuario. No sale a herramientas externas ni escribe SQL.

---

## Slide 11 — Arquitectura

*Insertar Figura 1 del informe.*

- Frontend React + TypeScript
- Backend FastAPI: autenticación JWT, validación y **autoridad de ejecución**
- MySQL INCC, solo lectura
- Metabase embebido
- Módulo predictivo + artefactos de modelo
- LLM Gateway → OpenAI

El usuario solo habla con la aplicación. Ni el frontend ni el LLM tocan la base.

---

## Slide 12 — Vista de despliegue

*Insertar Figura 5 del informe.*

- **Navegador:** frontend React
- **Servidor / Docker:** backend FastAPI, Metabase, MySQL de datos INCC, MySQL de aplicación Metabase
- **Externos:** LLM Gateway y OpenAI

El usuario llega por HTTPS a la app. El backend emite el token de embed. Metabase no es la puerta de entrada.

---

## Slide 13 — KPIs y Metabase

*Opcional: insertar Figura 2.*

Criterios: embed (35%), gratuidad (30%), dashboards privados (20%), facilidad de uso (15%).

| Herramienta | Puntaje | Resultado |
|---|---|---|
| Metabase | 3,00 | Seleccionada |
| Looker Studio | 2,80 | Descartada: privacidad y control de acceso |
| Apache Superset | 2,70 | Descartada: complejidad operativa |
| Power BI | 2,40 | Descartada: licencia para embedding seguro |
| Tableau | 2,40 | Descartada: licencia; versión pública no apta |

Cardio Insights controla acceso y navegación. Metabase visualiza.  
Categorías: actos, cirugía, hemodinamia, factores de riesgo, mortalidad.  
Los indicadores se contrastan con **SQL de referencia**.

---

## Slide 14 — Cómo se incorporan KPIs nuevos

1. **Necesidad de negocio** — referente del INCC o gestión define qué quiere ver
2. **Consulta de referencia** — SQL acordado, sobre un conjunto de datos conocido
3. **Construcción** — pregunta/dashboard en Metabase + filtros
4. **Validación** — contraste numérico + revisión de dominio
5. **Publicación** — embed en Cardio Insights y, si aplica, alta en el catálogo del chat

No se publica un indicador solo porque “el gráfico se ve bien”.

---

## Slide 15 — Análisis predictivo

*Insertar Figura 3.*

- Módulo de apoyo e investigación, no sistema de decisión clínica
- Usa variables disponibles **antes** del procedimiento
- Prioridad: modelos interpretables
- El usuario ve estimación, métricas, advertencias y metodología

---

## Slide 16 — Por qué el chat no genera SQL libre

Text-to-SQL directo: alucinación, consultas inseguras, poca trazabilidad.

Decisión de producto: el chat **forma parte de la solución**, con control estricto.

- El LLM **traduce** la pregunta a un contrato (tipo, KPI, endpoint, payload)
- El backend valida catálogo, permisos y reglas
- Si está fuera de alcance: se rechaza y **no se consulta MySQL**

---

## Slide 17 — Flujo del chat

*Insertar Figura 4.*

Pregunta → frontend → backend → LLM Gateway → contrato → validación  
→ ejecución autorizada **o** rechazo

El SQL de diagnóstico, cuando aplica, queda para **perfiles técnicos** (informática/soporte), no para el usuario médico.

---

## Slide 18 — Seguridad y datos

- Uso interno, autenticación JWT, roles
- Consultas analíticas con usuario MySQL de **solo lectura**
- LLM sin acceso directo a la base

**Desarrollo y prueba:** datos ofuscados o anonimizados.

**Producción:** eso no alcanza; aplica control de acceso, secretos, auditoría y mínimo privilegio.

Marco: datos personales y de salud; minimización de exposición.

---

## Slide 19 — Calidad y validación

Qué se prueba:

- **Unitarias** — servicios y reglas de validación
- **API y permisos** — JWT, roles, rechazos
- **Integración** — backend, Metabase, base, Gateway
- **KPIs** — SQL de referencia + revisión de dominio
- **Chat** — contrato válido y **rechazo fuera de alcance**
- **Predictivo** — salida con metodología, métricas y disclaimer
- **Despliegue** — contenedores, health checks, configuración por ambiente

Un KPI no está listo si solo renderiza. Un chat no está listo si siempre intenta contestar.

---

## Slide 20 — Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Datos clínicos sensibles | Ofuscación en desarrollo; JWT, roles y solo lectura en producción |
| Volumen histórico (~80.000) | Consultas controladas, pruebas de latencia, índices si hace falta |
| Alucinación o mala interpretación del chat | Catálogo, contrato, rechazo sin tocar MySQL |
| KPI incorrecto o mal leído | SQL de referencia + validación con referentes |
| Costo y dependencia de API de LLM | Gateway desacoplado; OpenAI solo interpreta; se evaluó alternativa local |
| Ampliar de más el producto | Tres módulos acotados; crecimiento por catálogo, no por SQL libre |

---

## Slide 21 — Tecnologías y factibilidad del LLM

Stack: React, TypeScript, FastAPI, MySQL, Metabase, modelos interpretables, LLM Gateway + OpenAI.

OpenAI vs Ollama (local):

| Criterio | OpenAI | Ollama / local |
|---|---|---|
| Calidad de interpretación | Alta, con poco setup | Variable; depende de hardware y modelo |
| Costo | Pago por uso | Infra y mantenimiento propios |
| Latencia | Depende de red/API | Depende del servidor local |
| Seguridad del dato | El modelo no ejecuta ni ve la base; interpreta el texto | Mayor control físico; más operación |
| Encaje en el producto | Elegida para interpretar | Viable a futuro vía Gateway |

Decisión: OpenAI interpreta; el backend ejecuta. El Gateway permite cambiar de proveedor sin rediseñar el producto.

---

## Slide 22 — Cómo se trabajó

- Enfoque ágil incremental (Scrum), sprints, Jira, GitHub con PRs, registro de horas
- Validación continua con tutora y referentes del INCC
- IA usada como apoyo de redacción y desarrollo; las decisiones y la validación son del equipo

---

## Slide 23 — Resultados

Plataforma interna operativa que:

- acerca los datos históricos a usuarios no técnicos
- centraliza KPIs, predicción y consulta natural
- mantiene control sobre seguridad, trazabilidad y alcance clínico

El INCC pasa de una explotación puntual y técnica de la base a una consulta sistemática, auditable y acotada.

---

## Slide 24 — Limitaciones y evolución

- No emite recomendaciones clínicas
- El predictivo es apoyo e investigación
- El chat responde solo consultas del catálogo autorizado

Evolución prevista:

- nuevos KPIs por el procedimiento ya definido
- más modelos, si el dominio lo sostiene
- ampliación controlada del catálogo de preguntas
- evaluación de mayor despliegue institucional

---

## Slide 25 — El producto en uso (I)

*Insertar capturas reales.*

- Login / acceso interno
- Home o navegación por módulos
- Un dashboard de KPIs con filtros aplicados (año, procedimiento o sector)

Pie: el usuario está en Cardio Insights, no en Metabase.

---

## Slide 26 — El producto en uso (II)

*Insertar capturas reales.*

- Módulo predictivo: formulario + resultado con advertencias / metodología
- Chat: pregunta válida con respuesta
- Chat: pregunta fuera de alcance y rechazo

Pie: el rechazo es comportamiento correcto del producto.

---

## Slide 27 — Demostración

Recorrido propuesto:

1. Login
2. Dashboards y filtros
3. Predictivo con metodología
4. Chat: consulta válida y consulta fuera de alcance

---

## Slide 28 — Cierre

Cardio Insights convierte la base histórica del INCC en información consultable, visual y controlada.

Es una herramienta de apoyo a decisiones institucionales, no un sistema de decisión clínica.

Arquitectura, seguridad y validación están pensadas para un dominio de datos sensibles.

---

## Figuras y capturas a insertar

| Slide | Material |
|---|---|
| 11 | Figura 1 – Vista general de arquitectura |
| 12 | Figura 5 – Vista de despliegue |
| 13 | Figura 2 – Flujo de KPIs (opcional) |
| 15 | Figura 3 – Flujo de análisis predictivo |
| 17 | Figura 4 – Flujo de consulta natural |
| 25–26 | Capturas de la aplicación |

---

## Notas de armado en PowerPoint

- Completar roles en la slide 2 antes de exponer
- Una idea por slide; las tablas se leen, no se recitan enteras
- Fondo limpio, sin estilo “Gemini / notebook”
- Epígrafes en las figuras, igual que en el documento
- Capturas 25–26 **antes** de la demo en vivo
- Demo al final
