"""Run a TLF aggregation and return the table as structured JSON.

We don't want preview to write an RTF or hit disk. To get at the fully-
formatted TableSpec the tlf library produces, we temporarily monkey-patch
`tlf.renderer.render_table` so it captures the spec instead of writing.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from config import get_settings
from services import generation_service, study_service


def generate_preview(study_id: str, table_id: str) -> dict[str, Any]:
    """Return the table as a JSON-serialisable preview payload:

      {
        title: [..., ..., ...],
        header_text: "...",
        column_headers: [...],
        arm_n_labels: [...],
        body_rows: [[...], ...],
        footnotes: [{"kind": "...", "text": "..."}],
        source: "...",
        page_indicator: "Page x of n",
      }
    """
    from tlf.config import load_shell_registry, load_study_config
    import tlf.renderer as renderer_mod
    from tlf.renderer import TableSpec

    sdir = study_service.study_dir(study_id)
    cfg = load_study_config(sdir / "study_config.yaml")
    settings = get_settings()
    registry = load_shell_registry(settings.tlf_registry_path)
    cfg.adam_path = (sdir / "data").resolve()
    cfg.output_path = (sdir / "outputs").resolve()
    cfg.output_path.mkdir(parents=True, exist_ok=True)

    dispatch = generation_service._dispatchers()
    if table_id not in dispatch:
        raise ValueError(f"Unknown table id: {table_id}")

    spec_box: dict[str, TableSpec | None] = {"spec": None}

    def _capture(spec: TableSpec, **kwargs: Any) -> Path:
        spec_box["spec"] = spec
        return (cfg.output_path / "__preview__.rtf").resolve()

    # Table modules import `render_table` by name (`from tlf.renderer
    # import render_table`), so patching `tlf.renderer.render_table` alone
    # isn't enough — we have to swap the binding in every importer too.
    import importlib

    target_modules = [
        renderer_mod,
        importlib.import_module("tlf.tables.disposition"),
        importlib.import_module("tlf.tables.baseline"),
        importlib.import_module("tlf.tables.exposure"),
        importlib.import_module("tlf.tables.adverse_events"),
        importlib.import_module("tlf.tables.labs"),
        importlib.import_module("tlf.tables.vitals"),
        importlib.import_module("tlf.tables.ecg"),
    ]
    originals: dict[Any, Any] = {}
    for mod in target_modules:
        if hasattr(mod, "render_table"):
            originals[mod] = mod.render_table
            mod.render_table = _capture  # type: ignore[assignment]
    try:
        dispatch[table_id](cfg, registry, run_dt=datetime.now())
    finally:
        for mod, original in originals.items():
            mod.render_table = original

    spec = spec_box["spec"]
    if spec is None:
        raise RuntimeError("No TableSpec was rendered for this shell")
    return _spec_to_json(spec, cfg)


def _spec_to_json(spec: Any, cfg: Any) -> dict[str, Any]:
    return {
        "shell_id": spec.shell_id,
        "title": list(spec.title),
        "header_text": f"Crinetics Pharmaceuticals    {cfg.protocol_number}",
        "column_headers": list(spec.column_headers),
        "arm_n_labels": list(spec.arm_n_labels),
        "body_rows": [list(row) for row in spec.body_rows],
        "footnotes": [{"kind": f.kind, "text": f.text} for f in spec.footnotes],
        "source": cfg.source_code_location,
        "page_indicator": "Page 1 of 1",
    }
