import logging
import json
from typing import Dict, Any, Optional
from google import genai
from google.genai import types
from src import config

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self):
        self.dry_run = config.DRY_RUN
        self.client = None
        if config.GEMINI_API_KEY:
            try:
                self.client = genai.Client(api_key=config.GEMINI_API_KEY)
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini Client: {e}")

    def generate_json(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.client:
            logger.warning("Gemini Client not initialized. Returning empty dict.")
            return {}

        try:
            config_opts = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2
            )
            response = self.client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=config_opts
            )
            return json.loads(response.text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Gemini: {e}. Raw response: {response.text}")
            raise
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise

    def generate_text(self, prompt: str, temperature: float = 0.2) -> str:
        if not self.client:
            logger.warning("Gemini Client not initialized. Returning empty string.")
            return ""

        try:
            config_opts = types.GenerateContentConfig(
                temperature=temperature
            )
            response = self.client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=config_opts
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise