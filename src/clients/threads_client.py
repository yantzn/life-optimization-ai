import logging
from typing import Any, Dict, Optional

from src import config

logger = logging.getLogger(__name__)


class ThreadsClient:
    """Threads API投稿を担当するクライアント。

    Threadsのテキスト投稿は container作成 -> publish実行 の2段階。
    DRY_RUN=trueでは実APIを呼ばず、Publisherがpost_logsにdry_run_successを残す。
    access tokenは認証情報なのでログに出さない。
    """

    def __init__(
        self,
        *,
        dry_run: Optional[bool] = None,
        access_token: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        self.dry_run = config.DRY_RUN if dry_run is None else dry_run
        self.access_token = access_token if access_token is not None else config.THREADS_ACCESS_TOKEN
        self.user_id = user_id if user_id is not None else config.THREADS_USER_ID
        self.base_url = "https://graph.threads.net/v1.0"

    def publish_post(self, text: str) -> Dict[str, Any]:
        """Threadsへ1投稿をpublishする。

        DRY_RUN=falseでも認証情報がなければ投稿しない。APIエラーは結果として返し、
        Publisherがpost_logsへ保存することで後から原因を追えるようにする。
        """
        if self.dry_run:
            logger.info("threads_dry_run text_length=%s", len(text))
            return {"success": True, "result": "dry_run_success", "id": None}

        if not self.access_token or not self.user_id:
            # 誤ってDRY_RUN=falseにしても、secretがなければ実投稿しない安全弁。
            return {"success": False, "result": "failed", "error_message": "Threads credentials missing"}

        try:
            creation_id = self._create_text_container(text)
            post_id = self._publish_container(creation_id)
            return {"success": True, "result": "success", "id": post_id}
        except Exception as exc:
            error = str(exc)
            if getattr(exc, "response", None) is not None:
                error = f"{error} response={exc.response.text}"
            logger.error("threads_publish_failed error=%s", error)
            return {"success": False, "result": "failed", "error_message": error}

    def _create_text_container(self, text: str) -> str:
        """Threads APIの1段階目: TEXTコンテナを作成する。"""
        import requests

        response = requests.post(
            f"{self.base_url}/{self.user_id}/threads",
            data={"media_type": "TEXT", "text": text, "access_token": self.access_token},
            timeout=30,
        )
        response.raise_for_status()
        creation_id = response.json().get("id")
        if not creation_id:
            raise RuntimeError("Threads create container response did not include id")
        return str(creation_id)

    def _publish_container(self, creation_id: str) -> str:
        """Threads APIの2段階目: 作成済みコンテナを公開する。"""
        import requests

        response = requests.post(
            f"{self.base_url}/{self.user_id}/threads_publish",
            data={"creation_id": creation_id, "access_token": self.access_token},
            timeout=30,
        )
        response.raise_for_status()
        post_id = response.json().get("id")
        if not post_id:
            raise RuntimeError("Threads publish response did not include id")
        return str(post_id)
