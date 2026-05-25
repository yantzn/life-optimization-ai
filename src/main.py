import argparse
import logging
from src.clients.firestore_client import FirestoreClient
from src.clients.gemini_client import GeminiClient
from src.clients.threads_client import ThreadsClient
from src.services.collector import Collector
from src.services.scoring_service import ScoringService
from src.services.product_service import ProductService
from src.services.content_generator import ContentGenerator
from src.services.quality_gate import QualityGate
from src.services.publisher import Publisher

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Threads Affiliate Auto-Operation System")
    parser.add_argument("--mode", required=True, choices=["collect", "score", "analyze", "generate", "publish", "all"])
    args = parser.parse_args()

    db = FirestoreClient()
    gemini = GeminiClient()
    threads = ThreadsClient()

    collector = Collector(db)
    scorer = ScoringService(db, gemini)
    analyzer = ProductService(db, gemini)
    generator = ContentGenerator(db, gemini)
    quality = QualityGate(db, gemini)
    publisher = Publisher(db, threads)

    try:
        if args.mode in ["collect", "all"]:
            logger.info("--- Starting COLLECT phase ---")
            collector.collect_mocks()

        if args.mode in ["score", "all"]:
            logger.info("--- Starting SCORE phase ---")
            scorer.score_candidates()

        if args.mode in ["analyze", "all"]:
            logger.info("--- Starting ANALYZE phase ---")
            analyzer.analyze_products()

        if args.mode in ["generate", "all"]:
            logger.info("--- Starting GENERATE phase ---")
            generator.generate_posts()
            logger.info("--- Starting QUALITY CHECK phase ---")
            quality.check_quality()

        if args.mode in ["publish", "all"]:
            logger.info("--- Starting PUBLISH phase ---")
            publisher.publish_queued_posts()

        logger.info("Pipeline execution completed successfully.")
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()