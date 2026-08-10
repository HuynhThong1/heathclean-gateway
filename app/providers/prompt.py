"""The recognition prompt and its parser.

Shared by every hosted provider so the contract asked of each model is
identical — otherwise comparing two models would also be comparing two prompts.
Adapted from plan.md §8.
"""

import json
from typing import List

from .base import ProviderError, RecognizedFood

RECOGNITION_PROMPT = """Analyze this meal image.

Identify every visible food item. Vietnamese dishes should be named in
Vietnamese, with an English name alongside.

Estimate portion size in grams when reasonably possible.

Do NOT calculate calories.

Return ONLY valid JSON matching:

{
  "foods": [
    {
      "name": "",
      "nameEn": "",
      "estimatedWeightGrams": 0,
      "confidence": 0.0
    }
  ]
}
"""


def parse_recognition_json(text: str) -> List[RecognizedFood]:
    """Turn a model's JSON reply into foods.

    Tolerates a ```json fence, which models add despite being asked not to.
    Rejects anything else loudly: a silently mis-parsed reply would become
    silently wrong calories.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise ProviderError("Model did not return JSON: {}".format(error))

    foods = payload.get("foods")
    if not isinstance(foods, list):
        raise ProviderError("Model JSON has no 'foods' array")

    results: List[RecognizedFood] = []
    for entry in foods:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        if not name:
            continue
        try:
            grams = float(entry.get("estimatedWeightGrams") or 0)
            confidence = float(entry.get("confidence") or 0)
        except (TypeError, ValueError):
            continue
        name_en = entry.get("nameEn")
        results.append(
            RecognizedFood(
                name=name,
                name_en=str(name_en).strip() if name_en else None,
                estimated_weight_grams=max(grams, 0.0),
                # Models occasionally emit percentages; fold those back to 0…1.
                confidence=min(max(confidence / 100 if confidence > 1 else confidence, 0.0), 1.0),
            )
        )
    return results
