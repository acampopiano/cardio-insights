from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Cardio Insights API"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    environment: str = Field(default="dev")
    debug: bool = Field(default=True)

    jwt_secret_key: str = Field(default="change-me-in-env")
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=120)

    repository_backend: str = Field(default="mock")
    natural_query_auto_kpi_mode: str = Field(default="human_approve")
    natural_query_auto_kpi_approver_roles: str = Field(default="admin,direccion,direccion_medica,medico_direccion")
    natural_query_learning_file: str = Field(default="data/natural_query_learning.jsonl")
    natural_query_training_export_file: str = Field(default="data/natural_query_training_dataset.jsonl")
    natural_query_auto_feedback_mode: str = Field(default="off")
    natural_query_auto_feedback_min_confidence: float = Field(default=0.8)
    natural_query_online_memory_enabled: bool = Field(default=True)
    natural_query_online_memory_min_score: float = Field(default=0.88)
    dynamic_kpis_file: str = Field(default="shared/dynamic_kpis.json")
    llm_gateway_url: str = Field(default="")
    llm_gateway_enabled: bool = Field(default=False)
    llm_gateway_timeout_seconds: float = Field(default=8.0)

    mysql_host: str = Field(default="localhost")
    mysql_port: int = Field(default=3306)
    mysql_user: str = Field(default="cardio")
    mysql_password: str = Field(default="cardio")
    mysql_database: str = Field(default="incc")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
