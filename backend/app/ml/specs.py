"""Especificación de los modelos de mortalidad (fuente única de verdad).

Cada `CohortSpec` define:
- El SQL de extracción (offline, contra la BD real).
- Los grupos de features (numéricas / categóricas / binarias) que ve el modelo.
- La limpieza `clean_common`, IDÉNTICA en entrenamiento y en inferencia, para que
  no haya skew entre ambos.
- Los `fields`: contrato de entrada de la API + metadatos para renderizar el
  formulario en el frontend.

Reglas de dato del INCC reflejadas acá:
- Flags clínicos: `255 = "sí"` -> 1, resto -> 0.
- Fechas `<= '1900-01-01'` = nulos lógicos.
- Mortalidad quirúrgica a 30 días vía `sqlsalud_fallece` (registro con fecha).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd


@dataclass
class Field:
    """Un campo de entrada del modelo (y del formulario de la UI)."""

    key: str                      # columna cruda que ve el modelo
    kind: str                     # 'bool' | 'number' | 'select'
    label: str
    group: str = "Otros"          # agrupación para la UI
    unit: str | None = None
    min: float | None = None
    max: float | None = None
    step: float | None = None
    options: list[dict[str, Any]] | None = None   # [{value,label}] para 'select'
    help: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = {"key": self.key, "kind": self.kind, "label": self.label, "group": self.group}
        for k in ("unit", "min", "max", "step", "options", "help"):
            v = getattr(self, k)
            if v is not None:
                d[k] = v
        return d


@dataclass
class CohortSpec:
    name: str
    title: str
    description: str
    sql: str
    numeric: list[str]
    categorical: list[str]
    binary: list[str]
    clean_common: Callable[[pd.DataFrame], pd.DataFrame]
    fields: list[Field]
    year_col: str = "anio"
    target_col: str = "fallecio"
    min_year: int = 2005
    outcome: str = "mortalidad"                        # sustantivo para la UI
    target_desc: str = "mortalidad del procedimiento"  # descripción del target

    @property
    def features(self) -> list[str]:
        return self.numeric + self.categorical + self.binary


def _as_category(series: pd.Series, na_values: tuple = ()) -> pd.Series:
    """A object-string con np.nan (evita pd.NA, que rompe SimpleImputer)."""
    s = pd.to_numeric(series, errors="coerce")
    if na_values:
        s = s.where(~s.isin(list(na_values)), np.nan)
    return s.apply(lambda v: str(int(v)) if pd.notna(v) else np.nan).astype(object)


def _clean_flags(df: pd.DataFrame, flags: list[str]) -> None:
    for col in flags:
        df[col] = (pd.to_numeric(df[col], errors="coerce") == 255).astype(int)


# --------------------------------------------------------------------------- #
# PTCA / angioplastia
# --------------------------------------------------------------------------- #
PTCA_FR = [
    "FRhipertension", "FRtabaco", "FRdiabetes", "FRobesidad", "FRsedentario",
    "FRdislipemia", "FRenfVascular", "FRenfVascular_MMii",
    "FRenfVascular_CerebroVascular", "FRanteFam", "FRanteFamCoro", "FRanteFamMS",
]
PTCA_CE = [
    "CEinsRenal", "CEinsRenalDialis", "CEfuncVentricular", "CEangorEstable",
    "CEangorInestable", "CEiamPrevio", "CEiamCurso", "CEinsufCardiaca", "CEarritmia",
]
PTCA_FLAGS = PTCA_FR + PTCA_CE

_PTCA_LABELS = {
    "FRhipertension": "Hipertensión arterial", "FRtabaco": "Tabaquismo",
    "FRdiabetes": "Diabetes", "FRobesidad": "Obesidad", "FRsedentario": "Sedentarismo",
    "FRdislipemia": "Dislipemia", "FRenfVascular": "Enfermedad vascular",
    "FRenfVascular_MMii": "Enf. vascular miembros inferiores",
    "FRenfVascular_CerebroVascular": "Enfermedad cerebrovascular",
    "FRanteFam": "Antecedentes familiares",
    "FRanteFamCoro": "Antec. familiares coronarios",
    "FRanteFamMS": "Antec. familiares de muerte súbita",
    "CEinsRenal": "Insuficiencia renal", "CEinsRenalDialis": "Insuf. renal en diálisis",
    "CEfuncVentricular": "Disfunción ventricular", "CEangorEstable": "Angor estable",
    "CEangorInestable": "Angor inestable", "CEiamPrevio": "IAM previo",
    "CEiamCurso": "IAM en curso", "CEinsufCardiaca": "Insuficiencia cardíaca",
    "CEarritmia": "Arritmia",
}

_SEXO_OPTIONS = [{"value": "1", "label": "Masculino"}, {"value": "2", "label": "Femenino"}]

PTCA_SQL = f"""
SELECT
    f.EdadCoo                   AS edad,
    pf.CodSexo                  AS sexo,
    YEAR(f.FechaRealizado)      AS anio,
    {",".join("c." + c for c in PTCA_FLAGS)},
    CASE WHEN c.IPfallece = 255 OR c.PPfallece = 255 THEN 1 ELSE 0 END AS fallecio
