from pydantic import BaseModel, Field


class ModelCard(BaseModel):
    id: str = Field(min_length=1)
    name: str | None = None


class ModelListResponse(BaseModel):
    models: list[str]
    cards: list[ModelCard] | None = None
