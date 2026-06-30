import argparse
import logging

from src import config
from src.clients.firestore_client import FirestoreClient
from src.clients.gemini_client import GeminiClient
from src.clients.threads_client import ThreadsClient
from src.services.collector import Collector
from src.services.content_generator import ContentGenerator
from src.services.product_service import ProductService
from src.services.publisher import Publisher
from src.services.quality_gate import QualityGate
from src.services.scoring_service import ScoringService

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """MVPパイプラインの手動実行入口を定義する。

    初期運用ではASP APIを直接叩かず、手動キュレーションした商品を
    JSON/CSVから投入し、Firestoreのstatusを進めながら各段階を確認する。
    """
    parser = argparse.ArgumentParser(description="Threads affiliate MVP pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    # ingest-products:
    # ローカルJSON/CSVを product_candidates に登録する。
    # PA-APIやA8 APIの利用資格がない初期フェーズでも商品選定を進めるための入口。
    ingest = sub.add_parser("ingest-products")
    ingest.add_argument("--file", required=True)

    for name in ["score-products", "enrich-products", "generate-posts", "quality-check-posts", "publish-posts", "run-mvp"]:
        command = sub.add_parser(name)
        command.add_argument("--limit", type=int, default=None)
        if name == "publish-posts":
            # publish-posts:
            # approved / queued の投稿を対象にする。--dry-run は実投稿前の安全確認用で、
            # Threads APIを呼ばず post_logs に dry_run_success を残す。
            command.add_argument("--dry-run", action="store_true", default=None)

    return parser


def main() -> None:
    """CLIコマンドを各service層へ委譲する。

    ここでは処理順序を制御するだけにして、Firestore/Gemini/Threadsの詳細は
    client/service層へ閉じ込める。secret値はログに出さない。
    """
    config.configure_logging()
    args = build_parser().parse_args()
    db = FirestoreClient()
    gemini = GeminiClient()

    if args.command == "ingest-products":
        count = Collector(db).ingest_file(args.file)
    elif args.command == "score-products":
        # fetched の product_candidates をGeminiで一次評価し product_scores を作る。
        # GEMINI_API_KEY未設定またはAPI失敗時はfallback_used/fallback_reason付きで代替評価する。
        count = ScoringService(db, gemini).score_candidates(limit=args.limit)
    elif args.command == "enrich-products":
        # raw の products にROIと詳細文脈を付け、enriched_products へ保存する。
        # 後続のLP/CMSや投稿生成はこのcollectionを入力にする。
        count = ProductService(db, gemini).analyze_products(limit=args.limit)
    elif args.command == "generate-posts":
        # enriched_products から post_candidates(draft) を生成する。
        # PR表記、CTA、affiliate_urlの扱いは生成後の品質チェックでも再確認する。
        count = ContentGenerator(db, gemini).generate_posts(limit=args.limit)
    elif args.command == "quality-check-posts":
        # publish前だけでなく生成直後にも品質を見て、approved/rejectedへ振り分ける。
        count = QualityGate(db, gemini).check_quality(limit=args.limit)
    elif args.command == "publish-posts":
        dry_run = True if args.dry_run else config.DRY_RUN
        count = Publisher(db, ThreadsClient(dry_run=dry_run)).publish_queued_posts(limit=args.limit)
    elif args.command == "run-mvp":
        count = run_mvp(db, gemini, limit=args.limit)
    else:
        raise ValueError(f"Unsupported command: {args.command}")

    logger.info("command_completed command=%s processed=%s", args.command, count)


def run_mvp(db: FirestoreClient, gemini: GeminiClient, *, limit: int | None = None) -> int:
    """ローカルdry-run用の最短疎通パイプライン。

    product_candidates -> product_scores -> products -> enriched_products
    -> post_candidates -> post_logs までを1プロセスで進める。
    ThreadsClientは明示的にdry_run=Trueで作るため、この一括実行では実投稿しない。
    """
    collector = Collector(db)
    scorer = ScoringService(db, gemini)
    products = ProductService(db, gemini)
    generator = ContentGenerator(db, gemini)
    quality = QualityGate(db, gemini)
    publisher = Publisher(db, ThreadsClient(dry_run=True))

    if not db.get_documents_by_status("product_candidates", "fetched", limit=1):
        collector.collect_mocks()

    total = 0
    total += scorer.score_candidates(limit=limit)
    total += products.analyze_products(limit=limit)
    total += generator.generate_posts(limit=limit)
    total += quality.check_quality(limit=limit)
    total += publisher.publish_queued_posts(limit=limit)
    return total


if __name__ == "__main__":
    main()
