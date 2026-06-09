"""App settings — Anthropic API key + version, for the in-app Settings page."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from config import APP_VERSION, get_settings, set_api_key


router = APIRouter(prefix="/api/settings", tags=["settings"])


class ApiKeyUpdate(BaseModel):
    api_key: str


class SettingsInfo(BaseModel):
    key_present: bool
    key_masked: str
    model: str
    app_version: str


class ApiKeySaveResult(BaseModel):
    saved: bool
    key_present: bool
    valid: bool
    message: str


def _mask(key: str) -> str:
    key = key or ""
    if len(key) <= 12:
        return "set" if key else ""
    return f"{key[:7]}…{key[-4:]}"


@router.get("", response_model=SettingsInfo)
def get_settings_info() -> SettingsInfo:
    s = get_settings()
    key = s.anthropic_api_key or ""
    return SettingsInfo(
        key_present=bool(key),
        key_masked=_mask(key),
        model=s.anthropic_model,
        app_version=APP_VERSION,
    )


@router.post("/api-key", response_model=ApiKeySaveResult)
def update_api_key(payload: ApiKeyUpdate) -> ApiKeySaveResult:
    key = (payload.api_key or "").strip()
    set_api_key(key)
    if not key:
        return ApiKeySaveResult(
            saved=True, key_present=False, valid=False, message="API key cleared."
        )
    valid, message = _validate_key()
    return ApiKeySaveResult(saved=True, key_present=True, valid=valid, message=message)


def _validate_key() -> tuple[bool, str]:
    """Confirm the saved key works with a tiny Claude call (2 tokens)."""
    s = get_settings()
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=s.anthropic_api_key)
        client.messages.create(
            model=s.anthropic_model,
            max_tokens=2,
            messages=[{"role": "user", "content": "hi"}],
        )
        return True, "API key saved and verified."
    except Exception as exc:  # noqa: BLE001 - surface a friendly hint
        name = type(exc).__name__
        if "Authentication" in name or "401" in str(exc):
            return False, "Saved, but the key was rejected. Check it's correct."
        return False, f"Saved, but couldn't verify ({name}). Check your connection."
