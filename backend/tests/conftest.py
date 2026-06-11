"""Shared pytest fixtures: tmp STUDIES_ROOT, FastAPI test client, sample
ADaM parquet files (synthetic), and a mock Anthropic client."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock

import polars as pl
import pytest


# Ensure backend/ is on sys.path so `import main, config, services...` works
# regardless of where pytest was invoked from.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch) -> Iterator[Path]:
    """Isolate every test: fresh STUDIES_ROOT and a stubbed tlf path."""
    studies = tmp_path / "studies"
    studies.mkdir()
    monkeypatch.setenv("STUDIES_ROOT", str(studies))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    # Tests assert on final job states in the submit response, so run jobs
    # synchronously rather than on the background worker thread.
    monkeypatch.setenv("TLF_JOB_EXECUTOR", "inline")
    # Point at the real automation project if present, else a tmp stub.
    repo_root = BACKEND_ROOT.parent.parent
    automation = repo_root / "crinetics-tlf-automation"
    if automation.exists():
        monkeypatch.setenv("TLF_AUTOMATION_PATH", str(automation))
        monkeypatch.setenv("TLF_REGISTRY_PATH", str(automation / "shells" / "registry.yaml"))
        monkeypatch.setenv("TLF_DEFAULT_CONFIG_PATH", str(automation / "config" / "study_config.yaml"))
    else:
        stub = tmp_path / "tlf_stub"
        stub.mkdir()
        (stub / "shells").mkdir()
        (stub / "config").mkdir()
        (stub / "shells" / "registry.yaml").write_text("version: 1\nshells: []\ncolumn_layouts: {}\n")
        (stub / "config" / "study_config.yaml").write_text("study_id: STUB\n")
        monkeypatch.setenv("TLF_AUTOMATION_PATH", str(stub))
        monkeypatch.setenv("TLF_REGISTRY_PATH", str(stub / "shells" / "registry.yaml"))
        monkeypatch.setenv("TLF_DEFAULT_CONFIG_PATH", str(stub / "config" / "study_config.yaml"))

    # Reset the cached settings singleton so the new env vars take effect.
    import config

    config._settings = None
    yield studies


@pytest.fixture
def client():
    """FastAPI test client, lazily imported so env fixtures run first."""
    from fastapi.testclient import TestClient

    # main imports routers which need fresh settings — re-import each time.
    if "main" in sys.modules:
        del sys.modules["main"]
    import main  # noqa: WPS433

    return TestClient(main.app)


# ---------------------------------------------------------------------------
# Synthetic ADaM datasets
# ---------------------------------------------------------------------------

def _make_synthetic_adsl(path: Path) -> None:
    """Tiny ADSL with 6 subjects across 3 arms and the standard analysis flags."""
    df = pl.DataFrame({
        "STUDYID":  ["MOCK01"] * 6,
        "USUBJID":  [f"MOCK01-{i:03d}" for i in range(6)],
        "TRT01P":   ["Drug Low", "Drug Low", "Drug High", "Drug High", "Placebo", "Placebo"],
        "TRT01PN":  [54, 54, 81, 81, 0, 0],
        "TRT01A":   ["Drug Low", "Drug Low", "Drug High", "Drug High", "Placebo", "Placebo"],
        "TRT01AN":  [54, 54, 81, 81, 0, 0],
        "AGE":      [70, 72, 68, 75, 80, 65],
        "SEX":      ["M", "F", "M", "F", "M", "F"],
        "SAFFL":    ["Y"] * 6,
        "ITTFL":    ["Y"] * 6,
        "EFFFL":    ["Y", "Y", "Y", "Y", "Y", "N"],
        "DTHFL":    ["Y", "N", "N", "N", "N", "N"],
        "DISCONFL": ["Y", "N", "N", "N", "N", "Y"],
        "DCDECOD":  ["ADVERSE EVENT", None, None, None, None, "WITHDRAWAL BY SUBJECT"],
    })
    df.write_parquet(path)


@pytest.fixture
def synthetic_data_dir(tmp_path) -> Path:
    """Return a directory with a small synthetic ADSL parquet."""
    d = tmp_path / "uploaded_data"
    d.mkdir()
    _make_synthetic_adsl(d / "adsl.parquet")
    return d


# ---------------------------------------------------------------------------
# Mock Anthropic client
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_anthropic(monkeypatch):
    """Patch the Anthropic client with canned responses.

    Tests can override the .text returned by calling ``mock_anthropic.set_text``.
    """
    holder = {"text": ""}

    class FakeMessages:
        def create(self, **_kwargs):
            msg = MagicMock()
            content = MagicMock()
            content.text = holder["text"]
            msg.content = [content]
            return msg

        def stream(self, **_kwargs):  # context-manager-ish
            class _Stream:
                def __init__(self, text: str):
                    self._text = text

                def __enter__(self):
                    return self

                def __exit__(self, *exc):
                    return False

                def text_stream(self):
                    yield self._text

                def get_final_message(self):
                    msg = MagicMock()
                    content = MagicMock()
                    content.text = self._text
                    msg.content = [content]
                    return msg

            return _Stream(holder["text"])

    fake_client = MagicMock()
    fake_client.messages = FakeMessages()

    def fake_anthropic(*_a, **_kw):
        return fake_client

    monkeypatch.setattr("anthropic.Anthropic", fake_anthropic)

    class Helper:
        @staticmethod
        def set_text(text: str) -> None:
            holder["text"] = text

    return Helper()
