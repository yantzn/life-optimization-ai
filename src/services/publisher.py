import logging

from src import config
from src.clients.firestore_client import FirestoreClient
from src.clients.threads_client import ThreadsClient
from src.services.compliance import ComplianceService

logger = logging.getLogger(__name__)


class Publisher:
    """approved/queuedの投稿候補をThreadsへ送るservice。

    draft -> approved/queued -> dry_run_posted/posted/failed/rejected の終盤を担当する。
    scheduled_atによる厳密な予約制御、MAX_DAILY_POSTS、MIN_POST_INTERVAL_MINUTESは
    後続のschedule-posts/publish-due-postsで扱う想定。
    """
    def __init__(self, db: FirestoreClient, threads: ThreadsClient):
        self.db = db
        self.threads = threads

    def publish_queued_posts(self, *, limit: int | None = None) -> int:
        """投稿対象をpublishする。

        publish直前に再度ComplianceServiceを通す。人間編集や予約待ちの間に、
        PR表記欠落・URL増加・NG表現混入が起きてもここで止めるため。
        DRY_RUN=trueではThreads APIを呼ばず、post_logsへdry_run_successを残す。
        """
        posts = self.db.get_documents_by_status("post_candidates", "queued", limit=limit)
        posts.extend(self.db.get_documents_by_status("post_candidates", "approved", limit=limit))
        processed = 0

        for post in posts[:limit] if limit else posts:
            text = post.get("post_text", "")
            has_affiliate_or_lp = post.get("post_type") == "affiliate" or "プロフィール" in text or "LP" in text
            final_check = ComplianceService.check_post(
                text,
                has_affiliate_or_lp=has_affiliate_or_lp,
                hook=post.get("hook"),
                auto_fix_pr=False,
            )
            if final_check.status == "rejected":
                self.db.update_document(
                    "post_candidates",
                    post["id"],
                    {
                        "status": "rejected",
                        "rejection_reason": final_check.rejection_reason,
                        "warnings": final_check.warnings,
                    },
                )
                self._log(post["id"], "failed", error_message=final_check.rejection_reason)
                continue

            result = self.threads.publish_post(final_check.text)
            status = "posted" if result.get("success") and not self.threads.dry_run else "dry_run_posted"
            if not result.get("success"):
                status = "failed"
            self.db.update_document("post_candidates", post["id"], {"status": status, "post_text": final_check.text})
            product_id = post.get("product_id")
            if product_id:
                self.db.update_document("products", product_id, {"status": "posted" if status == "posted" else status})
            self._log(
                post["id"],
                result.get("result", "failed"),
                external_post_id=result.get("id"),
                error_message=result.get("error_message"),
            )
            processed += 1
        return processed

    def _log(
        self,
        post_id: str,
        result: str,
        *,
        external_post_id: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """投稿結果をpost_logsへ保存する。

        Cloud LoggingだけでなくFirestoreに残すことで、投稿ID・失敗理由・クリック集計を
        後続のBigQuery/CMS連携へ渡しやすくする。
        """
        self.db.add_document(
            "post_logs",
            {
                "post_id": post_id,
                "platform": config.TARGET_PLATFORM,
                "posted_at": self.db.now_iso(),
                "result": result,
                "external_post_id": external_post_id,
                "error_message": error_message,
                "engagement": {},
                "click_count": 0,
                "status": "logged",
            },
        )
