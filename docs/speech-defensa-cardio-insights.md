# Cardio Insights — Speech de defensa

Versión extensa (aprox. 45–60 minutos de habla, más la demostración).  
Sigue el orden de `presentacion-defensa-cardio-insights.md` (28 slides).  
Producto presentado como cerrado. Audiencia que no conoce el proyecto.

Reparto sugerido:

- Persona 1: slides 1–10
- Persona 2: slides 11–15 y demo de tableros + predictivo
- Persona 3: slides 16–24 y 28, demo del chat; las 25–26 las narra quien muestre las capturas

Completar roles en la slide 2 antes de ensayar.

---

## Slide 1 — Portada

Buenas tardes. Somos Andrés Campopiano, Diego Caraballo y Gervasio García, estudiantes de la Licenciatura en Sistemas de la Universidad ORT Uruguay. El proyecto que vamos a presentar se llama Cardio Insights y fue desarrollado para el Instituto Nacional de Cirugía Cardíaca, con la tutoría de la ingeniera Mariel Feder Szafir.

Cardio Insights es una plataforma interna de inteligencia de datos. Su propósito es que la institución pueda consultar, visualizar y analizar la información histórica de procedimientos cardiovasculares de forma ágil, segura y comprensible para distintos perfiles de usuario. No es un sistema que tome decisiones clínicas. Es una herramienta de apoyo: organiza la información, la vuelve consultable y deja la interpretación en manos de los profesionales.

---

## Slide 2 — El equipo

Somos un equipo de tres. El trabajo fue colaborativo, con revisión cruzada de código, pero cada uno tuvo un frente principal: [completar: por ejemplo, aplicación web; backend, datos y seguridad; KPIs y Metabase; predictivo; chat].

La tutora nos acompañó en alcance, metodología y criterio académico. Del lado del cliente, los referentes del INCC fueron quienes explicaron el dominio y nos permitieron validar si un indicador o una pantalla tenía sentido institucional.

Eso importa porque lo que van a ver no es una herramienta genérica de BI: está recortada a este instituto, a esta base y a estos usuarios.

---

## Slide 3 — Agenda

La exposición es larga a propósito. Primero el cliente, el problema y qué decisiones concretas apoya la solución. Después cómo se relevó y cuáles son los requerimientos —los del instituto y los que propuso el equipo—. Luego el producto y la arquitectura, incluyendo cómo está desplegado. Entramos a los tres módulos: KPIs, predictivo y chat. Cerramos con seguridad, calidad, riesgos, resultados, capturas y una demostración en el sistema.

---

## Slide 4 — El cliente

El Instituto Nacional de Cirugía Cardíaca es una institución de asistencia médica especializada en el diagnóstico y tratamiento de las enfermedades cardiovasculares. Forma parte de un centro con una trayectoria larga en el país y está reconocido como Instituto Médico Altamente Especializado. Brinda servicios tanto en el marco del Fondo Nacional de Recursos como en el ámbito privado.

Eso importa por dos razones. La primera: el volumen y la diversidad de la actividad. Hay cirugía a corazón abierto, hemodinamia, implantes, distintos tipos de procedimiento y pacientes que llegan de muchos orígenes. La segunda: el instituto no parte de cero. Tiene una base de datos histórica, en MySQL, con registros desde 2005 y un volumen superior a los 80.000 procedimientos.

Esa base no es un archivo muerto. Permite estudiar actividad asistencial, tiempos de espera, procedencia, sectores de atención, complicaciones, factores de riesgo, productividad y evolución en el tiempo. Es, en los hechos, un activo estratégico. El proyecto nace de ahí: de una institución que ya tiene la información, pero no tenía una forma adecuada de ponerla en manos de quienes tienen que usarla.

---

## Slide 5 — El problema

El problema no es “faltan datos”. El problema es la distancia entre esos datos y las personas que necesitan responder preguntas.

Un médico o alguien de gestión puede querer saber cómo evolucionó la actividad quirúrgica mes a mes, qué centros derivan más pacientes, cómo se distribuyen los procedimientos, o cómo se ven los tiempos de espera. Esas preguntas son razonables. Lo que no es razonable es que, para contestarlas, haya que conocer nombres de tablas, armar un SQL, exportar a una planilla y, muchas veces, depender de informática o de un perfil estadístico.