FROM call_ptcamaster c
JOIN flow_coordina f ON f.Cod = c.CodCoordina
LEFT JOIN pac_ficha pf ON pf.Cod = f.CodPac
WHERE f.FechaRealizado > '1900-01-01'
"""


def _clean_ptca(df: pd.DataFrame) -> pd.DataFrame:
    _clean_flags(df, PTCA_FLAGS)
    df["edad"] = pd.to_numeric(df["edad"], errors="coerce")
    df.loc[(df["edad"] < 0) | (df["edad"] > 110), "edad"] = np.nan
    df["sexo"] = _as_category(df["sexo"], na_values=(0,))
    return df


def _ptca_fields() -> list[Field]:
    fields = [
        Field("edad", "number", "Edad", group="Demografía", unit="años", min=0, max=110, step=1),
        Field("sexo", "select", "Sexo", group="Demografía", options=_SEXO_OPTIONS),
    ]
    for k in PTCA_FR:
        fields.append(Field(k, "bool", _PTCA_LABELS[k], group="Factores de riesgo"))
    for k in PTCA_CE:
        fields.append(Field(k, "bool", _PTCA_LABELS[k], group="Cuadro de entrada"))
    return fields


PTCA_SPEC = CohortSpec(
    name="ptca",
    title="Mortalidad PTCA / angioplastia",
    description=(
        "Estima la probabilidad de mortalidad asociada a una angioplastia coronaria "
        "(PTCA) a partir de factores de riesgo y cuadro clínico de entrada."
    ),
    sql=PTCA_SQL,
    numeric=["edad"],
    categorical=["sexo"],
    binary=PTCA_FLAGS,
    clean_common=_clean_ptca,
    fields=_ptca_fields(),
    outcome="mortalidad",
    target_desc="mortalidad del procedimiento",
)


# --------------------------------------------------------------------------- #
# Cirugía cardíaca
# --------------------------------------------------------------------------- #
SURG_FR = [
    "FR_Cig", "FR_Hiper", "FR_Diab", "FR_Obeso", "FR_Dislipemia", "FR_AVE",
    "FR_Eceva", "FR_EPOC", "FR_FallaRen", "FR_IRC", "FR_AF", "FR_Apnea",
]
SURG_SC = [
    "SC_IAM", "SC_Shock", "SC_BIAC", "SC_Arritmia", "SC_Angina", "SC_Trombo", "SC_MP",
    "SC_Tapon", "SC_Cardia",
]
SURG_PROC = [
    "Procedimiento_ByPass", "Procedimiento_Aortico", "Procedimiento_Mitral",
    "Procedimiento_Tricuspide", "Procedimiento_Combinado",
    "IP_CCprevio", "CCHemo_EnfermedadAO", "CCHemo_EnfermedadMI",
    "DatosCC_CondicionesIAM",
]
SURG_FLAGS = SURG_FR + SURG_SC + SURG_PROC

_SURG_LABELS = {
    "FR_Cig": "Tabaquismo", "FR_Hiper": "Hipertensión arterial", "FR_Diab": "Diabetes",
    "FR_Obeso": "Obesidad", "FR_Dislipemia": "Dislipemia", "FR_AVE": "ACV previo",
    "FR_Eceva": "Enfermedad cerebrovascular", "FR_EPOC": "EPOC",
    "FR_FallaRen": "Falla renal", "FR_IRC": "Insuficiencia renal crónica",
    "FR_AF": "Antecedentes familiares", "FR_Apnea": "Apnea del sueño",
    "SC_IAM": "IAM", "SC_Shock": "Shock", "SC_BIAC": "Balón de contrapulsación",
    "SC_Arritmia": "Arritmia", "SC_Angina": "Angina", "SC_Trombo": "Trombólisis",
    "SC_MP": "Marcapasos", "SC_Tapon": "Taponamiento cardíaco",
    "SC_Cardia": "Situación cardíaca crítica",
    "Procedimiento_ByPass": "Bypass coronario (CRM)",
    "Procedimiento_Aortico": "Cirugía de válvula aórtica",
    "Procedimiento_Mitral": "Cirugía de válvula mitral",
    "Procedimiento_Tricuspide": "Cirugía de válvula tricúspide",
    "Procedimiento_Combinado": "Cirugía combinada",
    "IP_CCprevio": "Cirugía cardíaca previa (reintervención)",
    "CCHemo_EnfermedadAO": "Enfermedad aórtica", "CCHemo_EnfermedadMI": "Enfermedad mitral",
    "DatosCC_CondicionesIAM": "IAM reciente",
}

_CLASE_OPTIONS = [{"value": str(i), "label": f"Clase {i}"} for i in (1, 2, 3, 4)]
_PRIORIDAD_OPTIONS = [
    {"value": "109", "label": "Electiva / coordinada (109)"},
    {"value": "105", "label": "Prioritaria (105)"},
    {"value": "120", "label": "Urgente (120)"},
    {"value": "106", "label": "Emergencia (106)"},
    {"value": "-1", "label": "Otro"},
]

# El EuroSCORE (score internacional de riesgo quirúrgico) vive en
# `flow_procedimientocardiologiablockdetalle.Euroscore`, enlazado por CodMaster.
# El INCC lo registra desde 2021 (cobertura ~90%), por eso la cohorte se limita a
# la era moderna: así el modelo puede aprovecharlo. Es un campo opcional en la UI.
_EURO_DET = "flow_procedimientocardiologiablockdetalle"

SURG_SQL = f"""
SELECT
    s.EdadCoo                AS edad,
    pf.CodSexo               AS sexo,
    s.FR_Crea                AS creatinina,
    s.CCHemo_Eyeccion        AS fe,
    s.DatosCEC_HematocritoPre AS hto_pre,
    s.CCHemo_VasosAfectados  AS vasos,
    s.MP_NYHA                AS nyha,
    s.Anestesia_ClasificacionRiesgo AS asa,
    s.CCHemo_InsuficienciaMI AS insuf_mi,
    s.DatosCC_CodCirugiaClase AS clase_cirugia,
    s.CodCoordinaReglaMotivo AS prioridad,
    e.Euroscore              AS euroscore,
    YEAR(s.FechaRealizado)   AS anio,
    {",".join("s." + c for c in SURG_FLAGS)},
    CASE WHEN sf.Fecha > '1900-01-01'
              AND DATEDIFF(sf.Fecha, s.FechaRealizado) BETWEEN 0 AND 30
         THEN 1 ELSE 0 END   AS fallecio
