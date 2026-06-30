import logging
from pathlib import Path
from typing import Any, Dict, Tuple

from src.clients.firestore_client import FirestoreClient
from src.clients.gemini_client import GeminiClient

logger = logging.getLogger(__name__)


class ScoringService:
    """商品候補を一次評価し、採用/レビュー/却下へ振り分けるservice。

    読み: product_candidates(status=fetched)
    書き: product_scores、products、review_products、product_candidates.status
    Geminiは評価材料を作り、Python側の閾値で最終状態を安定的に決める。
    """

    def __init__(self, db: FirestoreClient, gemini: GeminiClient):
        self.db = db
        self.gemini = gemini
        self.prompt_path = Path(__file__).resolve().parents[1] / "prompts" / "product_scoring.txt"

    def score_candidates(self, *, limit: int | None = None) -> int:
        """fetchedの商品候補を評価する。

        状態遷移:
        product_candidates: fetched -> scored -> accepted/review/rejected
        acceptedはproducts(status=raw)へ昇格し、considerはreview_productsへ残す。
        """
        candidates = self.db.get_documents_by_status("product_candidates", "fetched", limit=limit)
        prompt_template = self.prompt_path.read_text(encoding="utf-8")
        processed = 0

        for candidate in candidates:
            try:
                score_data, fallback_used, fallback_reason = self._score_candidate(candidate, prompt_template)
                decision = self._normalize_decision(score_data)
                score_data.update(
                    {
                        "product_candidate_id": candidate["id"],
                        "decision": decision,
                        "fallback_used": fallback_used,
                        "fallback_reason": fallback_reason,
                        "scored_at": self.db.now_iso(),
                    }
                )
                self.db.update_document("product_candidates", candidate["id"], {"status": "scored"})
                score_id = self.db.add_document("product_scores", score_data, doc_id=candidate["id"])
                self._promote_candidate(candidate, score_data, score_id, decision)
                processed += 1
            except Exception as exc:
                self.db.update_document(
                    "product_candidates",
                    candidate["id"],
                    {"status": "score_error", "error_message": str(exc)},
                )
                logger.exception("score_failed candidate_id=%s", candidate["id"])

        return processed

    def _score_candidate(self, candidate: Dict[str, Any], prompt_template: str) -> Tuple[Dict[str, Any], bool, str | None]:
        """Geminiが使える時はdry-runでもGemini評価を優先する。

        fallbackはAPIキー未設定やAPI障害時にローカル疎通を止めないための代替で、
        本番品質の評価ではない。運用上判別できるようfallback_used/fallback_reasonを保存する。
        """
        prompt = self._render_prompt(prompt_template, candidate)
        if not self.gemini.client:
            return self._fallback_score(candidate), True, "GEMINI_API_KEY is not configured"

        try:
            score_data = self.gemini.generate_json(prompt)
            if score_data:
                return score_data, False, None
            return self._fallback_score(candidate), True, "Gemini returned an empty JSON object"
        except Exception as exc:
            logger.warning("gemini_score_failed fallback=true candidate_id=%s error=%s", candidate.get("id"), exc)
            return self._fallback_score(candidate), True, str(exc)

    def _fallback_score(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Gemini未使用時の控えめなルールベース評価。

        固定文言だけのreasonにせず、カテゴリ・価格・レビューから商品ごとの説明を作る。
        """
        price = float(candidate.get("price", 0) or 0)
        category = str(candidate.get("category", ""))
        title = str(candidate.get("title", ""))
        review_count = int(candidate.get("review_count", 0) or 0)
        rating = float(candidate.get("rating", 0) or 0)

        category_minutes = {
            "キッチン": 75,
            "スマート家電": 120,
            "家電": 100,
            "掃除": 110,
            "育児": 45,
        }
        minutes = next((value for key, value in category_minutes.items() if key in category or key in title), 60)
        persona = min(10.0, 5.5 + (rating / 5.0) * 2.0 + min(review_count, 1000) / 1000)
        pain = min(10.0, 5.0 + minutes / 30.0)
        differentiation = 6.0 if price < 50000 else 5.5
        overall = round(min(10.0, (persona * 0.3) + (pain * 0.45) + (differentiation * 0.25) + 0.6), 2)
        monthly_value = (minutes * 4 / 60) * 2000
        payback = round(price / monthly_value, 2) if monthly_value > 0 else None

        return {
            "time_saving_minutes_per_week": minutes,
            "payback_period_months": payback,
            "persona_fit_score": round(persona, 2),
            "pain_strength_score": round(pain, 2),
            "differentiation_score": differentiation,
            "overall_score": overall,
            "decision": "accept" if overall >= 7.5 else "consider" if overall >= 5.5 else "reject",
            "reason": f"{category or '生活用品'}として、週{minutes}分ほど家事や判断の摩擦を減らせる可能性があるため。",
            "target_scene": self._target_scene(category, title),
            "post_angle": self._post_angle(category, minutes),
        }

    def _normalize_decision(self, score_data: Dict[str, Any]) -> str:
        """Geminiのdecision文字列をそのまま信じず、overall_scoreの閾値で正規化する。"""
        overall = float(score_data.get("overall_score", 0))
        if overall >= 7.5:
            return "accept"
        if overall >= 5.5:
            return "consider"
        return "reject"

    def _promote_candidate(
        self,
        candidate: Dict[str, Any],
        score_data: Dict[str, Any],
        score_id: str,
        decision: str,
    ) -> None:
        """一次評価結果をFirestoreの次collectionへ反映する。

        accept: products(status=raw)へ昇格
        consider: review_productsで人間確認
        reject: candidateのstatusだけrejectedにする
        """
        status_map = {"accept": "accepted", "consider": "review", "reject": "rejected"}
        self.db.update_document("product_candidates", candidate["id"], {"status": status_map[decision]})

        if decision == "accept":
            self.db.add_document(
                "products",
                {
                    "title": candidate["title"],
                    "price": candidate["price"],
                    "category": candidate.get("category", ""),
                    "image_url": candidate.get("image_url", ""),
                    "affiliate_url": candidate.get("affiliate_url", ""),
                    "source": candidate.get("source", ""),
                    "selection_score": score_data.get("overall_score", 0),
                    "selected_reason": score_data.get("reason", ""),
                    "target_scene": score_data.get("target_scene", ""),
                    "post_angle": score_data.get("post_angle", ""),
                    "score_id": score_id,
                    "candidate_id": candidate["id"],
                    "status": "raw",
                },
            )
        elif decision == "consider":
            self.db.add_document(
                "review_products",
                {
                    "candidate_id": candidate["id"],
                    "score_id": score_id,
                    "title": candidate.get("title", ""),
                    "selection_score": score_data.get("overall_score", 0),
                    "reason": score_data.get("reason", ""),
                    "status": "review",
                },
            )

    @staticmethod
    def _target_scene(category: str, title: str) -> str:
        text = f"{category} {title}"
        if "キッチン" in text:
            return "夕飯後、シンク前で片付けが積み上がる時間"
        if "掃除" in text or "ロボット" in text:
            return "子どもを寝かせた後に床の汚れが目に入る時間"
        return "平日の夜、家事と仕事の残りが重なる時間"

    @staticmethod
    def _post_angle(category: str, minutes: float) -> str:
        if minutes >= 100:
            return "毎週のまとまった時間を買い戻す投資"
        if "キッチン" in category:
            return "夕飯後の片付け摩擦を減らす仕組み化"
        return "小さな家事ストレスを先回りで減らす投資"

    @staticmethod
    def _render_prompt(template: str, context: Dict[str, Any]) -> str:
        rendered = template
        for key, value in context.items():
            rendered = rendered.replace("{" + key + "}", str(value))
        return rendered
