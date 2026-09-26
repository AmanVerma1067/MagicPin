from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Dict, Optional
from pydantic import BaseModel, Field

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger("vera.llm")


class CompositionOutput(BaseModel):
    body: str = Field(description="Outbound WhatsApp engagement message (80-280 chars) citing exact facts")
    cta: str = Field(description="Clear binary Yes/No or choice 1/2 closing action prompt")
    rationale: str = Field(description="Concise strategic rationale explaining why this message was selected")


class GeminiClient:
    """Wrapper around google-genai SDK with strict deterministic parameters, SHA-256 caching, and timeouts."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self._cache: Dict[str, CompositionOutput] = {}
        self._client: Optional[genai.Client] = None
        if self.api_key and self.api_key != "your_gemini_api_key_here":
            try:
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Gemini Client: {e}")

    def _hash_prompt(self, prompt: str) -> str:
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    async def generate_composition(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        timeout_s: Optional[float] = None,
    ) -> Optional[CompositionOutput]:
        cache_key = self._hash_prompt(f"{system_instruction or ''}:::{prompt}")
        if cache_key in self._cache:
            return self._cache[cache_key]

        if not self._client:
            return None

        timeout = timeout_s or settings.LLM_TIMEOUT_S

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.0,
            top_p=1.0,
            seed=7,
            response_mime_type="application/json",
            response_schema=CompositionOutput,
        )

        try:
            # Run blocking SDK generate_content call in executor with strict timeout
            loop = asyncio.get_running_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self._client.models.generate_content(
                        model=self.model,
                        contents=prompt,
                        config=config,
                    ),
                ),
                timeout=timeout,
            )

            if response and response.text:
                data = json.loads(response.text)
                parsed = CompositionOutput.model_validate(data)
                self._cache[cache_key] = parsed
                return parsed
        except asyncio.TimeoutError:
            logger.warning(f"Gemini API timeout after {timeout}s")
        except Exception as e:
            logger.warning(f"Gemini API error: {e}")

        return None
