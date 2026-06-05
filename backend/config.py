"""Shared backend configuration loaded from environment variables.

The settings object also injects `<TLF_AUTOMATION_PATH>/src` into sys.path
so that `import tlf.*` works regardless of where the studio is deployed.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent / ".env"


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


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        # The backend reads backend/.env, but users often drop the API key in
        # the project-root .env instead. Fall back to it so either works.
        if not _settings.anthropic_api_key:
            _settings.anthropic_api_key = _api_key_from_root_env()
        _ensure_tlf_importable(_settings.tlf_automation_path)
        _settings.studies_root.mkdir(parents=True, exist_ok=True)
    return _settings


def _api_key_from_root_env() -> str:
    """Read ANTHROPIC_API_KEY from the project-root .env (one level above
    backend/) as a fallback when it isn't set in backend/.env."""
    root_env = Path(__file__).parent.parent / ".env"
    if not root_env.exists():
        return ""
    for raw in root_env.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#") or not line.startswith("ANTHROPIC_API_KEY="):
            continue
        return line.split("=", 1)[1].strip()
    return ""


def _ensure_tlf_importable(automation_path: Path) -> None:
    """Add `<automation_path>/src` to sys.path so `import tlf` works."""
    src = (automation_path / "src").resolve()
    if src.exists() and str(src) not in sys.path:
        sys.path.insert(0, str(src))
