import logging
from pathlib import Path
from typing import Any, Dict

from src import config
from src.clients.firestore_client import FirestoreClient
from src.clients.gemini_client import GeminiClient
from src.services.roi_calculator import calculate_roi

logger = logging.getLogger(__name__)


class ProductService:
    """採用商品に詳細文脈とROIを付けるservice。

    読み: products(status=raw)
    書き: enriched_products(status=enriched)、products(status=enriched)
    enriched_productsは投稿生成だけでなく、将来のCMS/LP表示データにもなる。
    """
    def __init__(self, db: FirestoreClient, gemini: GeminiClient):
        self.db = db
        self.gemini = gemini
        self.prompt_path = Path(__file__).resolve().parents[1] / "prompts" / "product_enrichment.txt"

    def analyze_products(self, *, limit: int | None = None) -> int:
        """raw商品を詳細分析し、ROI計算結果を付与する。"""
        products = self.db.get_documents_by_status("products", "raw", limit=limit)
        prompt_template = self.prompt_path.read_text(encoding="utf-8")
        processed = 0

        for product in products:
            try:
                analysis = self._analyze_product(product, prompt_template)
                minutes = float(analysis.get("time_saving_minutes_per_week", 60))
                roi = calculate_roi(
                    product_price=float(product.get("price", 0)),
                    time_saving_minutes_per_week=minutes,
                    hourly_value=config.DEFAULT_HOURLY_VALUE,
                )
                enriched_data = {
                    "product_id": product["id"],
                    "summary": analysis.get("summary", ""),
                    "use_cases": analysis.get("use_cases", []),
                    "pain_points": analysis.get("pain_points", []),
                    "time_saving_minutes_per_week": minutes,
                    "target_persona": analysis.get("target_persona", "30代の共働きパパ"),
                    "risk_notes": analysis.get("risk_notes", []),
                    "roi": roi,
                    "source_product": {
                        "title": product.get("title", ""),
                        "price": product.get("price", 0),
                        "category": product.get("category", ""),
                        "image_url": product.get("image_url", ""),
                        "affiliate_url": product.get("affiliate_url", ""),
                        "source": product.get("source", ""),
                        "target_scene": product.get("target_scene", ""),
                        "post_angle": product.get("post_angle", ""),
                    },
                    "enriched_at": self.db.now_iso(),
                    "status": "enriched",
                }
                self.db.add_document("enriched_products", enriched_data, doc_id=product["id"])
                self.db.update_document("products", product["id"], {"status": "enriched"})
                processed += 1
            except Exception as exc:
                logger.exception("product_enrichment_failed product_id=%s", product["id"])
                self.db.update_document("products", product["id"], {"status": "enrich_error", "error_message": str(exc)})

        return processed

    def _analyze_product(self, product: Dict[str, Any], prompt_template: str) -> Dict[str, Any]:
        prompt = self._render_prompt(prompt_template, product)
        try:
            analysis = self.gemini.generate_json(prompt)
            if analysis:
                return analysis
        except Exception as exc:
            logger.warning("gemini_enrichment_failed fallback=true product_id=%s error=%s", product.get("id"), exc)

        title = str(product.get("title", ""))
        category = str(product.get("category", ""))
        target_scene = str(product.get("target_scene") or "平日の夜、家事が残る時間")
        return {
            "summary": f"{title}は、{target_scene}の負担を減らすための時短投資として扱える商品です。",
            "use_cases": [target_scene, "休日に家事を持ち越したくない場面"],
            "pain_points": [self._pain_point(category, title), "家事が終わらず自分の時間が削られる"],
            "time_saving_minutes_per_week": self._fallback_minutes(category, title),
            "target_persona": "仕事も育児も抱えながら、根性論ではなく仕組みで家事を減らしたい30代共働きパパ",
            "risk_notes": ["効果を断定せず、時間削減の見込みとして表現する"],
        }

    @staticmethod
    def _fallback_minutes(category: str, title: str) -> int:
        text = f"{category} {title}"
        if "ロボット" in text or "掃除" in text:
            return 120
        if "キッチン" in text or "フライパン" in text:
            return 75
        return 60

    @staticmethod
    def _pain_point(category: str, title: str) -> str:
        text = f"{category} {title}"
        if "ロボット" in text or "掃除" in text:
            return "床掃除を後回しにして、夜に部屋の汚れが気になる"
        if "キッチン" in text or "フライパン" in text:
            return "夕飯後の洗い物と片付けがだらだら残る"
        return "細かい家事判断が積み重なって夜の余白が消える"

    @staticmethod
    def _render_prompt(template: str, context: Dict[str, Any]) -> str:
        rendered = template
        for key, value in context.items():
            rendered = rendered.replace("{" + key + "}", str(value))
        return rendered
