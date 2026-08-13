# Componente de Machine Learning — Informe del proyecto

Predicción de resultados de procedimientos cardíacos (mortalidad y complicaciones)
sobre los datos históricos del **Instituto Nacional de Cirugía Cardíaca (INCC)**.

Documento orientado a la **defensa**: explica qué se construyó, con qué criterios,
qué resultados se obtuvieron, las limitaciones honestas y cómo reproducirlo.

---

## 1. Objetivo

Aplicar **modelos predictivos** para anticipar posibles resultados de un
procedimiento médico a partir de las características del paciente conocidas **antes**
del acto. Del alcance original (complicaciones, mortalidad, reingresos) se
implementaron:

| # | Modelo | Predice | Cohorte |
|---|--------|---------|---------|
| 1 | Mortalidad PTCA | Mortalidad de la angioplastia | `call_ptcamaster` |
| 2 | Mortalidad quirúrgica | Mortalidad a 30 días de cirugía cardíaca | `sqlpvd_all` |
| 3 | Complicaciones quirúrgicas | Complicación grave intrahospitalaria | `sqlpvd_all` |

Los reingresos se evaluaron y **se descartaron** por baja calidad del dato (ver §8).

---

## 2. Qué es (y qué no es) esta funcionalidad

- Es **minería de datos** (data mining): descubrir patrones y relaciones útiles a
  partir de datos históricos.
- Se implementa con **machine learning supervisado**, concretamente un modelo de
  **clasificación binaria** (¿ocurre el evento: sí / no?).
- El algoritmo es **regresión logística calibrada**. **No** se usan redes
  neuronales ni IA generativa (justificación en §5 y §11).

Brinda dos usos del mismo modelo:
1. **Predecir** el riesgo de un paciente concreto antes del procedimiento.
2. **Descubrir y cuantificar** qué factores se asocian al riesgo (a nivel global y
   caso por caso).

---

## 3. Datos y definición de los objetivos (targets)

Cada tipo de procedimiento guarda su información en tablas distintas, con su propia
clave. Todos los modelos usan **solo procedimientos efectivamente realizados**
(fecha válida, descartando nulos lógicos `≤ 1900-01-01`).

- **Mortalidad PTCA**: `target = 1` si el formulario marca fallecimiento
  intra/post-procedimiento (`IPfallece` o `PPfallece`).
- **Mortalidad quirúrgica (30 días)**: `target = 1` si el paciente figura en el
  registro de fallecimientos `sqlsalud_fallece` con fecha de muerte dentro de los 30
  días posteriores a la cirugía. Se usa el registro reciente (2021+), que incorpora
  el **EuroSCORE**.
- **Complicaciones graves**: `target = 1` si hubo al menos una complicación grave
  intrahospitalaria: falla renal, hemodiálisis, sangrado quirúrgico, resutura o
  dehiscencia. Registrado 2008–2022 (desde 2023 no se carga), por eso el modelo se
  entrena con esa ventana.

---

## 4. Regla anti-fuga de información (anti-leakage)

Es la regla más importante del diseño. Se usan **únicamente variables conocidas
antes del procedimiento**: factores de riesgo, comorbilidades, cuadro clínico de
ingreso, función cardíaca y tipo de cirugía.

Se **excluyen deliberadamente** todas las variables intra y postoperatorias
(complicaciones del acto, tiempos de circulación extracorpórea, estadía en UCI,
etc.). Usarlas "haría trampa": inflaría artificialmente las métricas porque no
estarían disponibles en el momento en que la predicción sería útil.

En PTCA esto se codifica por prefijo: `FR*` (factores de riesgo) y `CE*` (cuadro de
entrada) son features; `IP*`/`PP*`/`PA*` (intra/post) quedan afuera.

---

## 5. Metodología

1. **Preprocesamiento** (idéntico en entrenamiento e inferencia, para no introducir
   sesgos):
   - Flags clínicos: `255 = "sí"` → 1, resto → 0.
   - Numéricas: imputación por mediana + estandarización; se limpian valores
     imposibles (ej. edad fuera de 0–110) a nulo.
   - Categóricas: imputación por moda + one-hot encoding.
