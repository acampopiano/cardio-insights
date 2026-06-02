from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas.natural_query import NaturalQueryGatewayResponse


class LLMGatewayClient:
    """Cliente HTTP para interpretar consultas naturales via LLM Gateway."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def is_enabled(self) -> bool:
        return bool(self._settings.llm_gateway_enabled)

    def interpret(self, question: str, use_llm_fallback: bool = True) -> tuple[NaturalQueryGatewayResponse | None, str | None]:
        """Retorna (respuesta, error). Nunca levanta excepciones de red al caller."""
        if not self.is_enabled():
            return None, "LLM Gateway deshabilitado por configuracion."

        base_url = str(self._settings.llm_gateway_url or "").strip().rstrip("/")
        if not base_url:
            return None, "LLM Gateway habilitado pero sin LLM_GATEWAY_URL configurada."

        final_url = f"{base_url}/llm/nl2kpi/interpret"
        timeout = float(self._settings.llm_gateway_timeout_seconds or 8.0)

        try:
            response = httpx.post(
                final_url,
                json={"question": question, "use_llm_fallback": use_llm_fallback},
                timeout=timeout,
            )
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                return None, "Respuesta invalida del LLM Gateway (JSON no es objeto)."
            return NaturalQueryGatewayResponse(**body), None
        except httpx.TimeoutException:
            return None, f"Timeout consultando LLM Gateway ({timeout}s)."
        except httpx.RequestError as exc:
            return None, f"No se pudo conectar al LLM Gateway: {exc}"
        except httpx.HTTPStatusError as exc:
            return None, f"LLM Gateway respondio HTTP {exc.response.status_code}."
        except ValueError:
            return None, "LLM Gateway devolvio JSON invalido."
        except Exception as exc:  # pragma: no cover - fallback defensivo
            return None, f"Error inesperado consultando LLM Gateway: {exc}"


__all__ = ["LLMGatewayClient"]
