"""Shared backend configuration.

Resolves three things that differ between local development and the
installed desktop app:

  - The tlf library + its shell/config data files. Prefer the vendored copy
    at ``backend/vendor`` (committed, and bundled into the frozen exe); fall
    back to the sibling ``crinetics-tlf-automation`` checkout in dev when the
    vendor dir is absent.
  - Where studies live. In dev: ``./studies`` (or STUDIES_ROOT from .env).
    In the installed app, Program Files is read-only, so per-user data lives
    under ``%APPDATA%\\TLF Studio\\studies``.
  - The Anthropic API key. From .env in dev; from ``%APPDATA%\\TLF Studio``
    in the installed app (written by the first-run screen).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent / ".env"

APP_DIR_NAME = "TLF Studio"
APP_VERSION = "0.10.0"


def is_frozen() -> bool:
    """True when running from a PyInstaller-frozen executable."""
    return bool(getattr(sys, "frozen", False))


def resource_base() -> Path:
    """Base directory for bundled resources (vendor/, etc.).

    Frozen: PyInstaller's extraction dir (``sys._MEIPASS``). Dev: ``backend/``.
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def appdata_dir() -> Path:
    """Per-user app data directory (created on demand)."""
    base = os.environ.get("APPDATA") or os.environ.get("XDG_DATA_HOME") or str(Path.home())
    path = Path(base) / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


class Settings(BaseSettings):
    """Environment-driven configuration."""

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    studies_root: Path = Path("./studies")
    tlf_automation_path: Path = Path("../crinetics-tlf-automation")
    tlf_registry_path: Path = Path("../crinetics-tlf-automation/shells/registry.yaml")
    tlf_default_config_path: Path = Path(
        "../crinetics-tlf-automation/config/study_config.yaml"
    )

    redis_url: str = "redis://localhost:6379/0"

    api_base_url: str = "http://localhost:8000"

    # How generation jobs run: "background" (worker thread; the default —
    # submission returns immediately and the UI polls), "inline" (synchronous,
    # used by the tests), or "celery" (Redis-backed worker).
    tlf_job_executor: str = "background"

    # Comma-separated list of origins allowed to call this API from a
    # browser. The API is unauthenticated and holds study data, so it must
    # NOT be wide open ("*") — any website the user has open could otherwise
    # drive it via drive-by requests to localhost.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        s = Settings()
        _apply_runtime_paths(s)
        if not s.anthropic_api_key:
            s.anthropic_api_key = _load_api_key_fallback()
        # A model chosen in the in-app Settings (stored in AppData) is the
        # authoritative choice — it overrides the .env / built-in default.
        appdata_model = (_appdata_config().get("anthropic_model") or "").strip()
        if appdata_model:
            s.anthropic_model = appdata_model
        _ensure_tlf_importable(s)
        s.studies_root.mkdir(parents=True, exist_ok=True)
        _settings = s
    return _settings


def _apply_runtime_paths(s: Settings) -> None:
    """Point the tlf paths at the vendored library, and (when frozen) move
    per-user storage to %APPDATA%."""
    vendor = resource_base() / "vendor"
    vendor_registry = vendor / "shells" / "registry.yaml"
    vendor_config = vendor / "config" / "study_config.yaml"

    # Prefer the vendored library whenever it is present. Only fall back to
    # the sibling repo (from .env defaults) when there is no vendor dir.
    if vendor_registry.exists():
        s.tlf_registry_path = vendor_registry
        s.tlf_default_config_path = vendor_config
        s.tlf_automation_path = vendor

    if is_frozen():
        # Program Files is read-only — studies must live per-user.
        s.studies_root = appdata_dir() / "studies"


def _ensure_tlf_importable(s: Settings) -> None:
    """Add the tlf source dir to sys.path so ``import tlf`` works.

    Tries the vendored copy first, then the sibling automation checkout.
    """
    candidates = [
        resource_base() / "vendor" / "src",
        Path(s.tlf_automation_path) / "src",
    ]
    for src in candidates:
        src = src.resolve()
        if (src / "tlf").exists():
            if str(src) not in sys.path:
                sys.path.insert(0, str(src))
            return


def _load_api_key_fallback() -> str:
    """Find ANTHROPIC_API_KEY when it isn't set in backend/.env.

    Checks, in order: the per-user AppData config (config.json / .env) used by
    the installed app, then the project-root .env used in development.
    """
    appdata = appdata_dir()
    # 1a. AppData config.json {"anthropic_api_key": "..."}
    cfg_json = appdata / "config.json"
    if cfg_json.exists():
        try:
            data = json.loads(cfg_json.read_text(encoding="utf-8"))
            key = str(data.get("anthropic_api_key", "")).strip()
            if key:
                return key
        except Exception:
            pass
    # 1b / 2. .env files (AppData, then project root)
    for env_path in (appdata / ".env", Path(__file__).parent.parent / ".env"):
        key = _read_env_key(env_path, "ANTHROPIC_API_KEY")
        if key:
            return key
    return ""


def _read_env_key(env_path: Path, name: str) -> str:
    if not env_path.exists():
        return ""
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#") or not line.startswith(f"{name}="):
            continue
        return line.split("=", 1)[1].strip()
    return ""


def _appdata_config() -> dict:
    """Read the per-user config.json (key + model), or {} if missing/invalid."""
    cfg_path = appdata_dir() / "config.json"
    if cfg_path.exists():
        try:
            return json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _write_appdata_config(updates: dict) -> None:
    cfg_path = appdata_dir() / "config.json"
    data = _appdata_config()
    data.update(updates)
    cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def set_api_key(key: str) -> None:
    """Persist the Anthropic API key to the per-user config and apply it live.

    Writes ``%APPDATA%\\TLF Studio\\config.json`` (where the installed app reads
    the key) and updates the cached Settings so the running backend uses the
    new key immediately — no restart needed.
    """
    key = (key or "").strip()
    _write_appdata_config({"anthropic_api_key": key})
    get_settings().anthropic_api_key = key


def set_model(model: str) -> None:
    """Persist the chosen Anthropic model to the per-user config and apply it
    live (the next AI call uses it; no restart needed)."""
    model = (model or "").strip()
    _write_appdata_config({"anthropic_model": model})
    get_settings().anthropic_model = model
