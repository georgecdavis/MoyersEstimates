import os

def require(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(f"Required environment variable {key!r} is not set.")
    return val

ANTHROPIC_API_KEY: str = require("ANTHROPIC_API_KEY")
APP_PASSWORD: str = require("APP_PASSWORD")
SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-insecure-key-change-in-prod")
ALLOWED_ORIGINS: str = os.environ.get("ALLOWED_ORIGINS", "*")
MAX_UPLOAD_MB: int = int(os.environ.get("MAX_UPLOAD_MB", "100"))
VISION_BATCH_SIZE: int = int(os.environ.get("VISION_BATCH_SIZE", "5"))
CLAUDE_MODEL: str = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")
