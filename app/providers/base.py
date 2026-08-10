"""The seam every recognition model plugs into.

The core product rule (plan.md §2) lives here: a provider identifies foods and
estimates portions. It does **not** return calories. Nutrition comes from the
resolver, so the model can be swapped without any risk to the numbers the user
finally sees.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class RecognizedFood:
    """One food a provider believes it saw."""

    name: str
    estimated_weight_grams: float
    confidence: float
    #: English name where the model offers one; used for the bilingual UI.
    name_en: Optional[str] = None


class ProviderError(RuntimeError):
    """Raised when a provider cannot produce a result at all.

    Distinct from "saw nothing", which is an empty list and a normal outcome.
    """


class FoodRecognitionProvider(ABC):
    """Implement this to add a model. Register it in `registry.py`."""

    #: Stable key used by MODEL_PROVIDER and the X-Model-Provider header.
    name: str = "unnamed"

    @property
    def is_configured(self) -> bool:
        """False when the provider is present but unusable — a missing API key,
        say. The registry reports this rather than failing at request time.
        """
        return True

    @abstractmethod
    async def recognize(self, image_bytes: bytes, mime_type: str) -> List[RecognizedFood]:
        """Identify visible foods and estimate grams. Never returns calories."""
        raise NotImplementedError
