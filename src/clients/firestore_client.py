import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from google.cloud import firestore
from src import config

logger = logging.getLogger(__name__)

class FirestoreClient:
    def __init__(self):
        self.dry_run = config.DRY_RUN
        self.mock_db: Dict[str, Dict[str, dict]] = {}
        if not self.dry_run:
            try:
                self.db = firestore.Client(project=config.GCP_PROJECT_ID)
            except Exception as e:
                logger.warning(f"Failed to initialize Firestore: {e}. Falling back to dry_run/mock.")
                self.dry_run = True

    def _get_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def add_document(self, collection_name: str, data: Dict[str, Any], doc_id: Optional[str] = None) -> str:
        if doc_id is None:
            doc_id = str(uuid.uuid4())
        
        data["created_at"] = data.get("created_at", self._get_now())
        data["updated_at"] = data.get("updated_at", self._get_now())

        if self.dry_run:
            if collection_name not in self.mock_db:
                self.mock_db[collection_name] = {}
            self.mock_db[collection_name][doc_id] = data
            return doc_id
        
        try:
            self.db.collection(collection_name).document(doc_id).set(data)
            return doc_id
        except Exception as e:
            logger.error(f"Firestore add_document error: {e}")
            raise

    def update_document(self, collection_name: str, doc_id: str, data: Dict[str, Any]) -> None:
        data["updated_at"] = self._get_now()
        
        if self.dry_run:
            if collection_name in self.mock_db and doc_id in self.mock_db[collection_name]:
                self.mock_db[collection_name][doc_id].update(data)
            return

        try:
            self.db.collection(collection_name).document(doc_id).update(data)
        except Exception as e:
            logger.error(f"Firestore update_document error: {e}")
            raise

    def get_documents_by_status(self, collection_name: str, status: str) -> List[Dict[str, Any]]:
        if self.dry_run:
            if collection_name not in self.mock_db:
                return []
            results = []
            for doc_id, doc_data in self.mock_db[collection_name].items():
                if doc_data.get("status") == status:
                    doc = doc_data.copy()
                    doc["id"] = doc_id
                    results.append(doc)
            return results
        
        try:
            docs = self.db.collection(collection_name).where("status", "==", status).stream()
            results = []
            for doc in docs:
                d = doc.to_dict()
                d["id"] = doc.id
                results.append(d)
            return results
        except Exception as e:
            logger.error(f"Firestore get_documents_by_status error: {e}")
            raise