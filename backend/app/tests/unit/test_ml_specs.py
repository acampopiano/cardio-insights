"""Contratos de especificaciones ML (limpieza y catálogo)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.ml.specs import SPECS, Field, get_spec


def test_get_spec_known_cohorts() -> None:
    assert set(SPECS) == {"ptca", "surgery", "surgery_complications"}
    for name in SPECS:
        spec = get_spec(name)
        assert spec.name == name
        assert spec.features
        assert spec.fields


def test_get_spec_unknown_raises() -> None:
    with pytest.raises(KeyError, match="desconocida"):
        get_spec("no_existe")


def test_field_to_dict_omits_none() -> None:
    f = Field("edad", "number", "Edad", unit="años", min=0, max=110)
    d = f.to_dict()
    assert d["key"] == "edad"
    assert d["unit"] == "años"
    assert "help" not in d
    assert "options" not in d


def test_field_to_dict_includes_options() -> None:
    f = Field(
        "sexo",
        "select",
        "Sexo",
        options=[{"value": "1", "label": "M"}],
        help="dato demográfico",
    )
    d = f.to_dict()
    assert d["options"] == [{"value": "1", "label": "M"}]
    assert d["help"] == "dato demográfico"


def test_ptca_clean_common_flags_and_edad() -> None:
    spec = get_spec("ptca")
    df = pd.DataFrame(
        {
            "edad": [65, -1, 200],
            "sexo": [1, 0, 2],
            **{flag: [255, 0, 1] for flag in spec.binary},
        }
    )
    cleaned = spec.clean_common(df.copy())
    assert cleaned.loc[0, "FRhipertension"] == 1
    assert cleaned.loc[1, "FRhipertension"] == 0
    assert cleaned.loc[2, "FRhipertension"] == 0
    assert pd.isna(cleaned.loc[1, "edad"])
    assert pd.isna(cleaned.loc[2, "edad"])
    assert cleaned.loc[0, "sexo"] == "1"
    assert cleaned.loc[1, "sexo"] is np.nan or pd.isna(cleaned.loc[1, "sexo"])


def test_surgery_clean_common_basic() -> None:
    spec = get_spec("surgery")
    row = {c: 0 for c in spec.features}
    row.update(
        {
            "edad": 70,
            "sexo": 1,
            "creatinina": 1.1,
            "fe": 55,
            "hto_pre": 40,
            "vasos": 2,
            "nyha": 2,
            "asa": 3,
            "insuf_mi": 0,
            "clase_cirugia": 2,
            "prioridad": 109,
            "euroscore": 5.0,
            "FR_Hiper": 255,
        }
    )
    df = pd.DataFrame([row])
    cleaned = spec.clean_common(df.copy())
    assert cleaned.loc[0, "FR_Hiper"] == 1
    assert cleaned.loc[0, "edad"] == 70
