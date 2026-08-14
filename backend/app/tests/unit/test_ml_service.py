"""Serving ML: carga de artefactos, predicción y niveles de riesgo."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ml.specs import get_spec
from app.services import ml_service as ml_service_module
from app.services.ml_service import MLService, ModelNotAvailableError, _get_model
from app.tests.helpers.ml_artifacts import write_ptca_artifacts


@pytest.fixture
def ptca_models_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    models_dir = tmp_path / "models"
    write_ptca_artifacts(models_dir)
    monkeypatch.setattr(ml_service_module, "MODELS_DIR", models_dir)
    _get_model.cache_clear()
    yield models_dir
    _get_model.cache_clear()


def test_list_models_marks_availability(ptca_models_dir: Path) -> None:
    models = MLService().list_models()
    by_cohort = {m["cohort"]: m for m in models}
    assert by_cohort["ptca"]["available"] is True
    assert by_cohort["ptca"]["version"] == "test-v1"
    assert by_cohort["surgery"]["available"] is False
    assert by_cohort["surgery"]["features"]
    assert by_cohort["surgery_complications"]["available"] is False


def test_get_model_meta(ptca_models_dir: Path) -> None:
    meta = MLService().get_model_meta("ptca")
    assert meta["cohort"] == "ptca"
    assert meta["youden_threshold"] == 0.2


def test_get_model_meta_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ml_service_module, "MODELS_DIR", tmp_path / "empty")
    _get_model.cache_clear()
    with pytest.raises(ModelNotAvailableError, match="no está entrenado"):
        MLService().get_model_meta("ptca")
    _get_model.cache_clear()


def test_get_model_unknown_cohort(ptca_models_dir: Path) -> None:
    with pytest.raises(KeyError, match="desconocida"):
        MLService().get_model_meta("nope")


def test_predict_ptca_happy_path(ptca_models_dir: Path) -> None:
    values = {
        "edad": 72,
        "sexo": "1",
        "FRhipertension": True,
        "FRdiabetes": True,
        "CEiamCurso": True,
    }
    result = MLService().predict("ptca", values)
    assert result["cohort"] == "ptca"
    assert 0.0 <= result["probability"] <= 1.0
    assert result["risk_level"] in {"bajo", "moderado", "alto"}
    assert result["model_version"] == "test-v1"
    assert isinstance(result["contributing_factors"], list)
    assert isinstance(result["explanation"], list)
    assert result["risk_ratio"] is not None


def test_predict_risk_levels(ptca_models_dir: Path) -> None:
    model = _get_model("ptca")
    assert model._risk_level(0.9) == "alto"
    assert model._risk_level(0.1) == "moderado"  # >= base_rate 0.05
    assert model._risk_level(0.01) == "bajo"


def test_predict_without_interp_skips_explanation(
    ptca_models_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = _get_model("ptca")
    monkeypatch.setattr(model, "interp", None)
    result = model.predict({"edad": 60, "sexo": "2"})
    assert result["explanation"] == []


def test_parse_feature_branches(ptca_models_dir: Path) -> None:
    model = _get_model("ptca")
    values = {"edad": 70, "sexo": "1", "FRhipertension": True}
    assert model._parse_feature("num__edad", 1.0, values) is not None
    assert model._parse_feature("num__edad", 1.0, {"edad": None}) is None
    assert model._parse_feature("bin__FRhipertension", 1.0, values) is not None
    assert model._parse_feature("bin__FRhipertension", 1.0, {"FRhipertension": False}) is None
    assert model._parse_feature("cat__sexo_1", 1.0, values) is not None
    assert model._parse_feature("cat__sexo_1", 0.0, values) is None
    assert model._parse_feature("cat__sexo_1", 1.0, {"sexo": None}) is None
    assert model._parse_feature("cat__desconocido_x", 1.0, values) is None
    assert model._parse_feature("other__", 1.0, values) is None


def test_build_frame_kinds(ptca_models_dir: Path) -> None:
    model = _get_model("ptca")
    df = model._build_frame({"edad": "", "sexo": "", "FRhipertension": False})
    assert "edad" in df.columns
    cleaned = get_spec("ptca").clean_common
    assert callable(cleaned)


def test_explain_handles_sparse_matrix(
    ptca_models_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cubre el branch `toarray()` cuando el preprocesador devuelve sparse."""
    import numpy as np

    model = _get_model("ptca")
    pre = model.interp.named_steps["pre"]
    lr = model.interp.named_steps["lr"]
    n = len(lr.coef_[0])

    class _Sparse:
        def toarray(self):
            return np.ones((1, n), dtype=float)

    monkeypatch.setattr(pre, "transform", lambda X: _Sparse())
    monkeypatch.setattr(
        pre,
        "get_feature_names_out",
        lambda: np.array([f"num__edad" if i == 0 else f"bin__FRhipertension" for i in range(n)]),
    )
    model.metadata["feature_means"] = [0.0] * n
    items = model.explain({"edad": 70, "sexo": "1", "FRhipertension": True}, top=3)
    assert isinstance(items, list)
    assert items  # al menos edad / hipertensión aportan
