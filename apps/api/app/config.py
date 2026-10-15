import hashlib
import json
import os
from urllib.parse import urlsplit, urlunsplit

from app.schemas.models import DigestRequest

PROMPT_VERSION = "pipeline-v1"
ENGINE_VERSION = "1.6.1"
MAX_REQUEST_BYTES = 2_000_000


def execution_fingerprint(request: DigestRequest) -> str:
    endpoint = urlsplit(os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))
    public_endpoint = urlunsplit(
        (
            endpoint.scheme,
            (endpoint.hostname or "") + (":" + str(endpoint.port) if endpoint.port else ""),
            endpoint.path,
            "",
            "",
        )
    )
    context = {
        "engine": ENGINE_VERSION,
        "prompt": PROMPT_VERSION,
        "request": request.model_dump(),
        "ai": {
            "configured": bool(os.getenv("LLM_API_KEY")),
            "model": os.getenv("LLM_MODEL", "gpt-4.1-mini"),
            "endpoint": public_endpoint,
        }
        if request.use_ai
        else None,
    }
    return hashlib.sha256(
        json.dumps(context, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