Cuando el acceso queda restringido a quienes dominan la base, la información se subutiliza. Las decisiones siguen existiendo, pero se toman con menos evidencia, más lento, o con recortes parciales de la historia. Cardio Insights se plantea exactamente en esa brecha.

Y acá hay una definición que queremos dejar clara desde el principio. Esto es un sistema de apoyo a la toma de decisiones. No diagnostica, no indica un tratamiento, no sustituye al especialista. Su función es que la información esté disponible, sea trazable y se pueda consultar sin perder control sobre datos clínicos.

---

## Slide 6 — Qué decisiones apoya

Si el producto solo “muestra gráficos”, no justifica un proyecto de este tipo. Lo que tiene que quedar explícito es qué tipo de decisiones institucionales mejora.

En actividad y gestión: permite ver volumen, evolución temporal, rankings y acumulados. Eso apoya preguntas de planificación, de carga de trabajo, de comparación entre períodos y de seguimiento de la operación.

En la relación con el resto del sistema de salud: permite mirar procedencia y centros que derivan. Eso no es un dato decorativo: habla de demanda, de red y de cómo llega el paciente al instituto.

En lo clínico-operativo: permite explorar distribución por tipo de procedimiento, sector —cirugía o hemodinamia—, factores de riesgo, complicaciones y mortalidad. Otra vez: no para que el sistema concluya qué hacer con un paciente, sino para que el análisis institucional no dependa de una extracción manual cada vez.

Y hay un cuarto nivel, más exploratorio: el módulo predictivo. Ahí el usuario puede estimar un riesgo a partir de variables disponibles antes del procedimiento, con el modelo y sus límites a la vista. Es un insumo de investigación y análisis. Si alguien lo leyera como una indicación médica, estaríamos usando mal la herramienta, y el producto está diseñado para que ese malentendido no sea el camino por defecto.

Los usuarios que sostienen esas decisiones son tres. Los médicos, que necesitan indicadores e interpretación clara. Gestión y administración, que necesitan tableros, tendencias y rankings. E informática, que necesita que todo eso ocurra con seguridad, auditoría y operación controlada.

---

## Slide 7 — Cómo se llegó a la solución

La solución no salió de una lista de tecnologías. Salió de un relevamiento.

Trabajamos con referentes del INCC para entender el dominio, qué se pregunta en la práctica y qué tendría valor real. Revisamos la estructura de la base. Identificamos consultas frecuentes: actividad, espera, procedencia, tipos de procedimiento, tendencias. Y fuimos validando de forma incremental: a medida que aparecían tableros y funcionalidades, se contrastaban con esas necesidades.

Lo que la organización planteó, en esencia, fueron tres cosas. Primera: poder consultar indicadores sin SQL y sin depender de un perfil técnico para cada pregunta. Segunda: ver esa información en tableros, dentro de una plataforma web propia, no saltando a una herramienta aparte. Tercera: que fuera viable sin un costo de licencia relevante, y con el cuidado que exige un dato clínico de uso interno.

A partir de ahí el equipo tomó decisiones de diseño. Elegimos embeber una herramienta de BI en lugar de programar cada gráfico a mano. Construimos un backend propio que autentica, valida y ejecuta. Incorporamos consulta en lenguaje natural, pero no como “un ChatGPT contra la base”, sino como una capa controlada. Y sumamos un módulo predictivo de apoyo, con metodología visible.

Eso es importante en términos académicos y de producto: Metabase, FastAPI o el LLM Gateway no son pedidos del instituto. Son medios. Los requerimientos del cliente son consultar, visualizar, filtrar, proteger el acceso y no exponer la complejidad interna de la base.

---

## Slide 8 — Requerimientos funcionales

Esta tabla es el contrato del producto.

Del INCC salen RF01 a RF05: consultar indicadores sin conocer la base, ver dashboards, filtrar, verlos dentro de la propia aplicación, y que el acceso sea interno y autenticado.

