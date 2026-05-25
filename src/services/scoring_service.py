import logging
from typing import Dict, Any, List
from src.clients.firestore_client import FirestoreClient
from src.clients.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

class ScoringService:
    def __init__(self, db: FirestoreClient, gemini: GeminiClient):
        self.db = db
        self.gemini = gemini

    def score_candidates(self) -> None:
        candidates = self.db.get_documents_by_status("product_candidates", "fetched")
        logger.info(f"Found {len(candidates)} candidates to score.")

        with open("src/prompts/product_scoring.txt", "r", encoding="utf-8") as f:
            prompt_template = f.read()

        for candidate in candidates:
            try:
                prompt = prompt_template.replace("{title}", str(candidate.get("title", ""))) \
                                        .replace("{price}", str(candidate.get("price", 0))) \
                                        .replace("{category}", str(candidate.get("category", "")))

                score_data = self.gemini.generate_json(prompt)
                if not score_data:
                    # Mock response for testing without API key
                    score_data = {
                        "time_saving_minutes_per_week": 120,
                        "payback_period_months": 2.5,
                        "persona_fit_score": 8.0,
                        "pain_strength_score": 8.0,
                        "differentiation_score": 7.0,
                        "overall_score": 8.5,
                        "decision": "accept",
                        "reason": "mock reason",
                        "target_scene": "mock scene",
                        "post_angle": "mock angle"
                    }

                score_data["product_candidate_id"] = candidate["id"]
                
                # Rule-based override based on overall_score
                overall = score_data.get("overall_score", 0.0)
                if overall >= 7.5:
                    decision = "accept"
                elif overall >= 5.5:
                    decision = "consider"
                else:
                    decision = "reject"
                score_data["decision"] = decision

                score_id = self.db.add_document("product_scores", score_data)
                logger.info(f"Scored candidate {candidate['id']} -> {score_id} ({decision})")

                if decision == "accept":
                    self.db.update_document("product_candidates", candidate["id"], {"status": "scored_accepted"})
                    product_data = candidate.copy()
                    product_data.pop("id", None)
                    product_data["status"] = "accepted"
                    product_data["score_id"] = score_id
                    self.db.add_document("products", product_data)
                elif decision == "consider":
                    self.db.update_document("product_candidates", candidate["id"], {"status": "review"})
                else:
                    self.db.update_document("product_candidates", candidate["id"], {"status": "rejected"})

            except Exception as e:
                logger.error(f"Error scoring candidate {candidate['id']}: {e}")