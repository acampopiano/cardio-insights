"""Entrenamiento offline de los modelos de mortalidad.

Se corre a mano contra la base real (no en runtime del API):

    python -m scripts.train_ml_models            # entrena ambos
    python -m scripts.train_ml_models ptca        # solo uno

Produce, en `backend/models/`:
    <cohorte>_mortality.joblib   -> pipeline sklearn (preproc + logística)
    <cohorte>_mortality.json     -> métricas, umbral, vocabularios y campos de UI

Métrica reportada = validación TEMPORAL (train en años previos, test en los
recientes). El modelo serializado se reentrena con TODOS los datos.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import pymysql
from pymysql.cursors import DictCursor
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score, brier_score_loss, roc_auc_score, roc_curve,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score

from app.ml.specs import SPECS, CohortSpec

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"
MODEL_VERSION = "v1"


def _db_config() -> dict[str, Any]:
    return dict(
        host=os.getenv("INCC_MYSQL_HOST", "190.64.90.170"),
        port=int(os.getenv("INCC_MYSQL_PORT", "8809")),
        user=os.getenv("INCC_MYSQL_USER", "proyecto"),
        password=os.getenv("INCC_MYSQL_PASSWORD", "proyecto"),
        database=os.getenv("INCC_MYSQL_DB", "incc"),
    )


def _read_sql(sql: str) -> pd.DataFrame:
    conn = pymysql.connect(cursorclass=DictCursor, autocommit=True, read_timeout=180, **_db_config())
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return pd.DataFrame(cur.fetchall())
    finally:
        conn.close()


def _build_pipeline(spec: CohortSpec) -> Pipeline:
    pre = ColumnTransformer([
        ("num", Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("sc", StandardScaler()),
        ]), spec.numeric),
        ("cat", Pipeline([
            ("imp", SimpleImputer(strategy="most_frequent")),
            ("oh", OneHotEncoder(handle_unknown="ignore")),
        ]), spec.categorical),
        ("bin", SimpleImputer(strategy="constant", fill_value=0), spec.binary),
    ])
    return Pipeline([
        ("pre", pre),
        ("lr", LogisticRegression(class_weight="balanced", max_iter=2000)),
    ])


def _calibrated(spec: CohortSpec) -> CalibratedClassifierCV:
    """Modelo servido: logística balanceada + calibración (Platt) para que las
    probabilidades reflejen la prevalencia real, no el peso de clases."""
    return CalibratedClassifierCV(_build_pipeline(spec), method="sigmoid", cv=5)


def _categorical_vocab(pipeline: Pipeline, spec: CohortSpec) -> dict[str, list[str]]:
    """Categorías aprendidas por el OneHotEncoder (para validar entradas/UI)."""
    ohe = pipeline.named_steps["pre"].named_transformers_["cat"].named_steps["oh"]
    return {col: [str(v) for v in cats] for col, cats in zip(spec.categorical, ohe.categories_)}


def _roc_points(fpr: np.ndarray, tpr: np.ndarray, n: int = 40) -> dict[str, list[float]]:
    """Curva ROC submuestreada (para dibujarla en el front sin inflar el JSON)."""
    idx = np.unique(np.linspace(0, len(fpr) - 1, num=min(n, len(fpr))).astype(int))
    return {
        "fpr": [round(float(fpr[i]), 4) for i in idx],
        "tpr": [round(float(tpr[i]), 4) for i in idx],
    }


def _odds_ratios(pipeline: Pipeline, top: int = 15) -> list[dict[str, Any]]:
    names = pipeline.named_steps["pre"].get_feature_names_out()
    coefs = pipeline.named_steps["lr"].coef_[0]
    df = pd.DataFrame({"feature": names, "coef": coefs})
    df["odds_ratio"] = np.exp(df["coef"]).round(3)
    df = df.reindex(df["coef"].abs().sort_values(ascending=False).index).head(top)
    return [{"feature": r.feature, "odds_ratio": float(r.odds_ratio)} for r in df.itertuples()]


def train_cohort(spec: CohortSpec) -> dict[str, Any]:
    print(f"\n=== Entrenando: {spec.name} ({spec.title}) ===")
    df = _read_sql(spec.sql)
    print(f"Filas crudas: {len(df):,}")

    df = spec.clean_common(df)
    df = df[df[spec.year_col] >= spec.min_year].copy()
    n, pos = len(df), int(df[spec.target_col].sum())
    print(f"Dataset final: {n:,} filas | {pos} muertes ({100 * pos / n:.2f}%)")

    X, y = df[spec.features], df[spec.target_col]

    # Validación temporal: últimos años (~25%) a test. El modelo evaluado es el
    # MISMO que se sirve (calibrado), para que el umbral y el Brier sean fieles.
    cutoff = int(df[spec.year_col].quantile(0.75))
    tr, te = df[spec.year_col] < cutoff, df[spec.year_col] >= cutoff
    model = _calibrated(spec)
    model.fit(X[tr], y[tr])
    proba = model.predict_proba(X[te])[:, 1]
    y_te = y[te]

    fpr, tpr, thr = roc_curve(y_te, proba)
    youden = float(thr[np.argmax(tpr - fpr)])
    roc_points = _roc_points(fpr, tpr)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_auc = cross_val_score(_build_pipeline(spec), X[tr], y[tr], cv=cv, scoring="roc_auc")

    metrics = {
        "cutoff_test_year": cutoff,
        "n_train": int(tr.sum()),
        "n_test": int(te.sum()),
        "base_rate": round(float(y_te.mean()), 4),
        "auc_roc": round(float(roc_auc_score(y_te, proba)), 3),
        "auc_pr": round(float(average_precision_score(y_te, proba)), 3),
        "brier": round(float(brier_score_loss(y_te, proba)), 4),
        "cv_auc_roc_mean": round(float(cv_auc.mean()), 3),
        "youden_threshold": round(youden, 4),
        "roc_curve": roc_points,
    }
    print("Métricas (validación temporal):", json.dumps(metrics, ensure_ascii=False))

    # Modelo de producción: calibrado y reentrenado con TODOS los datos.
    prod = _calibrated(spec)
    prod.fit(X, y)
    # Modelo interpretable (coeficientes/odds ratios) sobre todos los datos.
    interp = _build_pipeline(spec)
    interp.fit(X, y)

    # Medias de las features transformadas (baseline del "paciente promedio" para
    # la descomposición por caso: contribución_i = coef_i * (x_i - media_i)).
    Xt = interp.named_steps["pre"].transform(X)
    if hasattr(Xt, "toarray"):
        Xt = Xt.toarray()
    feature_means = np.asarray(Xt).mean(axis=0).ravel().tolist()

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODELS_DIR / f"{spec.name}_mortality.joblib"
    joblib.dump(prod, model_path)
    joblib.dump(interp, MODELS_DIR / f"{spec.name}_mortality_interp.joblib")

    metadata = {
        "cohort": spec.name,
        "title": spec.title,
        "description": spec.description,
        "version": MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "n_samples": n,
        "n_deaths": pos,
        "outcome": spec.outcome,
        "target": spec.target_desc,
        "metrics": metrics,
        "base_rate": round(float(y.mean()), 4),
        "youden_threshold": metrics["youden_threshold"],
        "categorical_vocab": _categorical_vocab(interp, spec),
        "odds_ratios": _odds_ratios(interp),
        "feature_means": feature_means,
        "features": [f.to_dict() for f in spec.fields],
    }
    meta_path = MODELS_DIR / f"{spec.name}_mortality.json"
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Guardado: {model_path.name} + {meta_path.name}")
    return metadata


def train_all(cohorts: list[str] | None = None) -> None:
    names = cohorts or list(SPECS)
    for name in names:
        if name not in SPECS:
            print(f"[!] Cohorte desconocida: {name} (disponibles: {list(SPECS)})")
            continue
        train_cohort(SPECS[name])