RF06, RF07 y RF08 los propuso el equipo y quedaron en el producto: lenguaje natural controlado, estimaciones predictivas de apoyo, y que el modelo se explique. No eran un pedido de “pongan un GPT” ni “armen un motor de machine learning”. Eran una forma de bajar más la barrera de consulta y de explorar la historia clínica, sin convertir esto en un sistema de decisión médica.

Si en la mesa preguntan “¿el cliente pidió Metabase?”, la respuesta es no. Pidió ver indicadores en una web interna, sin licencia. Metabase es cómo lo resolvimos. Lo mismo el Gateway: el requerimiento es consultar en lenguaje natural sin abrir la base; el Gateway es el mecanismo.

---

## Slide 9 — Requerimientos no funcionales

Los no funcionales no son adjetivos. Cada uno se puede contrastar.

Usabilidad: un médico o alguien de gestión consulta sin SQL. Seguridad: JWT, roles, MySQL de solo lectura, y el LLM sin ejecución libre. Confidencialidad: en desarrollo ofuscamos; en producción eso no alcanza, vale el acceso restringido. Integridad: el KPI se compara con un SQL de referencia. Transparencia: el predictivo sale con metodología. Mantenibilidad: los módulos se pueden evolucionar por separado. Operabilidad: se levanta de forma reproducible. Performance: el volumen histórico no es un Excel de mil filas; hay que poder consultar sin que la herramienta se vuelva inusable.

Y una restricción de producto que pesó en las herramientas: sin costo de licencia relevante para esta etapa.

---

## Slide 10 — El producto

El producto es una aplicación web interna. El usuario se autentica, entra con un rol, y desde ahí accede a tres formas de trabajo con los mismos datos.

La primera es la más estructurada: dashboards de KPIs. Categorías, filtros por período y dimensiones, gráficos y tablas. Es el camino natural para el seguimiento y para las preguntas que ya se sabe que se van a repetir.

La segunda es el análisis predictivo. El usuario autorizado elige un modelo, carga variables clínicas disponibles antes del procedimiento y obtiene una estimación. Junto con eso ve cómo interpretar el resultado y cuáles son las limitaciones. Si el módulo no explica, no sirve.

La tercera es el chat. Para cuando la persona tiene la pregunta en la cabeza y no quiere buscar el tablero exacto. Escribe en lenguaje natural. El sistema interpreta, valida, y o bien responde con información autorizada, o bien dice que esa consulta no está habilitada.

La experiencia que buscamos es esa: una sola puerta de entrada. El usuario no tiene que saber que atrás hay Metabase, un Gateway o una base MySQL. Eso es problema nuestro, no suyo.

---

## Slide 11 — Arquitectura

Esta figura es la vista general de la arquitectura.

Arriba, en lo que desarrollamos nosotros, están el frontend, el backend, el módulo predictivo y el LLM Gateway. Abajo, los componentes que integramos: Metabase, la MySQL institucional de solo lectura, y el proveedor del modelo de lenguaje, OpenAI.

El flujo mental es este. El usuario solo habla con el frontend. El frontend habla con el backend por APIs, con JWT. Si va a ver un dashboard, el backend emite un token de embedding y el frontend muestra Metabase embebido; Metabase consulta la base. Si va a predecir, el backend valida el pedido y ejecuta el modelo. Si va al chat, el backend le pide interpretación al Gateway y recién después decide si hay algo que ejecutar.

Hay un principio que ordena todo: el backend es la autoridad de ejecución. El frontend no consulta la base. El LLM no consulta la base. Metabase visualiza, pero el acceso del usuario a esos tableros entra por Cardio Insights, con sesión y permisos. Esa separación no es estética. Es la forma de no perder control en un dominio clínico.

---

## Slide 12 — Vista de despliegue

La figura anterior era lógica. Esta es de instalación.

En el navegador corre el frontend. En el servidor, con contenedores, están el backend, Metabase y dos bases: la de datos del INCC, que es la fuente de análisis, y la base propia de Metabase, que guarda sus tableros y configuración. Afuera, el Gateway y OpenAI.