FROM sqlpvd_all s
LEFT JOIN pac_ficha pf        ON pf.Cod = s.CodPac
LEFT JOIN sqlsalud_fallece sf ON sf.NroHistoria = s.CodPac
LEFT JOIN (
    SELECT CodMaster, MAX(Euroscore) AS Euroscore
    FROM {_EURO_DET} GROUP BY CodMaster
) e ON e.CodMaster = s.CodMaster
WHERE s.FechaRealizado > '1900-01-01'
  AND YEAR(s.FechaRealizado) >= 2021
"""


def _clean_surgery_base(df: pd.DataFrame) -> pd.DataFrame:
    """Limpieza común de cirugía SIN el EuroSCORE (features pre-operatorias)."""
    _clean_flags(df, SURG_FLAGS)
    df["edad"] = pd.to_numeric(df["edad"], errors="coerce")
    df.loc[(df["edad"] < 0) | (df["edad"] > 110), "edad"] = np.nan
    df["creatinina"] = pd.to_numeric(df["creatinina"], errors="coerce")
    df.loc[(df["creatinina"] <= 0) | (df["creatinina"] > 20), "creatinina"] = np.nan
    df["fe"] = pd.to_numeric(df["fe"], errors="coerce")
    df.loc[(df["fe"] <= 5) | (df["fe"] > 90), "fe"] = np.nan
    df["hto_pre"] = pd.to_numeric(df["hto_pre"], errors="coerce")
    df.loc[(df["hto_pre"] <= 10) | (df["hto_pre"] > 60), "hto_pre"] = np.nan
    df["vasos"] = pd.to_numeric(df["vasos"], errors="coerce")
    df.loc[(df["vasos"] < 0) | (df["vasos"] > 5), "vasos"] = np.nan
    df["nyha"] = pd.to_numeric(df["nyha"], errors="coerce")
    df.loc[(df["nyha"] < 1) | (df["nyha"] > 4), "nyha"] = np.nan
    df["asa"] = pd.to_numeric(df["asa"], errors="coerce")
    df.loc[(df["asa"] < 1) | (df["asa"] > 6), "asa"] = np.nan
    df["insuf_mi"] = pd.to_numeric(df["insuf_mi"], errors="coerce")
    df.loc[(df["insuf_mi"] < 0) | (df["insuf_mi"] > 4), "insuf_mi"] = np.nan
    df["sexo"] = _as_category(df["sexo"], na_values=(0,))
    df["clase_cirugia"] = _as_category(df["clase_cirugia"], na_values=(0,))
    # Prioridad: los motivos conocidos + "otro" (-1) para el resto.
    prio = pd.to_numeric(df["prioridad"], errors="coerce")
    known = [109, 105, 120, 106]
    df["prioridad"] = _as_category(prio.where(prio.isin(known), other=-1))
    return df


def _clean_surgery(df: pd.DataFrame) -> pd.DataFrame:
    df = _clean_surgery_base(df)
    df["euroscore"] = pd.to_numeric(df["euroscore"], errors="coerce")
    # 0 = no registrado (nulo lógico); rango válido del EuroSCORE (logístico %) 0–100.
    df.loc[(df["euroscore"] <= 0) | (df["euroscore"] > 100), "euroscore"] = np.nan
    return df


_EURO_FIELD = Field(
    "euroscore", "number", "EuroSCORE II", group="Evaluación",
    unit="%", min=0, max=100, step=0.1,
    help="Score internacional de riesgo quirúrgico. Opcional: dejar vacío si no se calculó.",
)


def _surgery_fields_base() -> list[Field]:
    fields = [
        Field("edad", "number", "Edad", group="Demografía", unit="años", min=0, max=110, step=1),
        Field("sexo", "select", "Sexo", group="Demografía", options=_SEXO_OPTIONS),
        Field("creatinina", "number", "Creatinina", group="Laboratorio", unit="mg/dL", min=0.1, max=20, step=0.1),
        Field("hto_pre", "number", "Hematocrito preoperatorio", group="Laboratorio", unit="%", min=10, max=60, step=1),
        Field("fe", "number", "Fracción de eyección", group="Función cardíaca", unit="%", min=5, max=90, step=1),
        Field("vasos", "number", "Vasos coronarios afectados", group="Función cardíaca", min=0, max=5, step=1),
        Field("nyha", "number", "Clase funcional (NYHA)", group="Función cardíaca", min=1, max=4, step=1),
        Field("insuf_mi", "number", "Insuficiencia mitral (grado)", group="Función cardíaca", min=0, max=4, step=1),
        Field("asa", "number", "Clasificación de riesgo (ASA)", group="Evaluación", min=1, max=6, step=1),
        Field("clase_cirugia", "select", "Clase de cirugía", group="Procedimiento", options=_CLASE_OPTIONS),
        Field("prioridad", "select", "Prioridad / urgencia", group="Procedimiento", options=_PRIORIDAD_OPTIONS),
    ]
    for k in SURG_PROC:
        fields.append(Field(k, "bool", _SURG_LABELS[k], group="Procedimiento"))
    for k in SURG_FR:
        fields.append(Field(k, "bool", _SURG_LABELS[k], group="Factores de riesgo"))
    for k in SURG_SC:
        fields.append(Field(k, "bool", _SURG_LABELS[k], group="Situación clínica"))
    return fields


def _surgery_fields() -> list[Field]:
    return [_EURO_FIELD, *_surgery_fields_base()]


SURGERY_SPEC = CohortSpec(
    name="surgery",
    title="Mortalidad quirúrgica (30 días)",
    description=(
        "Estima la probabilidad de mortalidad a 30 días de una cirugía cardíaca a "
        "partir del EuroSCORE (opcional), comorbilidades, función cardíaca y tipo de "
        "procedimiento."
    ),
    sql=SURG_SQL,
    numeric=["euroscore", "edad", "creatinina", "fe", "hto_pre", "vasos", "nyha", "asa", "insuf_mi"],
    categorical=["sexo", "clase_cirugia", "prioridad"],
    binary=SURG_FLAGS,
    clean_common=_clean_surgery,
    fields=_surgery_fields(),
    min_year=2021,
    outcome="mortalidad",
    target_desc="mortalidad a 30 días",
)


# --------------------------------------------------------------------------- #
# Complicaciones graves de cirugía cardíaca (intrahospitalarias)
# --------------------------------------------------------------------------- #
# Target compuesto: falla renal, hemodiálisis, sangrado quirúrgico, resutura o
# dehiscencia (flags 255). Registrado 2008–2022 (desde 2023 no se carga), por eso
# el cohorte se acota a esa ventana. Predicho SOLO con variables pre-operatorias.
_COMPLIC_FLAGS = [
    "ComplicacionesIntraHospitalaria_FallaRenal",
    "ComplicacionesIntraHospitalaria_Hemodialisis",
    "ComplicacionesIntraHospitalaria_OperatoriaSangradoQuirurgico",
    "ComplicacionesIntraHospitalaria_OperatoriaResutura",
    "ComplicacionesIntraHospitalaria_OperatoriaDehiscencia",
]
_COMPLIC_TARGET = " OR ".join(f"s.{c} = 255" for c in _COMPLIC_FLAGS)

SURG_COMPLIC_SQL = f"""
SELECT
    s.EdadCoo                AS edad,
    pf.CodSexo               AS sexo,
    s.FR_Crea                AS creatinina,
    s.CCHemo_Eyeccion        AS fe,
    s.DatosCEC_HematocritoPre AS hto_pre,
    s.CCHemo_VasosAfectados  AS vasos,
    s.MP_NYHA                AS nyha,
    s.Anestesia_ClasificacionRiesgo AS asa,
    s.CCHemo_InsuficienciaMI AS insuf_mi,
    s.DatosCC_CodCirugiaClase AS clase_cirugia,
    s.CodCoordinaReglaMotivo AS prioridad,
    YEAR(s.FechaRealizado)   AS anio,
    {",".join("s." + c for c in SURG_FLAGS)},
    CASE WHEN {_COMPLIC_TARGET} THEN 1 ELSE 0 END AS complica
