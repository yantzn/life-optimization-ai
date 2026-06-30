import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src import config

logger = logging.getLogger(__name__)


class FirestoreClient:
    """MVPパイプラインの状態管理DBを隠蔽する薄いクライアント。

    Firestore collectionの主な役割:
    - product_candidates: 手動/CSV/APIで集めた未評価の商品候補
    - product_scores: Gemini一次評価とfallback有無の記録
    - products: 採用商品。raw -> enriched -> post_generated -> posted系へ進む
    - enriched_products: ROIと投稿文脈を付与した投稿生成の入力
    - post_candidates: draft/approved/queued/rejected等の投稿候補
    - post_logs: dry-runまたはThreads API投稿の結果ログ

    dry-runやテストではJSONファイル/メモリに差し替え、外部GCPに依存せず
    状態遷移を検証できるようにしている。
    """

    def __init__(
        self,
        *,
        dry_run: Optional[bool] = None,
        storage_path: Optional[str] = config.LOCAL_FIRESTORE_PATH,
    ) -> None:
        self.dry_run = config.DRY_RUN if dry_run is None else dry_run
        self.storage_path = Path(storage_path) if storage_path else None
        self.mock_db: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.db: Any = None

        if self.dry_run:
            self._load_mock_db()
            return

        try:
            from google.cloud import firestore

            self.db = firestore.Client(project=config.GCP_PROJECT_ID or None)
        except Exception as exc:
            logger.warning("firestore_init_failed fallback=dry_run error=%s", exc)
            self.dry_run = True
            self._load_mock_db()

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _load_mock_db(self) -> None:
        if not self.storage_path or not self.storage_path.exists():
            return
        try:
            self.mock_db = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("mock_firestore_load_failed path=%s error=%s", self.storage_path, exc)
            self.mock_db = {}

    def _persist_mock_db(self) -> None:
        if not self.dry_run or not self.storage_path:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(
            json.dumps(self.mock_db, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def add_document(self, collection_name: str, data: Dict[str, Any], doc_id: Optional[str] = None) -> str:
        """新規ドキュメントを追加する。

        新しい処理結果を残す用途。例: product_scores、enriched_products、post_logs。
        created_at/updated_atは状態追跡と監査のためここで付与する。
        """
        doc_id = doc_id or str(uuid.uuid4())
        now = self.now_iso()
        payload = dict(data)
        payload.setdefault("created_at", now)
        payload.setdefault("updated_at", now)

        if self.dry_run:
            self.mock_db.setdefault(collection_name, {})[doc_id] = payload
            self._persist_mock_db()
            return doc_id

        self.db.collection(collection_name).document(doc_id).set(payload)
        return doc_id

    def upsert_document(self, collection_name: str, doc_id: str, data: Dict[str, Any]) -> str:
        """同じIDで再実行したい処理のためのupsert。

        バッチ再実行時に同一product_idへ上書きしたいケースを想定している。
        """
        if self.dry_run and doc_id in self.mock_db.get(collection_name, {}):
            self.update_document(collection_name, doc_id, data)
            return doc_id
        return self.add_document(collection_name, data, doc_id=doc_id)

    def update_document(self, collection_name: str, doc_id: str, data: Dict[str, Any]) -> None:
        """既存ドキュメントのstatusや補足情報を更新する。

        MVPではstatusをキューの代わりに使うため、updateは状態遷移の中心になる。
        """
        payload = dict(data)
        payload["updated_at"] = self.now_iso()

        if self.dry_run:
            self.mock_db.setdefault(collection_name, {}).setdefault(doc_id, {}).update(payload)
            self._persist_mock_db()
            return

        self.db.collection(collection_name).document(doc_id).update(payload)

    def get_document(self, collection_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """関連collectionの文脈を1件取得する。

        例: post_candidatesの品質チェック時にproductsのtitleを参照する。
        """
        if self.dry_run:
            data = self.mock_db.get(collection_name, {}).get(doc_id)
            if data is None:
                return None
            return {"id": doc_id, **data}

        doc = self.db.collection(collection_name).document(doc_id).get()
        if not doc.exists:
            return None
        return {"id": doc.id, **doc.to_dict()}

    def get_documents_by_status(
        self,
        collection_name: str,
        status: str,
        *,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """status単位で次に処理すべきドキュメントを取得する。

        Cloud Tasks未導入のMVPでは、statusが簡易キューとして機能する。
        """
        return self.query_documents(collection_name, {"status": status}, limit=limit)

    def query_documents(
        self,
        collection_name: str,
        filters: Optional[Dict[str, Any]] = None,
        *,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        filters = filters or {}
        if self.dry_run:
            docs: Iterable[tuple[str, Dict[str, Any]]] = self.mock_db.get(collection_name, {}).items()
            results = [
                {"id": doc_id, **data}
                for doc_id, data in docs
                if all(data.get(key) == value for key, value in filters.items())
            ]
            return results[:limit] if limit else results

        query: Any = self.db.collection(collection_name)
        for key, value in filters.items():
            query = query.where(key, "==", value)
        if limit:
            query = query.limit(limit)
        return [{"id": doc.id, **doc.to_dict()} for doc in query.stream()]
