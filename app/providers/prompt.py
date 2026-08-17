"""The recognition prompt and its parser.

Shared by every hosted provider so the contract asked of each model is
identical — otherwise comparing two models would also be comparing two prompts.
Adapted from plan.md §8.

**The granularity of the naming is load-bearing.** `vietnamese_foods` is keyed
on whole dishes, and `lookup` is exact-match on purpose, so a model that
decomposes a bowl of phở into noodles, broth and beef resolves *nothing* — every
item comes back with zero nutrition even though "Phở bò" is right there in the
table. Asking for menu-level names is what keeps recognition and nutrition at
the same level of detail, which is also what plan.md §2 divides between them:
the model says which dish, the database says what it is worth.
"""

import json
from typing import List

from .base import ProviderError, RecognizedFood

RECOGNITION_PROMPT = """Analyze this meal image.

Name each dish the way a Vietnamese menu would list it — the dish as served,
not the ingredients it is made from.

A bowl of phở is ONE item, "Phở bò". It is not rice noodles plus broth plus
beef plus herbs. A cơm tấm plate is SEVERAL items — "Cơm tấm", "Sườn nướng",
"Trứng ốp la" — because a menu lists those separately.

Use the dish's common base name and leave preparation variants out of it:
"Phở bò", not "Phở bò tái chín"; "Cơm gà", not "Cơm gà xối mỡ".

"name" MUST be the Vietnamese name when the dish has one — "Mì cay", not
"Spicy Noodle Soup". Put the English in "nameEn". A Vietnamese dish returned
under an English name does not resolve, and a generic English name can match an
unrelated packaged product.

Estimate the portion size of each dish in grams when reasonably possible.

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
