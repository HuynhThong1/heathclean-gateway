"""Open Food Facts full-text source for packaged foods.

Search-a-licious supplies candidates, but this adapter accepts only an exact
normalised product-name match. Open Food Facts is community data, so every
record carries a link back to the product rather than hiding its provenance.
"""

import os
from typing import Optional, Tuple

import httpx

from .base import NutritionRecord, NutritionSource, NutritionSourceError, same_food_name


class OpenFoodFactsSource(NutritionSource):
    name = "openfoodfacts"

    def __init__(
        self,
        user_agent: Optional[str] = None,
        search_url: Optional[str] = None,
        timeout: Optional[float] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self._user_agent = (
            user_agent if user_agent is not None else os.getenv("OPENFOODFACTS_USER_AGENT", "")
        )
        self._search_url = search_url or os.getenv(
            "OPENFOODFACTS_SEARCH_URL", "https://search.openfoodfacts.org/search"
        )
        self._timeout = timeout or float(os.getenv("NUTRITION_TIMEOUT_SECONDS", "8"))
        self._transport = transport

    @property
    def is_configured(self) -> bool:
        # Open Food Facts requires an identifying User-Agent for API clients.
        return bool(self._user_agent)

    def queries(self, name: str, name_en: Optional[str]) -> Tuple[str, ...]:
        return (name_en or name,)

    async def lookup(self, query: str) -> Optional[NutritionRecord]:
        if not self.is_configured:
            return None

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.post(
                    self._search_url,
                    headers={"User-Agent": self._user_agent},
                    json={
                        "q": query,
                        "page_size": 10,
                        "boost_phrase": True,
                        "langs": ["vi", "en"],
                        "fields": ["code", "product_name", "nutriments"],
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise NutritionSourceError(
                "Open Food Facts lookup failed: {}".format(error)
            ) from error

        for product in payload.get("hits", []):
            product_name = product.get("product_name", "")
            if not same_food_name(product_name, query):
                continue
            nutrients = product.get("nutriments") or {}
            values = {
                "calories": nutrients.get("energy-kcal_100g"),
                "protein": nutrients.get("proteins_100g"),
                "carbs": nutrients.get("carbohydrates_100g"),
                "fat": nutrients.get("fat_100g"),
            }
            if not all(isinstance(value, (int, float)) for value in values.values()):
                continue

            code = str(product.get("code", "")) or None
            return NutritionRecord(
                name=product_name,
                name_en=product_name,
                calories_per_100g=float(values["calories"]),
                protein_per_100g=float(values["protein"]),
                carbs_per_100g=float(values["carbs"]),
                fat_per_100g=float(values["fat"]),
                source="open_food_facts",
                source_id=code,
                source_url=(
                    "https://world.openfoodfacts.org/product/{}".format(code)
                    if code
                    else None
                ),
            )
        return None