El punto a subrayar: el usuario no entra a Metabase ni a la base. Entra a Cardio Insights por HTTPS. El backend le da el token para ver el dashboard embebido. Si preguntan “¿dónde está instalado?”, esta es la respuesta. Si preguntan “¿OpenAI ve la base?”, no: interpreta texto; la ejecución queda acá.

---

## Slide 13 — KPIs y Metabase

El módulo de indicadores es el corazón del valor inmediato para el instituto.

Podríamos haber dibujado cada gráfico en React. No lo hicimos, y fue una decisión consciente. El esfuerzo de desarrollo propio lo quisimos poner en integración, seguridad, navegación y en los otros módulos. La visualización analítica es un problema ya resuelto por herramientas de BI. La pregunta era cuál se bancaba este contexto.

Comparamos Apache Superset, Metabase, Power BI, Looker Studio y Tableau. Los criterios con más peso fueron cuatro, y están ponderados: embed, 35 por ciento, porque el reporte tiene que vivir dentro de nuestra app; gratuidad, 30, porque el instituto no quería atar el producto a una licencia; dashboards privados, 20, por el dato clínico; facilidad de uso, 15.

La matriz da a Metabase el 3,00. Looker Studio queda cerca, pero flojo en privacidad. Superset es sólido y más complejo de operar. Power BI y Tableau se caen por licencia, y Tableau Public no es opción con datos de pacientes.

Cardio Insights controla quién entra y cómo se navega. Metabase visualiza. Los KPIs están en categorías de dominio: actos, cirugía, hemodinamia, factores de riesgo, mortalidad. Y un KPI no está listo porque el gráfico renderiza: se contrasta con SQL de referencia.

---

## Slide 14 — Cómo se incorporan KPIs nuevos

Esto no es un detalle de mantenimiento: es cómo el producto puede crecer sin volverse un depósito de gráficos sueltos.

Primero hay una necesidad de negocio, dicha por un referente. Segundo, una consulta de referencia: el número tiene que poder armarse en SQL, sobre un conjunto de datos conocido. Tercero, se construye en Metabase, con filtros. Cuarto, se valida: el número cierra y el dominio dice que el indicador significa lo que creemos. Quinto, se publica embebido en Cardio Insights y, si el chat lo va a responder, entra al catálogo.

Si alguien pide “agreguemos diez tableros para la semana que viene”, el cuello de botella correcto es la validación, no el dibujo del gráfico.

---

## Slide 15 — Análisis predictivo

El módulo predictivo es donde más fácil sería sobrevendar el producto, y por eso lo presentamos con límites explícitos.

No es un sistema de decisión clínica. No recomienda operar o no operar. No sustituye scores clínicos validados por la especialidad. Es una herramienta de apoyo e investigación sobre datos históricos del propio instituto.

El diseño tiene una regla de integridad: las variables que usa el modelo tienen que estar disponibles antes del procedimiento. Si entrenáramos con información posterior al evento, el modelo “adivinaría” con datos que en la vida real todavía no existen. Eso puede dar métricas lindas y modelos inútiles, o peores, engañosos.

También priorizamos interpretabilidad. En este dominio, un número sin explicación es un riesgo. El usuario tiene que poder ver qué predice el modelo, con qué entra, cómo se lee el resultado y dónde se corta su validez. Por eso hay página de metodología, métricas y advertencias en la misma experiencia, no escondidas en un anexo.

El flujo es el de la figura: el usuario autorizado elige el modelo, carga las variables, el frontend manda el pedido al backend, el backend valida permisos, modelo y entradas, y recién ahí se ejecuta. La base clínica no se modifica. El modelo no escribe pacientes. Devuelve una estimación para analizar.

---

## Slide 16 — Por qué el chat no genera SQL libre

El chat es, de los tres módulos, el que más riesgo introduce si se diseña mal. Un lenguaje natural cómodo puede esconder una ejecución peligrosa.

