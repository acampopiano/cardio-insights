from fastapi import APIRouter, Depends

from app.core.security import get_current_claims
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
def ask_chat(
    payload: ChatRequest,
    _claims: dict = Depends(get_current_claims),
) -> ChatResponse:
    """Responde una pregunta en lenguaje natural sobre los datos clínicos.

    Traduce la pregunta a SQL (solo lectura), la valida, la ejecuta con un
    usuario MySQL de solo lectura y redacta la respuesta.
    """
    service = ChatService()
    return service.ask(payload.question, payload.history)
