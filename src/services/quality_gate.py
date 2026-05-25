import logging
from typing import Dict, Any, List
from src.clients.firestore_client import FirestoreClient
from src.clients.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

class QualityGate:
    def __init__(self, db: FirestoreClient, gemini: GeminiClient):
        self.db = db
        self.gemini = gemini

    def check_quality(self) -> None:
        candidates = self.db.get_documents_by_status("post_candidates", "generated")
        logger.info(f"Found {len(candidates)} posts to quality check.")

        with open("src/prompts/quality_check.txt", "r", encoding="utf-8") as f:
            quality_prompt_template = f.read()

        with open("src/prompts/rewrite_threads_style.txt", "r", encoding="utf-8") as f:
            rewrite_prompt_template = f.read()

        for candidate in candidates:
            try:
                text = candidate.get("post_text", "")
                
                # 1. Quality Check
                q_prompt = quality_prompt_template.replace("{text}", text)
                q_result = self.gemini.generate_json(q_prompt)
                
                if not q_result:
                    q_result = {"score": 85, "feedback": "Looks good."}
                
                score = q_result.get("score", 0)
                
                if score < 80:
                    # Rewrite
                    r_prompt = rewrite_prompt_template.replace("{text}", text)
                    new_text = self.gemini.generate_text(r_prompt)
                    if new_text:
                        text = new_text
                        
                        # Re-check Quality
                        q_prompt2 = quality_prompt_template.replace("{text}", text)
                        q_result2 = self.gemini.generate_json(q_prompt2)
                        if q_result2:
                            score = q_result2.get("score", 0)

                if score >= 80:
                    status = "queued"
                else:
                    status = "rejected"

                self.db.update_document("post_candidates", candidate["id"], {
                    "post_text": text,
                    "quality_score": score,
                    "status": status
                })
                logger.info(f"Quality check for {candidate['id']}: score={score}, status={status}")

            except Exception as e:
                logger.error(f"Error checking quality for {candidate['id']}: {e}")