El enfoque inseguro sería: el usuario pregunta, un modelo genera un SQL, y ese SQL corre contra la base. Aun con usuario de solo lectura, el problema no desaparece. El modelo puede inventar tablas o campos. Puede armar una consulta que no es la pregunta que la persona creyó hacer. Puede ser víctima de instrucciones inyectadas en el texto. Y, sobre todo, se pierde el control de qué está permitido preguntar. En un contexto clínico, una respuesta verosímil y equivocada es peor que un error técnico visible.

Por eso la decisión de producto fue incluir el chat, no sacarlo, pero cambiarle el contrato. El LLM no es un motor de base de datos. Es un intérprete. Traduce la pregunta a una estructura que el sistema ya entiende: un tipo de consulta, un indicador o métrica, un endpoint, un payload. Eso es un catálogo. El catálogo es la frontera autorizada entre el lenguaje humano y los datos históricos.

Si esa estructura no matchea lo permitido —porque la pregunta es clínica en el sentido de “qué tratamiento le doy”, porque el KPI no existe, porque el usuario no tiene permiso, o porque el contrato viene incompleto— el backend rechaza. Y en ese rechazo no se consulta MySQL. Fuera de alcance no es un fallo vergonzoso del sistema: es el comportamiento correcto.

---

## Slide 17 — Flujo del chat

La figura muestra esa anatomía.

El usuario escribe la pregunta en el frontend. El frontend no llama al modelo. Se la manda al backend, autenticada. El backend pide interpretación al LLM Gateway. El Gateway devuelve el contrato. El backend valida catálogo, permisos y esquema.

Si pasa: se ejecuta la operación autorizada y se responde con trazabilidad. Si no pasa: el frontend recibe que esa consulta no está habilitada.

Dos aclaraciones que importan en defensa. Primera: el Gateway puede estar desplegado aparte, pero funcionalmente es una capa nuestra de interpretación, no un atajo para que OpenAI “entre” a la base. Segunda: si hay que diagnosticar una consulta, el detalle técnico —cuando corresponde— es para informática o soporte. El usuario médico necesita una respuesta comprensible, no una lección de SQL. Mostrar el mecanismo interno a todos sería mezclar roles y, además, invitar a una lectura ingenieril de algo que tiene que ser una herramienta de análisis.

---

## Slide 18 — Seguridad y datos

Este es un proyecto de software, pero el objeto son datos de salud. Si la seguridad se cuenta al final, como lista de herramientas, estamos contando mal el diseño.

La plataforma es de uso interno. No está pensada como un portal abierto. Hay autenticación con JWT y autorización por roles. Las consultas analíticas se hacen con un usuario de MySQL de solo lectura: el producto no está para cargar actos, ni para corregir historias, ni para borrar nada. El LLM no tiene credenciales sobre la base.

Hay que separar desarrollo y producción, porque es de las confusiones más frecuentes. En desarrollo y prueba ofuscamos o anonimizamos. Eso reduce exposición mientras construimos y testeamos. No es, por sí solo, la estrategia de producción. En producción el dato es real, y entonces lo que vale es: quién entra, qué rol tiene, qué puede ver, cómo se guardan los secretos, cómo se audita, y cómo se minimiza lo que se expone.

Eso está alineado con un tratamiento responsable de datos personales y de salud: uso acotado, acceso restringido, confidencialidad, trazabilidad. No estamos presentando la ofuscación de desarrollo como si con eso ya estuviera resuelto el INCC en producción.

---

## Slide 19 — Calidad y validación

Calidad, en este proyecto, es poder defender un número, una predicción y una respuesta de chat.

No es una sola batería. Hay unitarias sobre servicios y validaciones. Hay pruebas de API y permisos: si no hay JWT, no entra; si el rol no corresponde, no ve. Hay integración entre backend, Metabase, base y Gateway. Los KPIs se contrastan con SQL de referencia y con el dominio. El chat se prueba en los dos caminos: contrato válido y rechazo. El predictivo se prueba en que la salida traiga metodología, no solo un número. Y el despliegue se prueba en que se pueda levantar otra vez, con contenedores y health checks.

La frase que queremos dejar: un KPI no está listo si solo renderiza. Un chat no está listo si siempre intenta contestar.

---

## Slide 20 — Riesgos y mitigaciones

