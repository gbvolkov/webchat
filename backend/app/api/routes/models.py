from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_chat_service
from app.schemas.model import ModelCard, ModelListResponse
from app.services.llm import LLMServiceError, OpenAIChatService

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=ModelListResponse)
async def list_models(
    chat_service: OpenAIChatService = Depends(get_chat_service),
) -> ModelListResponse:
    try:
        provider_cards = await chat_service.list_models()
    except LLMServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return ModelListResponse(
        models=[card.id for card in provider_cards],
        cards=[ModelCard(id=card.id, name=card.name) for card in provider_cards],
    )
