import logging
from typing import List, Dict, Any
from src.clients.firestore_client import FirestoreClient

logger = logging.getLogger(__name__)

class Collector:
    def __init__(self, db: FirestoreClient):
        self.db = db

    def collect_mocks(self) -> None:
        """MVP mock collector."""
        mocks = [
            {
                "source": "mock",
                "title": "ロボット掃除機 ルンバ i7+",
                "price": 89800,
                "category": "家電",
                "image_url": "http://example.com/roomba.jpg",
                "affiliate_url": "http://example.com/affiliate/roomba",
                "rating": 4.5,
                "review_count": 1200,
                "status": "fetched"
            },
            {
                "source": "mock",
                "title": "自動調理鍋 ホットクック 2.4L",
                "price": 55000,
                "category": "家電",
                "image_url": "http://example.com/hotcook.jpg",
                "affiliate_url": "http://example.com/affiliate/hotcook",
                "rating": 4.8,
                "review_count": 800,
                "status": "fetched"
            }
        ]

        for item in mocks:
            doc_id = self.db.add_document("product_candidates", item)
            logger.info(f"Added mock product candidate: {doc_id}")