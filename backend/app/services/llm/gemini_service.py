"""
Gemini LLM Client Service.

Provides resilient access to Google Gemini models with automatic model fallback
and offline deterministic fallback handling.
"""

from __future__ import annotations

import os
import re
from typing import List, Optional
import httpx
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

# Priority models to try in order
MODELS_TO_TRY = [
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-pro-latest",
]


class GeminiService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        timeout: float = 30.0,
    ) -> Optional[str]:
        """
        Sends prompt to Gemini REST API. Tries multiple models if one is busy/rate-limited.
        Returns generated text or None if all requests fail.
        """
        if not self.is_available():
            return None

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        for model in MODELS_TO_TRY:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            try:
                response = httpx.post(url, json=payload, timeout=timeout)
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
                elif response.status_code in (429, 503):
                    # Busy / high demand, try next model
                    continue
                else:
                    # Model not found or invalid
                    continue
            except httpx.ConnectError:
                # Network unreachable / offline / sandbox: don't retry subsequent models
                break
            except Exception:
                continue

        return None


# Global singleton instance
gemini_service = GeminiService()
