import logging
import requests
from typing import Dict, Any, Optional
from src import config

logger = logging.getLogger(__name__)

class ThreadsClient:
    def __init__(self):
        self.dry_run = config.DRY_RUN
        self.access_token = config.THREADS_ACCESS_TOKEN
        self.user_id = config.THREADS_USER_ID
        self.base_url = "https://graph.threads.net/v1.0"

    def publish_post(self, text: str) -> Dict[str, Any]:
        if self.dry_run:
            logger.info(f"[DRY_RUN] Pretending to post to Threads: {text[:50]}...")
            return {"success": True, "id": "mock_threads_post_id"}
        
        if not self.access_token or not self.user_id:
            logger.error("Threads access token or user ID not configured.")
            return {"success": False, "error_message": "Credentials missing"}

        try:
            # Step 1: Create media container
            create_url = f"{self.base_url}/{self.user_id}/threads"
            payload = {
                "media_type": "TEXT",
                "text": text,
                "access_token": self.access_token
            }
            create_res = requests.post(create_url, data=payload)
            create_res.raise_for_status()
            creation_id = create_res.json().get("id")

            if not creation_id:
                return {"success": False, "error_message": "Failed to get creation ID"}

            # Step 2: Publish media container
            publish_url = f"{self.base_url}/{self.user_id}/threads_publish"
            publish_payload = {
                "creation_id": creation_id,
                "access_token": self.access_token
            }
            publish_res = requests.post(publish_url, data=publish_payload)
            publish_res.raise_for_status()
            
            post_id = publish_res.json().get("id")
            return {"success": True, "id": post_id}

        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if e.response is not None:
                error_msg += f" Response: {e.response.text}"
            logger.error(f"Threads API Error: {error_msg}")
            return {"success": False, "error_message": error_msg}
        except Exception as e:
            logger.error(f"Unexpected error during Threads publish: {e}")
            return {"success": False, "error_message": str(e)}