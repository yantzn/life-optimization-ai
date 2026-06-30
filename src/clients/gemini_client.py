import json
import logging
from types import SimpleNamespace
from typing import Any, Dict, Optional

from src import config

logger = logging.getLogger(__name__)


class GeminiJSONParseError(ValueError):
    def __init__(self, raw_response: str, original_error: Exception) -> None:
        super().__init__(f"Gemini JSON parse failed: {original_error}")
        self.raw_response = raw_response
        self.original_error = original_error


class GeminiClient:
    """Gemini API呼び出しを集約するクライアント。

    google-genai SDKの response_mime_type="application/json" を使い、
    scoring/enrichmentでは機械処理しやすいJSON構造化出力を期待する。
    ただしLLM出力は常に信用せず、投稿前にはPython側の品質チェックを必ず通す。
    """

    def __init__(self, *, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self.api_key = api_key if api_key is not None else config.GEMINI_API_KEY
        self.model = model or config.GEMINI_MODEL
        self.client: Any = None
        if self.api_key:
            from google import genai

            self.client = genai.Client(api_key=self.api_key)

    def generate_json(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GeminiからJSONを受け取りdictへparseする。

        JSON parse失敗を握りつぶすと、不完全な評価結果がFirestoreへ混入する。
        そのため例外化し、呼び出し側でfallback_used/fallback_reasonとして保存できるようにする。
        """
        if not self.client:
            # APIキー未設定時はdry-runやローカルテストを止めないため空dictを返す。
            # scoring側ではこれをfallback scoreとして明示的に記録する。
            logger.info("gemini_skipped reason=missing_api_key")
            return {}

        response_text = ""
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=self._generate_content_config(
                    # JSON以外の説明文が混ざると後続の状態遷移が壊れるため、
                    # GeminiにはJSONレスポンスを明示的に要求する。
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.2,
                ),
            )
            response_text = response.text or ""
            return json.loads(response_text)
        except json.JSONDecodeError as exc:
            logger.error("gemini_json_parse_failed raw_response=%r error=%s", response_text, exc)
            raise GeminiJSONParseError(response_text, exc) from exc
        except Exception:
            logger.exception("gemini_generate_json_failed")
            raise

    def generate_text(self, prompt: str, temperature: float = 0.2) -> str:
        """自由文生成用。

        MVPでは投稿文も可能な限りJSON生成を使うが、将来のrewrite用途を考えて残している。
        """
        if not self.client:
            logger.info("gemini_skipped reason=missing_api_key")
            return ""

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=self._generate_content_config(temperature=temperature),
            )
            return response.text or ""
        except Exception:
            logger.exception("gemini_generate_text_failed")
            raise

    @staticmethod
    def _generate_content_config(**kwargs: Any) -> Any:
        try:
            from google.genai import types

            return types.GenerateContentConfig(**kwargs)
        except Exception:
            return SimpleNamespace(**kwargs)
