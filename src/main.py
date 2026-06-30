import argparse

from src import config
from src.cli import run_mvp
from src.clients.firestore_client import FirestoreClient
from src.clients.gemini_client import GeminiClient
from src.clients.threads_client import ThreadsClient
from src.services.collector import Collector
from src.services.content_generator import ContentGenerator
from src.services.product_service import ProductService
from src.services.publisher import Publisher
from src.services.quality_gate import QualityGate
from src.services.scoring_service import ScoringService


def main() -> None:
    config.configure_logging()
    parser = argparse.ArgumentParser(description="Compatibility entrypoint. Prefer python -m src.cli.")
    parser.add_argument("--mode", required=True, choices=["collect", "score", "analyze", "generate", "publish", "all"])
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    db = FirestoreClient()
    gemini = GeminiClient()

    if args.mode == "collect":
        Collector(db).collect_mocks()
    elif args.mode == "score":
        ScoringService(db, gemini).score_candidates(limit=args.limit)
    elif args.mode == "analyze":
        ProductService(db, gemini).analyze_products(limit=args.limit)
    elif args.mode == "generate":
        ContentGenerator(db, gemini).generate_posts(limit=args.limit)
        QualityGate(db, gemini).check_quality(limit=args.limit)
    elif args.mode == "publish":
        Publisher(db, ThreadsClient()).publish_queued_posts(limit=args.limit)
    else:
        run_mvp(db, gemini, limit=args.limit)


if __name__ == "__main__":
    main()
