"""Run a TLF aggregation and return the table as structured JSON.

We don't want preview to write an RTF or hit disk. To get at the fully-
formatted TableSpec the tlf library produces, we temporarily monkey-patch
`tlf.renderer.render_table` so it captures the spec instead of writing.
"""

from __future__ import annotations

import base64
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import re
from typing import Any, Iterator

from config import get_settings
from services import generation_service, study_service
from services.tlf_runtime import configure_for_study


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
    configure_for_study(cfg, sdir)

    dispatch = generation_service._dispatchers()
    table_id = _coerce_table_id(table_id, dispatch)
    if table_id not in dispatch:
        raise ValueError(f"Unknown table id: {table_id}")

    # Figures (f_* shells) are drawn with matplotlib and saved as a PNG; they
    # never call render_table, so there is no TableSpec to capture. Generate
    # the image and return it as a data URL instead.
    if table_id.startswith("f_"):
        return _figure_preview(table_id, cfg, registry, dispatch)

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


def _figure_preview(
    figure_id: str, cfg: Any, registry: Any, dispatch: dict[str, Any]
) -> dict[str, Any]:
    """Generate a figure to a temp dir and return it as a base64 PNG payload."""
    with tempfile.TemporaryDirectory() as tmp:
        path = dispatch[figure_id](cfg, registry, out_dir=Path(tmp), run_dt=datetime.now())
        png = Path(path)
        if not png.exists() or png.suffix.lower() != ".png":
            raise RuntimeError("Figure generation did not produce a PNG image")
        encoded = base64.b64encode(png.read_bytes()).decode("ascii")

    shell = registry.shells.get(figure_id, {}) if hasattr(registry, "shells") else {}
    title = [
        _preview_text(shell.get("title_line1", "")),
        _preview_text(shell.get("title_line2", "")),
        _preview_text(shell.get("title_line3", "")),
    ]
    return {
        "kind": "figure",
        "shell_id": figure_id,
        "title": title,
        "header_text": _preview_text(
            f"Crinetics Pharmaceuticals    {cfg.protocol_number}"
        ),
        "image": f"data:image/png;base64,{encoded}",
        "source": cfg.source_code_location,
        "page_indicator": "Page 1 of 1",
    }


def _coerce_table_id(table_id: str, dispatch: dict[str, Any]) -> str:
    """Accept old output-derived preview IDs and map them to shell IDs.

    A previous Outputs-page parser produced IDs like
    ``t_NEW_STUDY_Table_14_1_1_1_03JUN2026``. The preview endpoint expects
    registry shell IDs like ``t_14_1_1_1``.
    """
    if table_id in dispatch:
        return table_id

    raw = table_id[2:] if table_id.startswith(("t_", "f_")) else table_id
    match = re.search(r"_(Table|Figure)_([0-9][0-9_.]*[0-9])_\d{2}[A-Z]{3}\d{4}$", raw)
    if not match:
        return table_id

    prefix = "f" if match.group(1) == "Figure" else "t"
    number = match.group(2).replace(".", "_")
    candidate = f"{prefix}_{number}"
    return candidate if candidate in dispatch else table_id


def _spec_to_json(spec: Any, cfg: Any) -> dict[str, Any]:
    return {
        "kind": "table",
        "shell_id": spec.shell_id,
        "title": [_preview_text(t) for t in spec.title],
        "header_text": _preview_text(f"Crinetics Pharmaceuticals    {cfg.protocol_number}"),
        "column_headers": [_preview_text(h) for h in spec.column_headers],
        "arm_n_labels": [_preview_text(n) for n in spec.arm_n_labels],
        "body_rows": [[_preview_text(cell) for cell in row] for row in spec.body_rows],
        "footnotes": [{"kind": f.kind, "text": _preview_text(f.text)} for f in spec.footnotes],
        "source": cfg.source_code_location,
        "page_indicator": "Page 1 of 1",
    }


def _preview_text(value: Any) -> str:
    """Translate RTF-only line controls into browser-preview text."""
    text = str(value)
    return re.sub(r"\\line\s*", "\n", text)
