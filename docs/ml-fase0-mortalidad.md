# ML - Fase 0: dataset de mortalidad (diseño, con datos reales)

Documento de diseño para arrancar la funcionalidad de **modelos predictivos**
(machine learning / minería de datos) sobre los datos clínicos del INCC.

> Fase 0 = entender los datos y dejar el dataset bien definido. **No** se entrena
> nada todavía. La calidad del modelo dependerá casi por completo de qué features
> tengamos, no del algoritmo.

Este documento ya está **actualizado con el perfilado real** de la base `incc`
(217.999 episodios), corrido con `scripts/profile_incc_ml.py`.

---

## 1. Hallazgo clave: las cohortes están separadas por tipo de procedimiento

Cada tipo de acto guarda sus factores de riesgo y su desenlace en tablas
distintas, y **no todas se pueden unir**:

| Cohorte | Tabla | Filas realizadas | Features pre-proc. | Target de muerte | ¿Usable para ML? |
| --- | --- | --- | --- | --- | --- |
| **PTCA / angioplastia** | `call_ptcamaster` | 24.313 | `FR*` (factores riesgo) + `CE*` (cuadro de entrada) | `IPfallece` / `PPfallece` (255=sí) | ✅ **Sí, ideal** (todo self-contained) |
| **Cirugía** | `sqlpvd_all` | 14.592 | `FR_*` + `SC_*` + FE/NYHA/ASA + tipo cirugía + reop | `sqlsalud_fallece.Fecha` a 30d (join `CodPac`) | ✅ **Sí** (AUC 0.72) |
| Cardiología (cateterismo/MP) | `flow_procedimientocardiologia` | 25.710 egresos | — | `FechaFallece` (2.11%) | ❌ **No**: sin clave de join a features |

Correcciones respecto del diseño inicial:

- `flow_procedimientocardiologia` **no tiene columna de join** a `flow_coordina`
  (por eso el chat la usa "de forma independiente"). Sirve para KPIs agregados de
  mortalidad, **no** para un modelo por paciente (no se le pueden pegar features).
- `pvd_master` **no** contiene factores de riesgo: son contadores
  `Form_A..Form_T` de completitud de formulario. Descartada como fuente de features.
- Los factores de riesgo reales están en **`dat_cirugia`** (cirugía) y
  **`call_ptcamaster`** (PTCA).

---

## 2. Modelo #1 recomendado: mortalidad en PTCA (`call_ptcamaster`)

Es la mejor opción para arrancar: **self-contained** (features + target en la
misma tabla), buen `n` (24.313) y sin joins ambiguos.

- **Target (`y`)**: `1` si `IPfallece = 255` OR `PPfallece = 255`, si no `0`.
  - Base rate real: **317 / 24.313 = 1.30%** → problema **muy desbalanceado**.
    Usar `class_weight='balanced'` o SMOTE, y medir con **AUC-PR** + **Brier** +
    curva de calibración (NO accuracy).
- **Población**: `call_ptcamaster` unido a `flow_coordina` con
  `f.FechaRealizado > '1900-01-01'` (procedimiento efectivamente realizado).

---

## 3. Regla anti-*leakage* (la más importante)

En `call_ptcamaster` los prefijos codifican el momento del dato:

| Prefijo | Significado | ¿Feature? |
| --- | --- | --- |
| `FR*` | Factores de riesgo (previos) | ✅ sí |
| `CE*` | Cuadro de entrada / estado clínico al ingreso | ✅ sí |
| `PA*` | Acciones del procedimiento (biac, rotablator...) | ❌ intra-procedimiento |
| `IP*` | Eventos **intra**-procedimiento (incluye `IPfallece`) | ❌ (parte del desenlace) |
| `PP*` | Eventos **post**-procedimiento (incluye `PPfallece`) | ❌ (parte del desenlace) |

Regla: **solo `FR*` y `CE*` son features.** Todo `IP*`, `PP*`, `PA*` ocurre
durante/después → no puede predecir el desenlace (`IPfallece`/`PPfallece` son,
de hecho, el target).