2. **Modelo**: **regresión logística** con `class_weight="balanced"` (compensa el
   desbalanceo de clases, porque los eventos son minoritarios).
3. **Calibración**: se envuelve en `CalibratedClassifierCV` (Platt/sigmoide) para que
   las probabilidades reflejen la **frecuencia real observada** (no el peso artificial
   de clases). Esto se mide con el **Brier score**.
4. **Validación temporal**: se entrena con los años más antiguos y se evalúa con los
   más recientes, simulando el uso real (predecir el futuro con datos del pasado).
   Es más honesto y exigente que un split aleatorio.

> Separación offline/online: el entrenamiento corre a mano contra la base
> (`scripts/train_ml_models.py`) y serializa el modelo; el servicio del API solo
> carga el artefacto y predice, **sin tocar la base** en tiempo real.

---

## 6. Explicabilidad

Para cada predicción se calcula la **contribución exacta de cada variable** al
resultado: `contribución_i = coef_i × (x_i − media_i)` en log-odds. Para un modelo
lineal esto equivale a los **valores SHAP exactos**, sin dependencias externas.

- En la interfaz se muestra como un gráfico de barras ("¿qué pesó?"): qué **sube**
  (rojo) o **baja** (verde) el riesgo de ese paciente, y con qué intensidad
  (fuerte/medio/leve).
- A nivel global, los **odds ratios** indican los factores más influyentes del
  modelo.

Esto hace que cada estimación sea **auditable**, un requisito clave en salud y el
principal motivo de elegir un modelo interpretable.

---

## 7. Resultados (validación temporal)

| Modelo | Casos | Eventos | Base | AUC-ROC | AUC-PR | Brier |
|--------|------:|--------:|-----:|--------:|-------:|------:|
| Mortalidad PTCA | 13.978 | 177 | 1.3% | **0.775** | 0.122 | 0.006 |
| Mortalidad quirúrgica (30 d) | 1.513 | 115 | 8.7% | **0.792** | 0.354 | 0.071 |
| Complicaciones quirúrgicas | 6.498 | 1.659 | 25.5% | **0.706** | 0.436 | 0.189 |

Lectura de las métricas:
- **AUC-ROC**: capacidad de ordenar el riesgo (0.5 = azar, 1.0 = perfecto). Los tres
  modelos se despegan claramente del azar.
- **AUC-PR**: desempeño detectando los casos positivos (poco frecuentes) frente a su
  tasa base. En los tres hay **mejora real** sobre el azar (ej. complicaciones 0.436
  vs 0.276 de base; mortalidad quirúrgica 0.354 vs 0.087).
- **Brier**: calibración (más bajo = mejor); confirma que las probabilidades son
  fieles a la frecuencia real.

### Factores más influyentes (ejemplos coherentes clínicamente)
- Cirugía: clase de cirugía 4 y **emergencia** elevan fuertemente el riesgo;
  reintervención, falla renal y cirugía valvular también; fracción de eyección alta
  es protectora.
- El **EuroSCORE** (score internacional de riesgo quirúrgico) resultó un predictor
  muy fuerte de mortalidad (AUC ≈ 0.82 por sí solo en los casos donde está cargado).

---

## 8. Decisiones y hallazgos destacados

- **EuroSCORE (mortalidad quirúrgica)**: se encontró en
  `flow_procedimientocardiologiablockdetalle` (join por `CodMaster`). Se registra
  desde 2021 (cobertura ~90%). Incorporarlo llevó el modelo de AUC 0.72 → **0.79**.
  Se dejó como campo **opcional**: si no está, el modelo predice igual con el resto.
- **Reingresos — descartado**: definir "reingreso a 30 días" vía nuevas
  coordinaciones daba una prevalencia **inestable** (34% en 2010-2016 → 7% en 2020+),
  señal de que mezcla controles programados con reingresos reales y que la forma de
  registrar cambió. Un modelo así no sería confiable ni defendible.
- **Techo de datos, no de algoritmo**: se probaron variables adicionales y
  **Gradient Boosting**; no mejoraron la discriminación. La limitación es la
  información disponible, no el método.

---

