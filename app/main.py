import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from fastapi import Depends, FastAPI, HTTPException, Request, status
from litellm import acompletion, token_counter

from app.auth import verify_api_key
from app.log import get_usage, init_db, log_usage
from app.rate_limiter import token_budget_limiter



# load_dotenv()

ALLOWED_MODELS = {
    model.strip()
    for model in os.getenv("ALLOWED_MODELS", "").split(",")
    if model.strip()
}

PRIMARY_MODEL = os.getenv("PRIMARY_MODEL", "gpt-4o-mini")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "gemini/gemini-2.5-flash-lite")


UNNECESSARY_CLIENT_FIELDS = ("api_key", "api_base", "base_url", "stream")

app = FastAPI(
    title="LLM Gateway",
    description="Minimal gateway: virtual keys, budgets, usage logging, fallback.",
)


@app.on_event("startup")
def _startup():
    init_db()


def _provider_for(model: str) -> str:
    return "gemini" if model.startswith("gemini/") else "openai"


@app.post("/v1/chat/completions")
async def chat_completion(request: Request, api_key: str = Depends(verify_api_key)):
    data = await request.json()

    for field in UNNECESSARY_CLIENT_FIELDS:
        data.pop(field, None)

    messages = data.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="`messages` is required")

    max_tokens = data.get("max_tokens", 1024)
    temperature = data.get("temperature")

    requested_model = data.get("model") or PRIMARY_MODEL
    if requested_model not in ALLOWED_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported model: {requested_model}",
        )

    attempts = [requested_model]
    if requested_model != FALLBACK_MODEL:
        attempts.append(FALLBACK_MODEL)
    else:
        attempts.append(PRIMARY_MODEL)    

    last_error: Optional[Exception] = None

    for model in attempts:
        prompt_tokens = token_counter(model=model, messages=messages)
        estimated_tokens = prompt_tokens + max_tokens

        await token_budget_limiter.check_and_increment(api_key, estimated_tokens)

        try:
            response = await acompletion(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=False,
            )

            usage = getattr(response, "usage", None)
            actual_tokens = usage.total_tokens if usage else estimated_tokens
            await token_budget_limiter.reconcile_usage(
                api_key, estimated_tokens, actual_tokens
            )

            log_usage(
                api_key=api_key,
                model=model,
                provider=_provider_for(model),
                prompt_tokens=usage.prompt_tokens if usage else prompt_tokens,
                completion_tokens=usage.completion_tokens if usage else None,
                total_tokens=actual_tokens,
                status="success",
            )
            return response

        except Exception as e:
            
            await token_budget_limiter.reconcile_usage(api_key, estimated_tokens, 0)
            log_usage(
                api_key=api_key,
                model=model,
                provider=_provider_for(model),
                prompt_tokens=prompt_tokens,
                completion_tokens=0,
                total_tokens=0,
                status="error",
                error=str(e)[:300],
            )
            last_error = e
            continue

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"All providers failed. Last error: {last_error}",
    )


# @app.get("/usage")
# async def usage(key: str):
#     """Barebones admin endpoint: GET /usage?key=<api_key>"""
#     if key not in VALID_API_KEYS:
#         raise HTTPException(status_code=401, detail="Invalid API key")
#     return get_usage(key)


#returns usage for the specific authenticated llm_gateway api key
@app.get("/usage")
async def usage(api_key: str = Depends(verify_api_key)):
    return get_usage(api_key)


@app.get("/")
@app.get("/health")
async def health():
    return {"status": "ok", "service": "llm-gateway"}