Los riesgos no desaparecieron porque el producto esté construido; están gestionados.

Datos clínicos: ofuscación en desarrollo, y en producción acceso, roles y solo lectura. Volumen: más de ochenta mil procedimientos; consultas controladas y atención a latencia. Chat: el riesgo no es solo que “rompa” la base, es que conteste mal con cara de certeza; por eso catálogo y rechazo. KPIs: el riesgo es un número lindo y equivocado; por eso SQL de referencia y referentes. LLM: costo y dependencia; el modelo interpreta, no ejecuta, y el Gateway permite cambiar. Alcance: tres módulos, y el crecimiento es por catálogo, no por abrir SQL libre.

Si preguntan cuál era el riesgo más serio, para nosotros es la combinación de dato de salud más una respuesta de IA verosímil. Por eso el chat está adentro del producto, pero no suelto.

---

## Slide 21 — Tecnologías y factibilidad del LLM

El stack se eligió para este problema, no al revés.

React y TypeScript para una interfaz que integra tableros, predicción y chat. Python y FastAPI para APIs, validación y el ecosistema de modelos. MySQL porque es la fuente del instituto. Metabase para BI. Modelos interpretables para el predictivo. Gateway más OpenAI para interpretar lenguaje natural.

La comparación con Ollama no era académica de catálogo. OpenAI nos daba calidad de interpretación con poca infraestructura nuestra, a cambio de costo por uso y de no operar GPUs. Lo local da más control físico y otro perfil de costo, pero hay que mantener hardware y modelos. En seguridad del dato, en ambos casos la regla nuestra es la misma: el proveedor no ejecuta sobre MySQL.

Elegimos OpenAI para interpretar y el backend para ejecutar. Si el instituto más adelante quiere local, el corte está en el Gateway, no en rehacer Cardio Insights.

---

## Slide 22 — Cómo se trabajó

El proceso fue ágil e incremental. No esperamos a tener “todo el diseño perfecto” para construir, porque el dominio se entiende mejor cuando el referente ve un tablero y dice “esto sí, esto no”.

Trabajamos en sprints, con backlog en Jira, código en GitHub, ramas y pull requests, y registro de horas. Hubo comunicación interna frecuente y seguimiento con la tutora. Las decisiones relevantes se fueron documentando, porque este tipo de proyecto no se defiende solo con el software: se defiende con el rastro de por qué se hizo así.

También usamos asistentes de inteligencia artificial como apoyo para redactar y para tareas puntuales de desarrollo. Lo decimos porque el estilo del trabajo y del informe tiene que ser transparente. Lo que no delegamos es el análisis, las decisiones de diseño y la validación. Si algo está en el producto o en el documento, es porque el equipo lo sostiene.

---

## Slide 23 — Resultados

El resultado es una plataforma que está en condiciones de usarse internamente para lo que se propuso.

El instituto puede consultar indicadores clínicos y operativos sin SQL. Puede ver tendencias, filtros y tableros en un solo lugar. Puede explorar un módulo predictivo con las cartas sobre la mesa. Puede hacer preguntas en lenguaje natural dentro de un cerco: el catálogo, los permisos y el backend.

En términos de valor, el cambio es de proceso tanto como de software. Antes, una pregunta frecuente era un pedido a alguien técnico, o una exportación. Ahora es una consulta en la plataforma, con un resultado que se puede contrastar y, en el caso del chat, con una traza de qué se interpretó y qué se ejecutó.

Todo eso sin pretender que el sistema “sepa medicina”. El valor está en reducir fricción, no en sustituir juicio.

---

## Slide 24 — Limitaciones y evolución

Las limitaciones no son un descargo de última hora. Son parte del diseño.

El sistema no recomienda tratamientos. El predictivo no es un dispositivo clínico certificado ni un reemplazo de scores de la especialidad. El chat no es un oráculo: si la pregunta no está en el alcance, no se inventa una respuesta. La plataforma no modifica la operación institucional ni la historia clínica.

La evolución prevista va por el mismo carril, no por “agregar IA porque sí”. Nuevos KPIs, con el procedimiento que ya mostramos. Más modelos, si el dominio y los datos lo sostienen. Ampliar el catálogo de preguntas del chat, con la misma regla de control. Y, si el uso lo justifica, un despliegue más amplio dentro de la institución.

