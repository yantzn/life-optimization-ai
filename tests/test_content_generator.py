from src.clients.firestore_client import FirestoreClient
from src.services.content_generator import ContentGenerator


class MockGeminiClient:
    client = None

    def generate_json(self, prompt: str, schema=None):
        return {}

    def generate_text(self, prompt: str, temperature: float = 0.2) -> str:
        return ""


def _add_product(db: FirestoreClient, doc_id: str, title: str, affiliate_url: str = "https://example.com/lp") -> None:
    db.add_document(
        "products",
        {"title": title, "status": "enriched"},
        doc_id=doc_id,
    )
    db.add_document(
        "enriched_products",
        {
            "product_id": doc_id,
            "summary": f"{title}で夜の家事を減らす",
            "pain_points": ["夕飯後の片付けがだらだら残る"],
            "use_cases": ["夕飯後、シンク前で片付けが積み上がる時間"],
            "target_persona": "共働きパパ",
            "roi": {"roi_comment": "1か月ちょっとで元が取れるならかなり現実的。"},
            "source_product": {
                "title": title,
                "category": "キッチン",
                "affiliate_url": affiliate_url,
                "source": "manual",
                "post_angle": "片付け摩擦を減らす",
                "target_scene": "夕飯後、シンク前で片付けが積み上がる時間",
            },
            "status": "enriched",
        },
        doc_id=doc_id,
    )


def test_content_generator_creates_draft_post(monkeypatch):
    monkeypatch.setattr("src.services.content_generator.ContentGenerator._choose_post_type", lambda self: "affiliate")
    db = FirestoreClient(dry_run=True, storage_path=None)
    _add_product(db, "product-1", "時短フライパン")

    count = ContentGenerator(db, MockGeminiClient()).generate_posts()

    posts = db.get_documents_by_status("post_candidates", "draft")
    assert count == 1
    assert posts[0]["product_id"] == "product-1"
    assert posts[0]["post_type"] == "affiliate"
    assert posts[0]["post_text"].startswith("【PR】")
    assert "判定はbuyです" not in posts[0]["post_text"]


def test_a8_direct_link_is_not_in_post_text(monkeypatch):
    monkeypatch.setattr("src.services.content_generator.ContentGenerator._choose_post_type", lambda self: "affiliate")
    db = FirestoreClient(dry_run=True, storage_path=None)
    _add_product(db, "product-1", "時短フライパン", affiliate_url="https://px.a8.net/svt/ejp?a8mat=abc")

    ContentGenerator(db, MockGeminiClient()).generate_posts()

    post = db.get_documents_by_status("post_candidates", "draft")[0]
    assert "px.a8.net" not in post["post_text"]
    assert "プロフィール" in post["post_text"]


def test_hooks_are_unique_in_same_run(monkeypatch):
    monkeypatch.setattr("src.services.content_generator.ContentGenerator._choose_post_type", lambda self: "affiliate")
    db = FirestoreClient(dry_run=True, storage_path=None)
    _add_product(db, "product-1", "時短フライパンA")
    _add_product(db, "product-2", "時短フライパンB")

    ContentGenerator(db, MockGeminiClient()).generate_posts()

    posts = db.get_documents_by_status("post_candidates", "draft")
    hooks = [post["hook"] for post in posts]
    assert len(hooks) == len(set(hooks))
