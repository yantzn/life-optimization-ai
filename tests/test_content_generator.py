import pytest
from src.services.content_generator import ContentGenerator
from src.clients.firestore_client import FirestoreClient

class MockGeminiClient:
    def generate_text(self, prompt: str, temperature: float = 0.2) -> str:
        return "Generated mock text."

def test_content_generator_creates_post():
    db = FirestoreClient()
    db.dry_run = True
    
    product = {
        "product_id": "test_prod_1",
        "summary": "Test Product",
        "status": "enriched"
    }
    db.add_document("enriched_products", product, "doc_1")
    
    gemini = MockGeminiClient()
    generator = ContentGenerator(db, gemini)
    
    generator.generate_posts()
    
    posts = db.get_documents_by_status("post_candidates", "generated")
    assert len(posts) == 1
    assert posts[0]["product_id"] == "test_prod_1"
    assert posts[0]["post_text"] == "Generated mock text."
    
    enriched = db.mock_db["enriched_products"]["doc_1"]
    assert enriched["status"] == "post_generated"