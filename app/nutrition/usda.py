"""USDA FoodData Central nutrition source.

Only Foundation, SR Legacy and Survey (FNDDS) records are queried. Matching is
strict after normalising word order, so a search result that merely resembles
the requested food remains unresolved for the user to review.
"""

import os
from typing import Dict, Optional, Tuple

import httpx

from .base import NutritionRecord, NutritionSource, NutritionSourceError, same_food_name


class USDAFoodDataSource(NutritionSource):
    name = "usda"
    _nutrient_ids = {
        "calories": 1008,
        "protein": 1003,
        "carbs": 1005,
        "fat": 1004,
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else os.getenv("USDA_API_KEY", "")
        self._base_url = (
            base_url or os.getenv("USDA_BASE_URL", "https://api.nal.usda.gov/fdc/v1")
        ).rstrip("/")
        self._timeout = timeout or float(os.getenv("NUTRITION_TIMEOUT_SECONDS", "8"))
        self._transport = transport

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

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
                    "{}/foods/search".format(self._base_url),
                    params={"api_key": self._api_key},
                    json={
                        "query": query,
                        "pageSize": 10,
                        "dataType": ["Foundation", "SR Legacy", "Survey (FNDDS)"],
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise NutritionSourceError("USDA lookup failed: {}".format(error)) from error

        for food in payload.get("foods", []):
            description = food.get("description", "")
            if not same_food_name(description, query):
                continue

            nutrients: Dict[int, float] = {}
            for item in food.get("foodNutrients", []):
                nutrient_id = item.get("nutrientId")
                value = item.get("value")
                if isinstance(nutrient_id, int) and isinstance(value, (int, float)):
                    nutrients[nutrient_id] = float(value)

            required = [nutrients.get(value) for value in self._nutrient_ids.values()]
            if any(value is None for value in required):
                continue

            fdc_id = str(food.get("fdcId", "")) or None
            return NutritionRecord(
                name=description,
                name_en=description,
                calories_per_100g=nutrients[self._nutrient_ids["calories"]],
                protein_per_100g=nutrients[self._nutrient_ids["protein"]],
                carbs_per_100g=nutrients[self._nutrient_ids["carbs"]],
                fat_per_100g=nutrients[self._nutrient_ids["fat"]],
                source="usda_fdc",
                source_id=fdc_id,
                source_url=(
                    "https://fdc.nal.usda.gov/fdc-app.html#/food-details/{}/nutrients".format(
                        fdc_id
                    )
                    if fdc_id
                    else None
                ),
            )
        return None