---

## 4. Features candidatas (PTCA, pre-procedimiento)

> **Codificación crítica (verificada en el perfilado):** en los flags clínicos
> `FR*`/`CE*`, **`255` = "sí"** y **`0` = "no"** (misma convención que
> `IPfallece`). El valor `1` aparece 1–7 veces → **ruido de carga**, mapearlo a
> "no" o descartarlo. Encodear como binaria: `feature = 1 if valor == 255 else 0`.
> Prevalencias reales confirmadas (realistas): HTA ~64%, diabetes ~24%,
> dislipemia ~51%, IAM en curso ~18%, insuf. renal ~4%.

**Binarias `FR*`/`CE*` (USAR, tienen señal)**: `FRhipertension`, `FRtabaco`,
`FRdiabetes`, `FRobesidad`, `FRsedentario`, `FRdislipemia`, `FRanteFam*`,
`FRenfVascular*`, `CEinsRenal`, `CEinsRenalDialis`, `CEfuncVentricular`,
`CEangorEstable`, `CEangorInestable`, `CEiamPrevio`, `CEiamCurso`,
`CEinsufCardiaca`, `CEarritmia`, `CEestudioFuncional*`.

**Numéricas `FR*` — ⚠️ DESCARTAR (vacías)**: `FRimc` (casi todo 0), `FRldl`
(100% en 0), `CEtasaFiltracionGlomecular` (100% en 0). No están cargadas → no
aportan. (Revisar `FRpeso`/`FRtalla` con el perfilado antes de usarlas.)

Demográficas (join a núcleo/paciente):
- Edad: `flow_coordina.EdadCoo` (⚠️ ver §7, hay valores imposibles hasta 137) o,
  mejor, `TIMESTAMPDIFF(YEAR, pac_ficha.FecNace, f.FechaRealizado)`.
- Sexo: `pac_ficha.CodSexo` (2=57.717, 1=27.095, 0=1.297 "sin dato").
- Centro derivador: `flow_coordina.CodSeguroCoo` (181 valores → agrupar los raros).

Códigos `*Tipo` (int): son categóricos, no numéricos → tratarlos como categoría.

---

## 5. SQL borrador de extracción del dataset (PTCA)

```sql
SELECT
    -- ===== Identificador (NO feature) =====
    c.Cod                                              AS cod_ptca,

    -- ===== Features demográficas =====
    TIMESTAMPDIFF(YEAR, pf.FecNace, f.FechaRealizado)  AS edad,
    pf.CodSexo                                         AS sexo,
    f.CodSeguroCoo                                     AS centro,

    -- ===== Features FR* (factores de riesgo, pre) — binarias 255=sí/0=no =====
    c.FRhipertension, c.FRtabaco, c.FRdiabetes, c.FRobesidad, c.FRsedentario,
    c.FRdislipemia, c.FRenfVascular, c.FRenfVascular_MMii,
    c.FRenfVascular_CerebroVascular, c.FRanteFam, c.FRanteFamCoro, c.FRanteFamMS,

    -- ===== Features CE* (cuadro de entrada, pre) — binarias 255=sí/0=no =====
    c.CEinsRenal, c.CEinsRenalDialis, c.CEfuncVentricular,
    c.CEangorEstable, c.CEangorInestable, c.CEiamPrevio, c.CEiamCurso,
    c.CEinsufCardiaca, c.CEarritmia,
    -- NB: NO incluir FRimc/FRldl/CEtasaFiltracionGlomecular (vacías, todo 0).

    -- ===== Target =====
    CASE WHEN c.IPfallece = 255 OR c.PPfallece = 255 THEN 1 ELSE 0 END AS fallecio

FROM call_ptcamaster c
JOIN flow_coordina f ON f.Cod = c.CodCoordina
LEFT JOIN pac_ficha pf ON pf.Cod = f.CodPac
WHERE f.FechaRealizado > '1900-01-01'
;
```

Encoding/limpieza posterior (en pandas):
- Flags `FR*`/`CE*`: `feature = (valor == 255).astype(int)` (255=sí, resto=no; el
  `1` esporádico es ruido → queda como "no").
