"""HealthClean AI gateway.

Contract: plan.md §25 — POST /v1/meals/analyze takes a meal photo and returns
per-item nutrition plus a total.

The image is held in memory for the duration of the request and never written
to disk (plan.md §20). Nothing about the user is stored here at all.
"""

import os
from typing import List, Optional

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .nutrition.repository import build_repository
from .nutrition.resolver import resolve_with_repository, total
from .providers import registry
from .providers.base import ProviderError

MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", str(8 * 1024 * 1024)))
ALLOWED_MIME = {"image/jpeg", "image/png", "image/heic", "image/heif", "image/webp"}

app = FastAPI(
    title="HealthClean AI gateway",
    version="0.1.0",
    summary="Recognizes foods in a meal photo and resolves their nutrition.",
)
nutrition_repository = build_repository()


class AnalyzedItem(BaseModel):
    name: str
    name_en: Optional[str] = Field(default=None, alias="nameEn")
    weight: float
    calories: float
    protein: float
    carbs: float
    fat: float
    confidence: float
    #: False when the food is not in the nutrition database. The client must ask
    #: the user rather than present zeros as fact.
    resolved: bool
    nutrition_source: Optional[str] = Field(default=None, alias="nutritionSource")
    nutrition_source_id: Optional[str] = Field(default=None, alias="nutritionSourceId")
    nutrition_source_url: Optional[str] = Field(default=None, alias="nutritionSourceURL")
    nutrition_is_reference: bool = Field(default=False, alias="nutritionIsReference")

    model_config = {"populate_by_name": True}


class AnalyzedTotal(BaseModel):
    calories: float
    protein: float
    carbs: float
    fat: float


class AnalyzeResponse(BaseModel):
    items: List[AnalyzedItem]
    total: AnalyzedTotal
    #: Which model produced this, echoed so a result can always be attributed.
    provider: str


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/v1/providers")
async def providers() -> dict:
    """What models exist and which are usable — so the client can show the
    truth rather than offering a provider that has no key."""
    return {"default": registry.DEFAULT_PROVIDER, "providers": registry.available()}


@app.get("/v1/nutrition/sources")
async def nutrition_sources() -> dict:
    """Configured lookup order and whether each source has its credentials."""
    return {"sources": nutrition_repository.status()}


@app.post("/v1/meals/analyze", response_model=AnalyzeResponse)
async def analyze_meal(
    image: UploadFile = File(...),
    x_model_provider: Optional[str] = Header(default=None, alias="X-Model-Provider"),
) -> AnalyzeResponse:
    try:
        provider = registry.get(x_model_provider)
    except registry.UnknownProviderError:
        raise HTTPException(
            status_code=400,
            detail="Unknown model provider '{}'. Known: {}".format(
                x_model_provider,
                ", ".join(entry["name"] for entry in registry.available()),
            ),
        )

    mime = (image.content_type or "").lower()
    if mime not in ALLOWED_MIME:
        raise HTTPException(
            status_code=415, detail="Unsupported image type '{}'".format(mime)
        )

    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty image")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Image exceeds {} bytes".format(MAX_IMAGE_BYTES),
        )

    try:
        foods = await provider.recognize(data, mime)
    except ProviderError as error:
        # 502: the gateway is fine, the model behind it is not. The client
        # distinguishes this from a bad request so it can offer a retry.
        raise HTTPException(status_code=502, detail=str(error))

    items = await resolve_with_repository(foods, nutrition_repository)
    totals = total(items)

    return AnalyzeResponse(
        items=[
            AnalyzedItem(
                name=item.name,
                nameEn=item.name_en,
                weight=item.weight_grams,
                calories=item.calories,
                protein=item.protein,
                carbs=item.carbs,
                fat=item.fat,
                confidence=item.confidence,
                resolved=item.resolved,
                nutritionSource=item.nutrition_source,
                nutritionSourceId=item.nutrition_source_id,
                nutritionSourceURL=item.nutrition_source_url,
                nutritionIsReference=item.nutrition_is_reference,
            )
            for item in items
        ],
        total=AnalyzedTotal(
            calories=totals.calories,
            protein=totals.protein,
            carbs=totals.carbs,
            fat=totals.fat,
        ),
        provider=provider.name,
    )