## 9. Limitaciones (declaradas explícitamente)

- Es una herramienta de **apoyo e investigación**, **no** un sistema de decisión
  clínica; no reemplaza el juicio médico.
- Las **complicaciones** son más difíciles de anticipar solo con datos
  pre-operatorios (AUC ≈ 0.71): dependen en parte del propio acto quirúrgico.
- El **EuroSCORE** solo existe desde 2021 → el modelo quirúrgico se entrena con la
  era reciente (~1.500 casos).
- No considera variables no registradas ni la evolución clínica en tiempo real.
- Es un modelo **estadístico poblacional**: las asociaciones no implican causalidad.

---

## 10. Arquitectura e integración

- **Backend (FastAPI)**:
  - `app/ml/specs.py`: fuente única de verdad por cohorte (SQL, features, limpieza,
    campos de UI).
  - `app/ml/training.py` + `scripts/train_ml_models.py`: entrenamiento offline y
    serialización (`backend/models/*.joblib` + `.json` con métricas, curva ROC, odds
    ratios y campos).
  - `app/services/ml_service.py`: serving (carga perezosa, predicción + explicación).
  - `app/api/v1/predictions.py`: endpoints con autenticación JWT
    (`GET /predictions/models`, `POST /predictions/{cohort}`).
- **Frontend (React)**:
  - `routes/MLPage.tsx`: formulario dinámico por modelo, resultado calibrado, nivel
    de riesgo, riesgo relativo y explicación por caso, en lenguaje llano.
  - `routes/MethodologyPage.tsx`: metodología, métricas, **curvas ROC**, variables por
    modelo y factores más influyentes (material de transparencia para la defensa).

---

## 11. Preguntas frecuentes anticipadas (defensa)

**¿Por qué regresión logística y no redes neuronales / deep learning?**
Con este volumen de datos (cientos a pocos miles de casos por modelo) y variables
mayormente clínicas/binarias, un modelo lineal rinde igual o mejor y no se
sobreajusta. Además es **interpretable**: se puede justificar cada predicción, algo
imprescindible en salud. Se probó Gradient Boosting y no mejoró la discriminación.

**¿Cómo evitan el sobreajuste y la fuga de información (leakage)?**
Validación **temporal** (no aleatoria), calibración con validación cruzada interna, y
una regla estricta de **solo variables pre-procedimiento** (§4). Se excluye
deliberadamente todo lo intra/postoperatorio.

**¿Por qué validación temporal y no k-fold aleatorio?**
Porque el uso real es predecir el futuro con datos del pasado. Un split aleatorio
sería optimista (el modelo "vería" datos del mismo período que luego evalúa).

**¿Qué significa que esté "calibrado"?**
Que si el modelo dice 10%, aproximadamente 1 de cada 10 pacientes similares
efectivamente presenta el evento. Se verifica con el Brier score.

**¿Cómo manejan el desbalance (pocos eventos)?**
Con `class_weight="balanced"` en el entrenamiento y midiendo con **AUC-PR** y
**Brier** (no con "accuracy", que sería engañosa con eventos raros).

**¿Cómo se explica una predicción individual?**
Con la descomposición exacta en log-odds (equivalente a SHAP para el modelo lineal),
que se muestra como el gráfico "¿qué pesó?".

**¿Se puede usar para decidir sobre un paciente?**
No como criterio único. Es apoyo a la evaluación clínica; así está declarado en la
propia interfaz y en este informe.

---

## 12. Cómo reproducir

```bash
cd backend
set INCC_MYSQL_HOST=190.64.90.170
set INCC_MYSQL_PORT=8809
set INCC_MYSQL_USER=proyecto
set INCC_MYSQL_PASSWORD=proyecto
set INCC_MYSQL_DB=incc

python -m scripts.train_ml_models                 # entrena los tres modelos
python -m scripts.train_ml_models surgery         # o una sola cohorte
```

Los artefactos se guardan en `backend/models/`. El API los carga automáticamente al
iniciar; el frontend arma la interfaz a partir de sus metadatos.

> Documento complementario de diseño/perfilado técnico: `docs/ml-fase0-mortalidad.md`.