- Target: ya viene 0/1 del `CASE`.
- Fechas `<= '1900-01-01'` → NaN; numéricos `-99` → NaN.
- Edad: capear a `[0, 110]`; fuera de rango → NaN.
- `pac_ficha.CodSexo = 0` (1.297 casos) → NaN (sin dato).

---

## 6. Modelo #2: mortalidad quirúrgica (`sqlpvd_all`)

Resuelto usando la tabla `sqlpvd_all` (formulario perioperatorio, 14.599 filas,
449 columnas) en vez de `dat_cirugia`/`pvd_master`.

- **Target**: **mortalidad a 30 días** — `1` si el paciente figura en el registro
  **`sqlsalud_fallece`** con `Fecha` (fecha de muerte) dentro de los 30 días
  posteriores a `FechaRealizado`. Base rate ≈ **7.3%** (usando todos los años).
- **Features**:
  - Comorbilidades `FR_*` y situación clínica `SC_*` (`255 = "sí"`), + edad +
    creatinina (`FR_Crea`) + sexo (join `pac_ficha`).
  - **Enriquecimiento pre-op** (del perfilado, gran salto de AUC): fracción de
    eyección (`CCHemo_Eyeccion`), hematocrito pre (`DatosCEC_HematocritoPre`),
    vasos coronarios afectados, clase funcional NYHA (`MP_NYHA`), clasificación de
    riesgo anestésico ASA (`Anestesia_ClasificacionRiesgo`), clase de cirugía
    (`DatosCC_CodCirugiaClase`), tipo de procedimiento (ByPass / Aórtico / Mitral /
    Tricúspide / Combinado), **reintervención** (`IP_CCprevio`), enfermedad
    valvular AO/MI, taponamiento (`SC_Tapon`).
- **Resultado del baseline enriquecido** (regresión logística, validación temporal
  `año >= 2018`): **AUC-ROC 0.72** (CV 0.725), AUC-PR 0.23 (2.8× azar), Brier 0.21.
  Salto desde el baseline mínimo (0.65) al sumar las variables pre-op.
- **Odds ratios coherentes**: reintervención ×2.1, falla renal ×2.1, cirugía clase 3
  ×2.3, valvular mitral/aórtica ×1.8, combinada ×1.6, taponamiento ×1.8, shock/BIAC
  ×1.4, edad ×1.35; fracción de eyección protectora (×0.74). Cirugía clase 1
  (electiva/simple) protectora (×0.54).
- **Techo alcanzado (finding honesto)**: se probaron las dos palancas de mayor
  impacto teórico y **no mejoraron la discriminación**:
  - Sumar **urgencia/prioridad** (`CodCoordinaReglaMotivo`), **IAM reciente**
    (`DatosCC_CondicionesIAM`) e **insuficiencia mitral** (`CCHemo_InsuficienciaMI`):
    AUC test 0.72 → 0.71 (CV 0.725 → 0.726, plano). La urgencia tenía señal
    univariada fuerte pero es **redundante** con clase de cirugía / tipo de
    procedimiento / shock, que ya la capturan.
  - **Gradient Boosting** (HistGB, class_weight balanced): AUC test 0.70, CV 0.71
    → **no supera a la regresión logística** en discriminación (sí mejora la
    calibración, Brier 0.197). Con ~9k filas y features mayormente binarias, la
    logística está en el techo del dato.
  - `CCHemo_PAPs` (HT pulmonar): descartada, 96% sin dato.
- **Conclusión**: el modelo quirúrgico se estabiliza en **AUC ≈ 0.72** con
  regresión logística. Es un plateau de **dato**, no de algoritmo. Subir de ahí
  requeriría variables pre-op nuevas y bien cargadas (no disponibles hoy).
  Modelo elegido: **regresión logística** (interpretable, mejor AUC, odds ratios
  clínicamente válidos).

