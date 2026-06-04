"""Naver gateway service.

Implements the contract the cloud worker calls:
    POST /places/{place_id}/main-image
    Authorization: Bearer <GATEWAY_KEY>
    X-Naver-Account-Token: <credential>   # JSON {"loginId","loginPw"} or opaque
    body: { "imageUrl": "<url>" }
"""

import json

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel

from app.config import get_settings
from app.naver import CaptchaRequired, GatewayError, apply_main_image

settings = get_settings()
app = FastAPI(title="SmartPlace Naver Gateway", version="1.0.0")


class ApplyReq(BaseModel):
    imageUrl: str


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "mock": settings.mock}


@app.post("/places/{place_id}/main-image")
def apply_image(
    place_id: str,
    body: ApplyReq,
    authorization: str = Header(default=""),
    x_naver_account_token: str = Header(default=""),
) -> dict[str, bool]:
    # AuthN: the worker must present the shared gateway key.
    if authorization != f"Bearer {settings.key}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid gateway key")

    credential = _parse_credential(x_naver_account_token)

    try:
        apply_main_image(credential, place_id, body.imageUrl)
    except CaptchaRequired as exc:
        # 423 Locked → operator must seed a session; worker will mark fail+retry.
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(exc)) from exc
    except GatewayError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return {"ok": True}


def _parse_credential(raw: str) -> dict:
    """Accepts a JSON {loginId, loginPw} blob or an opaque token string."""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"token": raw}
    except json.JSONDecodeError:
        return {"token": raw}
