import pytest

from src.clients.gemini_client import GeminiClient, GeminiJSONParseError


class FakeModels:
    def generate_content(self, **kwargs):
        return type("Response", (), {"text": "{not json"})()


class FakeClient:
    models = FakeModels()


def test_gemini_json_parse_error_is_raised_and_exposes_raw_response():
    client = GeminiClient(api_key="")
    client.client = FakeClient()

    with pytest.raises(GeminiJSONParseError) as exc:
        client.generate_json("prompt")

    assert exc.value.raw_response == "{not json"
