import logging
from typing import Dict, Any, List
from src.clients.firestore_client import FirestoreClient
from src.clients.threads_client import ThreadsClient
from src.services.compliance import ComplianceService

logger = logging.getLogger(__name__)

class Publisher:
    def __init__(self, db: FirestoreClient, threads: ThreadsClient):
        self.db = db
        self.threads = threads

    def publish_queued_posts(self) -> None:
        queued_posts = self.db.get_documents_by_status("post_candidates", "queued")
        logger.info(f"Found {len(queued_posts)} posts to publish.")

        for post in queued_posts:
            try:
                original_text = post.get("post_text", "")
                has_link = "http://" in original_text or "https://" in original_text
                
                # Final compliance check before posting
                final_text, is_rejected = ComplianceService.check_and_format_post(original_text, has_link)

                if is_rejected:
                    logger.warning(f"Post {post['id']} rejected during final compliance check.")
                    self.db.update_document("post_candidates", post["id"], {"status": "rejected"})
                    
                    self.db.add_document("post_logs", {
                        "post_candidate_id": post["id"],
                        "success": False,
                        "error_message": "Rejected by compliance rules",
                        "status": "logged"
                    })
                    continue

                # Publish
                result = self.threads.publish_post(final_text)

                if result["success"]:
                    self.db.update_document("post_candidates", post["id"], {"status": "posted"})
                else:
                    self.db.update_document("post_candidates", post["id"], {"status": "failed"})

                log_data = {
                    "post_candidate_id": post["id"],
                    "success": result["success"],
                    "threads_id": result.get("id"),
                    "error_message": result.get("error_message"),
                    "status": "logged"
                }
                self.db.add_document("post_logs", log_data)

            except Exception as e:
                logger.error(f"Error publishing post {post['id']}: {e}")