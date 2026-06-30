import logging
from typing import Set

from src.clients.firestore_client import FirestoreClient
from src.clients.gemini_client import GeminiClient
from src.services.compliance import ComplianceService

logger = logging.getLogger(__name__)


class QualityGate:
    """post_candidatesを投稿可能な品質へ振り分けるservice。

    読み: post_candidates(status=draft/generated)
    書き: post_candidates(status=approved/rejected)
    生成直後とpublish直前の両方でチェックする前提。
    """
    def __init__(self, db: FirestoreClient, gemini: GeminiClient):
        self.db = db
        self.gemini = gemini

    def check_quality(self, *, limit: int | None = None) -> int:
        """draft/generated投稿を品質チェックしてapprovedまたはrejectedへ更新する。

        scheduled_atやqueued運用は後続拡張だが、初期運用では人間がapprovedへ進める
        半自動運用を想定している。
        """
        posts = self.db.get_documents_by_status("post_candidates", "draft", limit=limit)
        posts.extend(self.db.get_documents_by_status("post_candidates", "generated", limit=limit))
        processed = 0
        seen_hooks = self._hooks_for_statuses({"approved", "queued", "dry_run_posted", "posted", "rejected"})

        for post in posts[:limit] if limit else posts:
            text = post.get("post_text", "")
            product = self.db.get_document("products", post.get("product_id", "")) or {}
            has_affiliate_or_lp = post.get("post_type") == "affiliate" or "プロフィール" in text or "LP" in text
            result = ComplianceService.check_post(
                text,
                has_affiliate_or_lp=has_affiliate_or_lp,
                hook=post.get("hook"),
                existing_hooks=seen_hooks,
                product_title=product.get("title"),
                auto_fix_pr=False,
            )
            seen_hooks.add(str(post.get("hook", "")))
            self.db.update_document(
                "post_candidates",
                post["id"],
                {
                    "post_text": result.text,
                    "quality_score": result.quality_score,
                    "status": "approved" if result.status == "queued" else result.status,
                    "warnings": result.warnings,
                    "rejection_reason": result.rejection_reason,
                },
            )
            processed += 1
            logger.info("quality_checked post_id=%s status=%s score=%s", post["id"], result.status, result.quality_score)
        return processed

    def _hooks_for_statuses(self, statuses: Set[str]) -> Set[str]:
        hooks: Set[str] = set()
        for status in statuses:
            for post in self.db.get_documents_by_status("post_candidates", status):
                hook = str(post.get("hook", ""))
                if hook:
                    hooks.add(hook)
        return hooks
