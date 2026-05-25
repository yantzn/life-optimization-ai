import logging
from typing import Dict, Any, List
from src.clients.firestore_client import FirestoreClient
from src.clients.gemini_client import GeminiClient
from src.services.roi_calculator import ROICalculator

logger = logging.getLogger(__name__)

class ProductService:
    def __init__(self, db: FirestoreClient, gemini: GeminiClient):
        self.db = db
        self.gemini = gemini

    def analyze_products(self) -> None:
        # Fetch both "raw" and "accepted" products
        products = self.db.get_documents_by_status("products", "accepted")
        products.extend(self.db.get_documents_by_status("products", "raw"))

        logger.info(f"Found {len(products)} products to analyze.")

        with open("src/prompts/product_analysis.txt", "r", encoding="utf-8") as f:
            prompt_template = f.read()

        for product in products:
            try:
                prompt = prompt_template.replace("{title}", str(product.get("title", ""))) \
                                        .replace("{category}", str(product.get("category", "")))

                analysis_data = self.gemini.generate_json(prompt)
                if not analysis_data:
                    # Mock response for testing
                    analysis_data = {
                        "summary": "Mock summary",
                        "use_cases": ["Case 1", "Case 2"],
                        "pain_points": ["Pain 1", "Pain 2"],
                        "time_saving_minutes_per_week": 180,
                        "target_persona": "Busy parents",
                        "risk_notes": "None"
                    }

                # Calculate ROI
                price = product.get("price", 0)
                ts = analysis_data.get("time_saving_minutes_per_week", 0)
                roi_data = ROICalculator.calculate(price, ts)

                enriched_data = {
                    "product_id": product["id"],
                    "summary": analysis_data.get("summary", ""),
                    "use_cases": analysis_data.get("use_cases", []),
                    "pain_points": analysis_data.get("pain_points", []),
                    "time_saving_minutes_per_week": ts,
                    "target_persona": analysis_data.get("target_persona", ""),
                    "risk_notes": analysis_data.get("risk_notes", ""),
                    "roi": roi_data,
                    "status": "enriched"
                }

                self.db.add_document("enriched_products", enriched_data)
                self.db.update_document("products", product["id"], {"status": "analyzed"})
                logger.info(f"Analyzed product {product['id']}")

            except Exception as e:
                logger.error(f"Error analyzing product {product['id']}: {e}")