import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.clients.firestore_client import FirestoreClient

logger = logging.getLogger(__name__)


class Collector:
    """商品候補をproduct_candidatesへ投入するservice。

    初期フェーズではASP APIに依存せず、手動キュレーションしたJSON/CSVを取り込む。
    将来はGAS/Spreadsheet同期やCloud Run Batch Collectorへ置き換えられる境界。
    """
    REQUIRED_FIELDS = {"source", "title", "price", "category", "affiliate_url"}

    def __init__(self, db: FirestoreClient):
        self.db = db

    def ingest_file(self, file_path: str) -> int:
        """JSON/CSVの商品行をFirestoreのproduct_candidates(status=fetched)へ登録する。"""
        path = Path(file_path)
        rows = self._load_rows(path)
        count = 0
        for row in rows:
            candidate = self._normalize_candidate(row)
            self.db.add_document("product_candidates", candidate)
            count += 1
        logger.info("products_ingested count=%s file=%s", count, path)
        return count

    def collect_mocks(self) -> int:
        return self.ingest_rows(
            [
                {
                    "source": "manual",
                    "title": "食洗機対応の時短フライパンセット",
                    "price": 12800,
                    "category": "キッチン",
                    "image_url": "https://example.com/pan.jpg",
                    "affiliate_url": "https://example.com/lp/pan",
                    "rating": 4.4,
                    "review_count": 318,
                },
                {
                    "source": "manual",
                    "title": "ロボット掃除機エントリーモデル",
                    "price": 39800,
                    "category": "スマート家電",
                    "image_url": "https://example.com/robot.jpg",
                    "affiliate_url": "https://example.com/lp/robot",
                    "rating": 4.2,
                    "review_count": 921,
                },
            ]
        )

    def ingest_rows(self, rows: Iterable[Dict[str, Any]]) -> int:
        count = 0
        for row in rows:
            self.db.add_document("product_candidates", self._normalize_candidate(row))
            count += 1
        return count

    def _load_rows(self, path: Path) -> List[Dict[str, Any]]:
        if path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data = data.get("products", [])
            if not isinstance(data, list):
                raise ValueError("JSON input must be a list or {'products': [...]}")
            return [dict(item) for item in data]

        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                return [dict(row) for row in csv.DictReader(handle)]

        raise ValueError("Only JSON and CSV product files are supported")

    def _normalize_candidate(self, row: Dict[str, Any]) -> Dict[str, Any]:
        missing = self.REQUIRED_FIELDS - {key for key, value in row.items() if value not in (None, "")}
        if missing:
            raise ValueError(f"Missing required product fields: {sorted(missing)}")

        now = self.db.now_iso()
        return {
            "source": str(row.get("source", "manual")),
            "title": str(row["title"]).strip(),
            "price": int(float(row.get("price", 0))),
            "category": str(row.get("category", "")).strip(),
            "image_url": str(row.get("image_url", "")).strip(),
            "affiliate_url": str(row.get("affiliate_url", "")).strip(),
            "rating": float(row.get("rating", 0) or 0),
            "review_count": int(float(row.get("review_count", 0) or 0)),
            "fetched_at": str(row.get("fetched_at") or now),
            "status": str(row.get("status") or "fetched"),
        }
