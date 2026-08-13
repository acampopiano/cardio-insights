"""Artefactos ML mínimos para tests de serving (sin BD ni entrenamiento real)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.ml.specs import PTCA_SPEC, CohortSpec


def _build_pipeline(spec: CohortSpec) -> Pipeline:
    pre = ColumnTransformer(
        [
            (
                "num",
                Pipeline(
                    [
                        ("imp", SimpleImputer(strategy="median")),
                        ("sc", StandardScaler()),
                    ]
                ),
                spec.numeric,
            ),
            (
                "cat",
                Pipeline(
                    [
                        ("imp", SimpleImputer(strategy="most_frequent")),
                        ("oh", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                spec.categorical,
            ),
            ("bin", SimpleImputer(strategy="constant", fill_value=0), spec.binary),
        ]
    )
    return Pipeline(
        [
            ("pre", pre),
            ("lr", LogisticRegression(class_weight="balanced", max_iter=500)),
        ]
    )


def _synthetic_frame(spec: CohortSpec, n: int = 40) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(42)
    data: dict[str, Any] = {
        "edad": rng.integers(40, 85, size=n),
        "sexo": rng.choice([1, 2], size=n),
    }
    for col in spec.binary:
        data[col] = rng.choice([0, 255], size=n, p=[0.7, 0.3])
    y = pd.Series(rng.choice([0, 1], size=n, p=[0.85, 0.15]), name=spec.target_col)
    return pd.DataFrame(data), y


def write_ptca_artifacts(models_dir: Path) -> dict[str, Any]:
    """Entrena un pipeline toy de PTCA y lo serializa como en producción."""
    models_dir.mkdir(parents=True, exist_ok=True)
    spec = PTCA_SPEC
    raw, y = _synthetic_frame(spec)
    X = spec.clean_common(raw)[spec.features]

    pipeline = _build_pipeline(spec)
    pipeline.fit(X, y)
    interp = _build_pipeline(spec)
    interp.fit(X, y)

    Xt = interp.named_steps["pre"].transform(X)
    if hasattr(Xt, "toarray"):
        Xt = Xt.toarray()
    feature_means = np.asarray(Xt).mean(axis=0).ravel().tolist()
    names = interp.named_steps["pre"].get_feature_names_out()
    coefs = interp.named_steps["lr"].coef_[0]
    odds_ratios = [
        {"feature": str(name), "odds_ratio": float(np.exp(coef))}
        for name, coef in zip(names, coefs)
        if str(name).startswith("bin__")
    ][:10]

    metadata: dict[str, Any] = {
        "cohort": spec.name,
        "title": spec.title,
        "description": spec.description,
        "version": "test-v1",
        "outcome": spec.outcome,
        "target": spec.target_desc,
        "youden_threshold": 0.2,
        "base_rate": 0.05,
        "feature_means": feature_means,
        "odds_ratios": odds_ratios,
        "features": [f.to_dict() for f in spec.fields],
        "metrics": {"auc_roc": 0.75, "youden_threshold": 0.2, "base_rate": 0.05},
    }

    joblib.dump(pipeline, models_dir / f"{spec.name}_mortality.joblib")
    joblib.dump(interp, models_dir / f"{spec.name}_mortality_interp.joblib")
    (models_dir / f"{spec.name}_mortality.json").write_text(
        json.dumps(metadata, ensure_ascii=False),
        encoding="utf-8",
    )
    return metadata
