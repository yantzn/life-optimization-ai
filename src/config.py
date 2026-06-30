import logging
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    pass


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


BASE_DIR = Path(__file__).resolve().parent.parent

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN", "")
THREADS_USER_ID = os.getenv("THREADS_USER_ID", "")
DRY_RUN = _bool_env("DRY_RUN", True)
DEFAULT_HOURLY_VALUE = int(os.getenv("DEFAULT_HOURLY_VALUE", "2000"))
TARGET_PLATFORM = os.getenv("TARGET_PLATFORM", "threads")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOCAL_FIRESTORE_PATH = os.getenv(
    "LOCAL_FIRESTORE_PATH",
    str(BASE_DIR / ".local" / "firestore_mock.json"),
)


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