FROM sqlpvd_all s
LEFT JOIN pac_ficha pf ON pf.Cod = s.CodPac
WHERE s.FechaRealizado > '1900-01-01'
  AND YEAR(s.FechaRealizado) BETWEEN 2008 AND 2022
"""


SURGERY_COMPLICATIONS_SPEC = CohortSpec(
    name="surgery_complications",
    title="Complicaciones graves de cirugía",
    description=(
        "Estima la probabilidad de una complicación grave intrahospitalaria (falla "
        "renal, hemodiálisis, sangrado quirúrgico, resutura o dehiscencia) en una "
        "cirugía cardíaca, a partir de comorbilidades, función cardíaca y tipo de "
        "procedimiento."
    ),
    sql=SURG_COMPLIC_SQL,
    numeric=["edad", "creatinina", "fe", "hto_pre", "vasos", "nyha", "asa", "insuf_mi"],
    categorical=["sexo", "clase_cirugia", "prioridad"],
    binary=SURG_FLAGS,
    clean_common=_clean_surgery_base,
    fields=_surgery_fields_base(),
    min_year=2008,
    target_col="complica",
    outcome="complicaciones graves",
    target_desc="complicaciones graves intrahospitalarias",
)


SPECS: dict[str, CohortSpec] = {
    PTCA_SPEC.name: PTCA_SPEC,
    SURGERY_SPEC.name: SURGERY_SPEC,
    SURGERY_COMPLICATIONS_SPEC.name: SURGERY_COMPLICATIONS_SPEC,
}


def get_spec(name: str) -> CohortSpec:
    if name not in SPECS:
        raise KeyError(f"Cohorte desconocida: {name!r}. Disponibles: {list(SPECS)}")
    return SPECS[name]
