import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Header, HTTPException

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Comma-separated gateway keys, e.g. "sk-user-1,sk-user-2,sk-user-3,sk-user-4,sk-user-5"
ALLOWED_API_KEYS_ENV = os.getenv("ALLOWED_API_KEYS", "")
VALID_API_KEYS = {k.strip() for k in ALLOWED_API_KEYS_ENV.split(",") if k.strip()}

def verify_api_key(x_api_key: str = Header(None, alias ="x-api-key")) -> str:
    if not x_api_key or x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code  = 401, detail="Invalid/missing API key")
    return x_api_key