Eso último es importante: el producto está pensado para crecer por catálogo y por módulos, no por ir destapando acceso libre a la base.

---

## Slide 25 — El producto en uso (I)

Antes de la demo en vivo, esto es el sistema.

Acá se ve el acceso interno: no es un sitio abierto. La navegación está en Cardio Insights. Este dashboard está embebido: el usuario no se fue a Metabase. El filtro —año, procedimiento, sector— es una pregunta de negocio, no un parámetro técnico.

Si en la demo algo no carga, esta captura sigue mostrando el recorte del producto.

---

## Slide 26 — El producto en uso (II)

El predictivo no es un número suelto: el resultado va con advertencia y camino a la metodología.

En el chat hay dos pantallas a propósito. Una pregunta que el catálogo puede resolver. Y una que el sistema rechaza. Esa segunda no es un bug de captura. Es el producto diciendo que no está habilitada, sin ir a la base.

---

## Slide 27 — Demostración

Ahora sí, el sistema.

El recorrido que les proponemos es el mismo que haría un usuario interno. Primero el ingreso, para ver que no es una herramienta abierta. Después los dashboards: una categoría, un filtro de período, cómo se lee un indicador. Después el predictivo: cargar variables, ver la estimación y, sobre todo, la metodología y las advertencias. Por último el chat: una pregunta que el catálogo puede resolver, y una que el sistema tiene que rechazar. Esa segunda no es un error de demo. Es el producto funcionando.

Mientras lo mostramos, vamos a señalar dónde está el backend decidiendo, aunque en pantalla se vea “solo” la interfaz. Eso es lo que no se nota si uno mira la herramienta como un sitio más, y es lo que hace que esto sea defendible en un dominio clínico.

### Guion durante la demo

**Login.** Esto es uso interno. Sin sesión no hay KPIs, ni predicción, ni chat.

**Dashboards.** El usuario no está en Metabase. Está en Cardio Insights. El tablero está embebido. El filtro es una pregunta de negocio: por año, por procedimiento, por sector. El número que vemos es el mismo tipo de indicador que contrastamos con SQL de referencia.

**Predictivo.** Acá el sistema no está diciendo qué hacer. Está devolviendo una estimación a partir de variables previas al procedimiento. Si no mostráramos metodología, esta pantalla no debería existir.

**Chat, pregunta válida.** La persona preguntó en castellano. Lo que ocurrió atrás no es un SQL libre. Es interpretación, contrato, validación y ejecución autorizada.

**Chat, fuera de alcance.** Esta es la pregunta que un modelo conversacional común intentaría contestar igual. Nosotros no. No hay consulta a la base. El sistema dice que no está habilitada. Eso es seguridad de producto, no falta de inteligencia.

---

## Slide 28 — Cierre

Para cerrar, Cardio Insights parte de algo que el INCC ya tenía: una historia rica de procedimientos cardiovasculares. Lo que no tenía era un camino razonable para que médicos y gestión la consultaran sin volverse expertos en la base, y sin abrir la puerta a un uso incontrolado de esos datos.

La solución es una plataforma interna, de apoyo a decisiones, con tres modos de acceso —tableros, predicción y lenguaje natural— y una arquitectura que no le entrega la base ni al usuario final ni al modelo de lenguaje. El backend ejecuta. El catálogo limita. La ofuscación protege el desarrollo. La producción se protege con acceso, roles, solo lectura y auditoría. Los KPIs se pueden contrastar. El predictivo se explica. El chat sabe callarse.

Eso es lo que entendemos por un sistema de inteligencia de datos en un instituto de cirugía cardíaca: no más magia, más control, y más evidencia a mano de quien tiene que decidir.

Quedamos a disposición para las preguntas.

---

## Si la mesa se pone técnica o de negocio

- Técnica: slides 11–12, 16–18, 21.
- Negocio: slides 5, 6, 10, 23.
- Calidad / Amalia: slides 8, 9, 14, 19, 20.
