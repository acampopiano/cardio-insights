"""CLI para entrenar los modelos de mortalidad (offline, contra la BD real).

Uso:
    python -m scripts.train_ml_models              # entrena todos
    python -m scripts.train_ml_models ptca surgery # cohortes específicas

Requiere las credenciales de la BD en variables de entorno (o usa los defaults
de producción definidos en app.ml.training):
    INCC_MYSQL_HOST, INCC_MYSQL_PORT, INCC_MYSQL_USER, INCC_MYSQL_PASSWORD, INCC_MYSQL_DB
"""

import sys

from app.ml.training import train_all

if __name__ == "__main__":
    cohorts = sys.argv[1:] or None
    train_all(cohorts)
