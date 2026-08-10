"""Provider lookup.

Switching models is configuration, never a code change: set `MODEL_PROVIDER`,
or send `X-Model-Provider` to override it for a single request. The per-request
override is what makes A/B comparison and debugging practical — the same photo
can be sent to two models back to back.
"""

import os
from typing import Dict, List

from .base import FoodRecognitionProvider
from .gemini import GeminiProvider
from .mock import MockProvider
from .qwen import QwenProvider

_PROVIDERS: Dict[str, FoodRecognitionProvider] = {}


def _register(provider: FoodRecognitionProvider) -> None:
    _PROVIDERS[provider.name] = provider


_register(MockProvider())
_register(GeminiProvider())
_register(QwenProvider())


DEFAULT_PROVIDER = os.getenv("MODEL_PROVIDER", "mock")


class UnknownProviderError(KeyError):
    pass


def available() -> List[Dict[str, object]]:
    """Every registered provider and whether it is usable right now."""
    return [
        {"name": name, "configured": provider.is_configured}
        for name, provider in sorted(_PROVIDERS.items())
    ]


def get(name: str = None) -> FoodRecognitionProvider:
    """Resolve a provider by name, falling back to `MODEL_PROVIDER`.

    An unknown name is an error rather than a silent fallback: quietly serving
    a different model than the caller asked for would make results impossible
    to interpret.
    """
    key = (name or DEFAULT_PROVIDER).strip().lower()
    if key not in _PROVIDERS:
        raise UnknownProviderError(key)
    return _PROVIDERS[key]
