"""Serving de los modelos de mortalidad.

NO toca la base de datos: solo carga los artefactos `.joblib` + `.json` que dejó
el entrenamiento offline (`app.ml.training`) y calcula la probabilidad para un
caso puntual enviado por la API.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.ml.specs import SPECS, get_spec
from app.ml.training import MODELS_DIR


class ModelNotAvailableError(RuntimeError):
    """El modelo no fue entrenado todavía (faltan los artefactos en disco)."""


class _LoadedModel:
    def __init__(self, cohort: str) -> None:
        import joblib  # import perezoso: solo si se usa el serving

        self.spec = get_spec(cohort)
        model_path = MODELS_DIR / f"{cohort}_mortality.joblib"
        meta_path = MODELS_DIR / f"{cohort}_mortality.json"
        if not model_path.exists() or not meta_path.exists():
            raise ModelNotAvailableError(
                f"El modelo '{cohort}' no está entrenado. Corré "
                f"`python -m scripts.train_ml_models {cohort}` primero."
            )
        self.pipeline = joblib.load(model_path)
        interp_path = MODELS_DIR / f"{cohort}_mortality_interp.joblib"
        self.interp = joblib.load(interp_path) if interp_path.exists() else None
        self.metadata: dict[str, Any] = json.loads(Path(meta_path).read_text(encoding="utf-8"))
        self.threshold: float = float(self.metadata.get("youden_threshold", 0.5))
        self.base_rate: float = float(self.metadata.get("base_rate", 0.0))
        self._fields = {f["key"]: f for f in self.metadata.get("features", [])}
        self._labels = {k: f["label"] for k, f in self._fields.items()}
        self._or_by_feat = {o["feature"]: o["odds_ratio"] for o in self.metadata.get("odds_ratios", [])}
        self._option_labels: dict[str, dict[str, str]] = {
            k: {o["value"]: o["label"] for o in f.get("options", [])}
            for k, f in self._fields.items() if f.get("kind") == "select"
        }

    def _risk_level(self, proba: float) -> str:
        if proba >= self.threshold:
            return "alto"
        if proba >= self.base_rate:
            return "moderado"
        return "bajo"

    def _contributing_factors(self, values: dict[str, Any]) -> list[dict[str, Any]]:
        """Factores de riesgo presentes en el caso con odds ratio > 1 (explicación)."""
        out = []
        for key in self.spec.binary:
            if not values.get(key):
                continue
            odds = self._or_by_feat.get(f"bin__{key}")
            if odds and odds > 1:
                out.append({"factor": self._labels.get(key, key), "odds_ratio": odds})
        out.sort(key=lambda d: d["odds_ratio"], reverse=True)
        return out[:6]

    def _build_frame(self, values: dict[str, Any]) -> pd.DataFrame:
        row: dict[str, Any] = {}
        for f in self.spec.fields:
            v = values.get(f.key)
            if f.kind == "bool":
                row[f.key] = 255 if bool(v) else 0
            elif f.kind == "number":
                row[f.key] = float(v) if v is not None and v != "" else None
            else:  # select
                row[f.key] = v if v not in (None, "") else None
        return self.spec.clean_common(pd.DataFrame([row]))

    def _parse_feature(self, name: str, active: float, values: dict[str, Any]) -> str | None:
        """Traduce el nombre de la feature transformada a una etiqueta legible.
        Devuelve None para las que no aportan al caso (flags ausentes, categorías
        no seleccionadas)."""
        if name.startswith("num__"):
            key = name[5:]
            raw = values.get(key)
            if raw in (None, ""):  # no cargada -> imputada: no es un factor del caso
                return None
            return f"{self._labels.get(key, key)} ({raw})"
        if name.startswith("bin__"):
            key = name[5:]
            return self._labels.get(key, key) if values.get(key) else None
        if name.startswith("cat__"):
            if active != 1:
                return None
            rest = name[5:]
            for key in self.spec.categorical:
                if rest.startswith(f"{key}_"):
                    if values.get(key) in (None, ""):  # imputada
                        return None
                    val = rest[len(key) + 1:]
                    opt = self._option_labels.get(key, {}).get(val, val)
                    return f"{self._labels.get(key, key)}: {opt}"
            return None
        return None

    def explain(self, values: dict[str, Any], top: int = 8) -> list[dict[str, Any]]:
        """Contribución de cada variable a la predicción (log-odds, exacta para el
        modelo lineal): contribución_i = coef_i * (x_i - media_i)."""
        if self.interp is None:
            return []
        pre = self.interp.named_steps["pre"]
        lr = self.interp.named_steps["lr"]
        df = self._build_frame(values)
        xt = pre.transform(df[self.spec.features])
        if hasattr(xt, "toarray"):
            xt = xt.toarray()
        xt = np.asarray(xt)[0]
        names = pre.get_feature_names_out()
        coef = lr.coef_[0]
        means = np.asarray(self.metadata.get("feature_means") or [0.0] * len(coef))
        contrib = coef * (xt - means)

        items = []
        for name, c, x in zip(names, contrib, xt):
            label = self._parse_feature(name, x, values)
            if label is None or abs(c) < 1e-6:
                continue
            items.append({
                "label": label,
                "effect": round(float(c), 4),
                "direction": "up" if c > 0 else "down",
            })
        items.sort(key=lambda d: abs(d["effect"]), reverse=True)
        return items[:top]

    def predict(self, values: dict[str, Any]) -> dict[str, Any]:
        df = self._build_frame(values)
        proba = float(self.pipeline.predict_proba(df[self.spec.features])[:, 1][0])
        return {
            "cohort": self.spec.name,
            "probability": round(proba, 4),
            "probability_pct": round(proba * 100, 2),
            "risk_level": self._risk_level(proba),
            "threshold": round(self.threshold, 4),
            "base_rate": round(self.base_rate, 4),
            "risk_ratio": round(proba / self.base_rate, 1) if self.base_rate > 0 else None,
            "contributing_factors": self._contributing_factors(values),
            "explanation": self.explain(values),
            "model_version": self.metadata.get("version"),
        }


@lru_cache(maxsize=None)
def _get_model(cohort: str) -> _LoadedModel:
    return _LoadedModel(cohort)


class MLService:
    """Fachada del serving usada por los endpoints."""

    def list_models(self) -> list[dict[str, Any]]:
        """Metadatos + campos de cada modelo (para el catálogo y los formularios)."""
        out = []
        for cohort in SPECS:
            try:
                m = _get_model(cohort).metadata
                out.append({**m, "available": True})
            except ModelNotAvailableError:
                spec = get_spec(cohort)
                out.append({
                    "cohort": spec.name,
                    "title": spec.title,
                    "description": spec.description,
                    "available": False,
                    "features": [f.to_dict() for f in spec.fields],
                })
        return out

    def get_model_meta(self, cohort: str) -> dict[str, Any]:
        return _get_model(cohort).metadata

    def predict(self, cohort: str, values: dict[str, Any]) -> dict[str, Any]:
        return _get_model(cohort).predict(values)
