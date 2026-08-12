"""Qwen-VL provider, plan.md §8's recommendation for the self-hosted MVP.

Speaks the OpenAI chat-completions shape, which DashScope, OpenRouter, vLLM and
Ollama all expose — so `QWEN_BASE_URL` points at whichever is in use and nothing
else changes.

**Unverified.** No endpoint or key was available when this was written.
"""

import base64
import os
from typing import List, Optional

import httpx

from .base import FoodRecognitionProvider, ProviderError, RecognizedFood
from .prompt import RECOGNITION_PROMPT, parse_recognition_json


class QwenProvider(FoodRecognitionProvider):
    name = "qwen"

    def __init__(self) -> None:
        self._base_url = os.getenv("QWEN_BASE_URL", "").rstrip("/")
        self._api_key: Optional[str] = os.getenv("QWEN_API_KEY")
        self._model = os.getenv("QWEN_MODEL", "qwen2.5-vl-7b-instruct")
        self._timeout = float(os.getenv("PROVIDER_TIMEOUT_SECONDS", "60"))

    @property
    def is_configured(self) -> bool:
        # A local vLLM or Ollama needs no key, so only the URL is required.
        return bool(self._base_url)

    async def recognize(self, image_bytes: bytes, mime_type: str) -> List[RecognizedFood]:
        if not self._base_url:
            raise ProviderError("QWEN_BASE_URL is not set")

        data_url = "data:{};base64,{}".format(
            mime_type, base64.b64encode(image_bytes).decode("ascii")
        )
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": RECOGNITION_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            "temperature": 0,
        }
        headers = {}
        if self._api_key:
            headers["Authorization"] = "Bearer {}".format(self._api_key)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    "{}/chat/completions".format(self._base_url),
                    json=payload,
                    headers=headers,
                )
        except httpx.HTTPError as error:
            raise ProviderError("Qwen request failed: {}".format(error)) from error
        if response.status_code != 200:
            raise ProviderError(
                "Qwen returned {}: {}".format(response.status_code, response.text[:200])
            )

        try:
            text = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as error:
            raise ProviderError("Unexpected Qwen response shape: {}".format(error))

        return parse_recognition_json(text)
