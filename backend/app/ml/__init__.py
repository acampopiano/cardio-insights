"""Modelos predictivos (mortalidad PTCA y quirúrgica).

Separación offline/online:
- `specs`: fuente única de verdad (SQL, features, limpieza, campos de UI).
- `training`: entrena y serializa los modelos (se corre offline, contra la BD).
- El serving vive en `app.services.ml_service` y solo carga los `.joblib`.
"""
