"""Deterministic provider for development and tests.

Exists so the whole pipeline — upload, resolve, total, and the iOS review
screen — can be exercised without a model, a key, or a network call. It is
deterministic on the image bytes so the same photo always yields the same
plate, which keeps tests meaningful.
"""

import hashlib
from typing import List

from .base import FoodRecognitionProvider, RecognizedFood

#: Plates a Vietnamese user would plausibly photograph. Every name here must
#: exist in the nutrition table, otherwise the resolver falls back to unknown.
_PLATES = [
    [
        ("Cơm trắng", "White rice", 180.0, 0.92),
        ("Sườn nướng", "Grilled pork chop", 120.0, 0.86),
        ("Trứng ốp la", "Fried egg", 55.0, 0.94),
    ],
    [
        ("Phở bò", "Beef pho", 400.0, 0.90),
        ("Rau thơm", "Fresh herbs", 30.0, 0.71),
    ],
    [
        ("Bánh mì thịt", "Banh mi", 180.0, 0.88),
    ],
    [
        ("Bún thịt nướng", "Grilled pork noodles", 350.0, 0.83),
        ("Chả giò", "Spring roll", 60.0, 0.68),
    ],
]


class MockProvider(FoodRecognitionProvider):
    name = "mock"

    async def recognize(self, image_bytes: bytes, mime_type: str) -> List[RecognizedFood]:
        digest = hashlib.sha256(image_bytes).digest()
        plate = _PLATES[digest[0] % len(_PLATES)]
        return [
            RecognizedFood(
                name=name,
                name_en=name_en,
                estimated_weight_grams=grams,
                confidence=confidence,
            )
            for name, name_en, grams, confidence in plate
        ]
