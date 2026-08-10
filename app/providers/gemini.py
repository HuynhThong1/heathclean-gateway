"""Gemini provider — plan.md §31 nominates the free tier for the POC.

**Unverified.** No API key was available when this was written, so the request
shape follows Google's published REST contract but has never been run. Treat
the first live call as the real test.
"""

import base64
import json
import os
from typing import List, Optional

import httpx

from .base import FoodRecognitionProvider, ProviderError, RecognizedFood
from .prompt import RECOGNITION_PROMPT, parse_recognition_json

_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


class GeminiProvider(FoodRecognitionProvider):
    name = "gemini"

    def __init__(self) -> None:
        self._api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
        self._model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self._timeout = float(os.getenv("PROVIDER_TIMEOUT_SECONDS", "30"))

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def recognize(self, image_bytes: bytes, mime_type: str) -> List[RecognizedFood]:
        if not self._api_key:
            raise ProviderError("GEMINI_API_KEY is not set")

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": RECOGNITION_PROMPT},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": base64.b64encode(image_bytes).decode("ascii"),
                            }
                        },
                    ]
                }
            ],
            # Ask for JSON rather than hoping for it — free-form text would put
            # a parser between the model and the user's calories.
            "generationConfig": {"response_mime_type": "application/json"},
        }

        url = _ENDPOINT.format(model=self._model)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                url, params={"key": self._api_key}, json=payload
            )
        if response.status_code != 200:
            raise ProviderError(
                "Gemini returned {}: {}".format(response.status_code, response.text[:200])
            )

        try:
            body = response.json()
            text = body["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, ValueError) as error:
            raise ProviderError("Unexpected Gemini response shape: {}".format(error))

        return parse_recognition_json(text)
