"""Shared backend configuration loaded from environment variables.

The settings object also injects `<TLF_AUTOMATION_PATH>/src` into sys.path
so that `import tlf.*` works regardless of where the studio is deployed.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

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
        _ensure_tlf_importable(_settings.tlf_automation_path)
        _settings.studies_root.mkdir(parents=True, exist_ok=True)
    return _settings


def _ensure_tlf_importable(automation_path: Path) -> None:
    """Add `<automation_path>/src` to sys.path so `import tlf` works."""
    src = (automation_path / "src").resolve()
    if src.exists() and str(src) not in sys.path:
        sys.path.insert(0, str(src))
