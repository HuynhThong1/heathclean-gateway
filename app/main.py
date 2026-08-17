"""HealthClean AI gateway.

Contract: plan.md §25 — POST /v1/meals/analyze takes a meal photo and returns
per-item nutrition plus a total.

The image is held in memory for the duration of the request and never written
to disk (plan.md §20). Nothing about the user is stored here at all.
"""

import os
import secrets
from typing import List, Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .logging_config import configure_logging
from .nutrition.repository import build_repository
from .nutrition.resolver import resolve_with_repository, total
from .providers import registry
from .providers.base import ProviderError

# Before anything logs. Uvicorn installs its own configuration while building
# its Config and imports this module afterwards, so this replaces it — see
# `configure_logging`.
configure_logging()

MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", str(8 * 1024 * 1024)))
ALLOWED_MIME = {"image/jpeg", "image/png", "image/heic", "image/heif", "image/webp"}


def require_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> None:
    """Guards every `/v1` route with a shared secret.

    An unset `GATEWAY_API_KEY` leaves the gateway open, which is what a local
    run wants and what the suite assumes. That default stops being acceptable
    the moment the port faces the Internet: an analysis costs a call to a hosted
    model on the operator's key, so an unauthenticated endpoint is someone else's
    quota to spend. `docker-compose.yml` therefore requires the variable rather
    than defaulting it.

    `/healthz` stays open on purpose — the container healthcheck and any future
    reverse proxy probe it, and it reveals nothing.

    Unlike provider configuration this is read per request rather than at import
    time. It is one `getenv` against a network call, and it keeps the setting
    testable without reimporting the app.
    """
    expected = os.getenv("GATEWAY_API_KEY", "").strip()
    if not expected:
        return
    # compare_digest rather than ==: the comparison must not leak the key
    # through how long it takes to fail.
    if not secrets.compare_digest(x_api_key or "", expected):
        raise HTTPException(status_code=401, detail="Thiếu hoặc sai API key.")

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


@app.get("/v1/providers", dependencies=[Depends(require_api_key)])
async def providers() -> dict:
    """What models exist and which are usable — so the client can show the
    truth rather than offering a provider that has no key."""
    return {"default": registry.DEFAULT_PROVIDER, "providers": registry.available()}


@app.get("/v1/nutrition/sources", dependencies=[Depends(require_api_key)])
async def nutrition_sources() -> dict:
    """Configured lookup order and whether each source has its credentials."""
    return {"sources": nutrition_repository.status()}


@app.post(
    "/v1/meals/analyze",
    response_model=AnalyzeResponse,
    dependencies=[Depends(require_api_key)],
)
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