Fuente de muerte con fecha — **`sqlsalud_fallece`** (hallazgo clave):
- Registro de fallecimientos: 5.195 filas (1 por paciente), con `Fecha` (fecha de
  muerte), `Tipo` (causa: Cardíaca 2.668, Sin Identificar 1.868, Tumor, Sepsis…) y
  join `NroHistoria = pac_ficha.Cod = sqlpvd_all.CodPac` (**100% de match**).
- **Cubre años recientes** (2023: 156, 2024: 136, 2025: 120, 2026: 25) → elimina
  la necesidad del corte temporal y permite testear en datos actuales.
- La mortalidad a 30d que produce (6.7% global) **coincide** con el desenlace del
  formulario `sqlpvd_all` (6.5%) → ambas fuentes se validan mutuamente.
- Aplica a **ambas cohortes** por `pac_ficha.Cod`. Nota: para **PTCA** el registro
  solo captura 53 muertes a 30d vs 317 del formulario (`IPfallece`/`PPfallece`) →
  para PTCA el formulario es más completo; idealmente combinar ambos (OR).

Otras notas (descartadas como fuente de muerte):
- **`salud_paciente` NO tiene fecha de fallecimiento** (solo demografía).
- `pac_ficha.Fallecio` = "falleció alguna vez" (~13%) → mortalidad de por vida, no
  del acto. Descartado como target.
- `pac_fichafallece_evaluaborrar.FecFallece` existe pero es tabla "evaluaborrar"
  (marcada para borrar) → frágil; `sqlsalud_fallece` la reemplaza.

> Para PTCA conviene migrar el dataset de `call_ptcamaster` a
> **`sqlcall_ptcamaster`** (misma info + columnas `*Detalle` y `FechaRealizado`
> propia, sin depender de `flow_coordina` para la fecha).

---

## 7. Advertencias de calidad de dato (del perfilado real)

- `flow_coordina.EdadCoo`: min 0, **max 137** (imposible) → capear a rango
  plausible (p. ej. 0–110).
- `dat_cirugia.POestadiaUCI`: **98% centinela** (`-99`) → casi inútil, pero
  igual es postoperatorio (leakage) para mortalidad.
- Complicaciones quirúrgicas (`CIOstroke`, `CIOsepsis`, `CIOfallaRenalAguda`):
  **casi no registradas** (1–2 positivos en 2.745) → **un modelo de
  complicaciones NO es viable hoy** con estos datos. Anotarlo como limitación.
- **Trampa de codificación**: `255` NO siempre es "sin dato". En los flags
  clínicos (`FR*`, `CE*`, `IPfallece`...) `255` = "sí". Confirmar por columna con
  el perfilado antes de encodear.
- Features numéricas de PTCA (`FRimc`, `FRldl`, `CEtasaFiltracionGlomecular`):
  **vacías** (todo/casi todo 0) → descartar.
- Features binarias de PTCA **vacías** (100% en 0, detectado al entrenar):
  `FRsedentario`, `FRenfVascular_MMii`, `FRenfVascular_CerebroVascular` → quitar.
- **Outcome sin cargar en años recientes** (crítico): en `call_ptcamaster`,
  `IPfallece`/`PPfallece` figuran 0 para **2024–2026** (0% mortalidad, imposible).
  Los outcomes se cargan con retraso → esas filas son negativos falsos. Entrenar
  solo con años con outcome consolidado (`anio <= 2023`).
- Reingreso: se puede intentar a futuro vía `flow_coordina.CodReingreso` /
  `CodCoordinaReglaMotivo IN (105,109,120)` (a validar).

---

## 8. Cómo correr / re-correr el perfilado

Script: `backend/scripts/profile_incc_ml.py` (solo lectura, `pymysql`).

```bash
cd backend
set INCC_MYSQL_HOST=190.64.90.170
set INCC_MYSQL_PORT=8809
set INCC_MYSQL_USER=proyecto
set INCC_MYSQL_PASSWORD=proyecto
set INCC_MYSQL_DB=incc
python scripts/profile_incc_ml.py --full-columns --json perfil_incc.json
```

---

