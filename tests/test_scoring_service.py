from src.clients.firestore_client import FirestoreClient
from src.services.scoring_service import ScoringService


class MissingKeyGemini:
    client = None

    def generate_json(self, prompt: str, schema=None):
        raise AssertionError("generate_json should not be called without a client")


class WorkingGemini:
    client = object()

    def generate_json(self, prompt: str, schema=None):
        return {
            "time_saving_minutes_per_week": 100,
            "payback_period_months": 2.0,
            "persona_fit_score": 8.0,
            "pain_strength_score": 8.0,
            "differentiation_score": 7.0,
            "overall_score": 8.0,
            "decision": "accept",
            "reason": "商品ごとのGemini評価",
            "target_scene": "夕飯後",
            "post_angle": "時間を取り戻す",
        }


class FailingGemini:
    client = object()

    def generate_json(self, prompt: str, schema=None):
        raise RuntimeError("api down")


def _add_candidate(db: FirestoreClient) -> None:
    db.add_document(
        "product_candidates",
        {
            "source": "manual",
            "title": "時短フライパン",
            "price": 12800,
            "category": "キッチン",
            "image_url": "",
            "affiliate_url": "https://example.com",
            "rating": 4.4,
            "review_count": 100,
            "status": "fetched",
        },
        doc_id="candidate-1",
    )


def test_fallback_used_when_gemini_key_missing():
    db = FirestoreClient(dry_run=True, storage_path=None)
    _add_candidate(db)

    ScoringService(db, MissingKeyGemini()).score_candidates()

    score = db.get_document("product_scores", "candidate-1")
    assert score["fallback_used"] is True
    assert "GEMINI_API_KEY" in score["fallback_reason"]
    assert score["reason"] != "dry-run fallback score"


def test_gemini_used_when_client_available():
    db = FirestoreClient(dry_run=True, storage_path=None)
    _add_candidate(db)

    ScoringService(db, WorkingGemini()).score_candidates()

    score = db.get_document("product_scores", "candidate-1")
    assert score["fallback_used"] is False
    assert score["fallback_reason"] is None
    assert score["reason"] == "商品ごとのGemini評価"


def test_fallback_used_when_gemini_call_fails():
    db = FirestoreClient(dry_run=True, storage_path=None)
    _add_candidate(db)

    ScoringService(db, FailingGemini()).score_candidates()

    score = db.get_document("product_scores", "candidate-1")
    assert score["fallback_used"] is True
    assert "api down" in score["fallback_reason"]
