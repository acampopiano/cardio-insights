from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Respuesta estandar del endpoint de salud del servicio."""

    status: str
    service: str
    version: str
    environment: str
