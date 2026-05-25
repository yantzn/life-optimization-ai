import logging
import random
from typing import Dict, Any, List
from src.clients.firestore_client import FirestoreClient
from src.clients.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

class ContentGenerator:
    def __init__(self, db: FirestoreClient, gemini: GeminiClient):
        self.db = db
        self.gemini = gemini

    def generate_posts(self) -> None:
        enriched_products = self.db.get_documents_by_status("enriched_products", "enriched")
        logger.info(f"Found {len(enriched_products)} enriched products to generate posts for.")

        post_types = ["affiliate", "two_line_copy", "story", "account_note"]
        weights = [50, 20, 20, 10]

        for product in enriched_products:
            try:
                # Randomly pick post type
                post_type = random.choices(post_types, weights=weights, k=1)[0]
                
                prompt_file = f"src/prompts/{post_type}.txt" if post_type in ["two_line_copy", "story"] else "src/prompts/story_post.txt"
                
                try:
                    with open(prompt_file, "r", encoding="utf-8") as f:
                        prompt_template = f.read()
                except FileNotFoundError:
                    prompt_template = "以下の商品について投稿を作成してください。商品名: {title}"

                prompt = prompt_template.replace("{title}", str(product.get("summary", "Unknown Product")))

                post_text = self.gemini.generate_text(prompt, temperature=0.7)
                if not post_text:
                    post_text = f"【PR】もっと早く買えばよかった…\nこれ最高です。\n\n詳細はこちら\nhttp://example.com/affiliate/{product['product_id']}"

                post_data = {
                    "product_id": product["product_id"],
                    "post_type": post_type,
                    "platform": "threads",
                    "hook": "Generated Hook",
                    "body": "Generated Body",
                    "hashtags": ["#時短", "#PR"],
                    "cta": "Click here",
                    "post_text": post_text,
                    "quality_score": 0,
                    "status": "generated"
                }

                self.db.add_document("post_candidates", post_data)
                self.db.update_document("enriched_products", product["id"], {"status": "post_generated"})
                logger.info(f"Generated post for product {product['product_id']} ({post_type})")

            except Exception as e:
                logger.error(f"Error generating post for {product['id']}: {e}")