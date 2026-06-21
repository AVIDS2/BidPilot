import os

import httpx
from fastapi import HTTPException, Request, status

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
VERIFY_TIMEOUT_SECONDS = 5.0


def is_turnstile_enabled() -> bool:
    return bool(os.getenv("DOCPILOT_TURNSTILE_SECRET_KEY"))


def verify_turnstile_or_raise(token: str | None, request: Request) -> None:
    secret = os.getenv("DOCPILOT_TURNSTILE_SECRET_KEY")
    if not secret:
        return
    if not token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Human verification is required.",
        )

    remote_ip = _client_ip(request)
    payload = {"secret": secret, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        response = httpx.post(SITEVERIFY_URL, data=payload, timeout=VERIFY_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Human verification is temporarily unavailable.",
        )

    if not data.get("success"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Human verification failed.",
        )


def _client_ip(request: Request) -> str | None:
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None