## 9. Estado de las fases

1. **Fase 1** ✅ — notebooks EDA + baseline (`notebooks/ptca_mortality_eda.ipynb`,
   `notebooks/surgery_mortality_eda.ipynb`). PTCA AUC-ROC 0.82; cirugía 0.72.
2. **Fase 2** ✅ — **productivización** (ver §10).
3. **Fase 3** ✅ — explicabilidad por caso y lectura en lenguaje llano:
   - `ml_service.explain()` calcula la **contribución exacta** de cada variable a la
     predicción (`coef_i · (x_i − media_i)` en log-odds; SHAP exacto para el modelo
     lineal, sin dependencias extra). Se guarda un modelo interpretable
     (`*_interp.joblib`) y las medias de features para el "paciente promedio".
   - La respuesta incluye `explanation` (waterfall: qué sube/baja el riesgo) y
     `risk_ratio` (cuántas veces la tasa base).
   - El frontend muestra el waterfall, el riesgo relativo, el significado del nivel,
     tooltips de métricas y una sección "¿Cómo leer esta estimación?".
4. **Fase 4** ✅ — fuente de muerte quirúrgica resuelta con `sqlsalud_fallece`
   (mortalidad a 30d datada) + enriquecimiento de features (§6).

> Recordatorio de rigor: es una **herramienta de apoyo / investigación**, no un
> sistema de decisión clínica. Documentar siempre limitaciones.

---

## 10. Fase 2 — Productivización (implementada)

Arquitectura offline (entrenamiento) / online (serving), sin acoplar el API a la BD:

- **`app/ml/specs.py`**: fuente única de verdad por cohorte (SQL de extracción,
  grupos de features, limpieza `clean_common` idéntica en train e inferencia, y
  `fields` = contrato de la API + metadatos para el formulario del frontend).
- **`app/ml/training.py`** + **`scripts/train_ml_models.py`**: entrenan offline
  contra la BD real, validan temporalmente y serializan en `backend/models/`:
  - `<cohorte>_mortality.joblib` — pipeline sklearn **calibrado** (Platt/sigmoid)
    para que `predict_proba` refleje la prevalencia real (Brier PTCA 0.006,
    cirugía 0.071), reentrenado con todos los datos.
  - `<cohorte>_mortality.json` — métricas de validación temporal, umbral (Youden),
    tasa base, odds ratios, vocabulario categórico y campos de UI.
- **`app/services/ml_service.py`**: carga los `.joblib` (import perezoso de joblib,
  cache LRU), arma la fila de entrada, aplica la misma limpieza y devuelve
  probabilidad + nivel de riesgo (bajo/moderado/alto) + factores presentes de
  mayor peso (odds ratio).
- **Endpoints** (`app/api/v1/predictions.py`, requieren JWT):
  - `GET /api/v1/predictions/models` — catálogo + campos para el formulario.
  - `GET /api/v1/predictions/models/{cohort}` — metadatos de un modelo.
  - `POST /api/v1/predictions/{cohort}` — predicción para un caso (`{ "values": {...} }`).
- **Frontend** (`/ml`): `features/predictions/predictionsApi.ts` + `routes/MLPage.tsx`
  renderizan el formulario dinámicamente desde `features`, muestran la probabilidad
  calibrada, el nivel de riesgo, los factores de mayor peso y las métricas del
  modelo, con el disclaimer de herramienta de apoyo.

Reentrenar los modelos:

```bash
cd backend
set INCC_MYSQL_HOST=190.64.90.170
set INCC_MYSQL_PORT=8809
set INCC_MYSQL_USER=proyecto
set INCC_MYSQL_PASSWORD=proyecto
set INCC_MYSQL_DB=incc
python -m scripts.train_ml_models            # ambos
python -m scripts.train_ml_models ptca        # una cohorte
```

Nota: el modelo servido de PTCA excluye la variable administrativa `centro`
(seguro/derivador) para ser un calculador puramente clínico; por eso su AUC de
validación (0.78) es algo menor al del notebook exploratorio (0.82, que la incluye).
