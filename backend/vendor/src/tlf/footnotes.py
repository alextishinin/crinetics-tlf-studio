"""Build the final footnote text that appears under each table.

Table shells store footnotes as reusable text templates. This file fills in
study-specific placeholders, decides what kind of footnote each line is,
sorts footnotes into the required order, and checks that each one is ready
for a regulatory-style output.

For example, a shell can contain a placeholder for the MedDRA version, and
this module will replace it with the value from the study configuration
before the table is rendered.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from jinja2 import Environment, StrictUndefined

from tlf.validator import (
    FOOTNOTE_ORDER,
    ValidationError,
    validate_footnote_ends_with_period,
    validate_footnote_order,
)


_jinja_env = Environment(undefined=StrictUndefined, autoescape=False)


@dataclass(frozen=True)
class Footnote:
    """A rendered footnote with its classification kind."""
    kind: str  # one of FOOTNOTE_ORDER
    text: str

    def __post_init__(self) -> None:
        if self.kind not in FOOTNOTE_ORDER:
            raise ValidationError(f"Footnote kind {self.kind!r} invalid")


def classify(text: str) -> str:
    """Best-effort classification of a footnote into one of the four kinds."""
    lower = text.lower()
    if "meddra" in lower or "who drug" in lower or "dictionary" in lower:
        return "coding_dictionary"
    # Abbreviations footnotes typically contain "=" between term and meaning
    # without a sentence-style verb.
    if "=" in text and " is defined " not in lower:
        return "abbreviations"
    if "model" in lower or "ancova" in lower or "covariate" in lower:
        return "statistical"
    return "definitions"


def render(template: str, context: dict[str, Any]) -> str:
    """Interpolate a Jinja2 template against the supplied context."""
    tmpl = _jinja_env.from_string(template)
    return tmpl.render(**context)


def render_footnotes(
    templates: Sequence[str],
    *,
    context: dict[str, Any],
    extra: Sequence[tuple[str, str]] = (),
) -> list[Footnote]:
    """Render `templates`, classify each, append `extra` (already classified),
    sort into canonical order, and validate.

    Returns a list of Footnote instances ready for the renderer.
    """
    rendered: list[Footnote] = []
    for tpl in templates:
        text = render(tpl, context).strip()
        if not text:
            continue
        text = _ensure_period(text)
        rendered.append(Footnote(kind=classify(text), text=text))
    for kind, text in extra:
        rendered.append(Footnote(kind=kind, text=_ensure_period(text)))

    ordered = sorted(rendered, key=lambda f: FOOTNOTE_ORDER.index(f.kind))
    # Validate via dict form expected by validator
    validate_footnote_order([{"kind": f.kind} for f in ordered])
    for f in ordered:
        validate_footnote_ends_with_period(f.text)
    return ordered


def render_abbreviations(abbrev: Iterable[tuple[str, str]]) -> str:
    """Format an abbreviations line per spec: lowercase, '=' separator,
    comma-space between terms, single line, ends with a period."""
    parts: list[str] = []
    for term, meaning in abbrev:
        # Lowercase both per the spec
        parts.append(f"{term.lower()} = {meaning.lower()}")
    if not parts:
        return ""
    line = ", ".join(parts)
    return _ensure_period(line)


def _ensure_period(text: str) -> str:
    text = text.rstrip()
    if not text.endswith("."):
        text += "."
    return text


# Detect unresolved Jinja placeholders ({{ x }}) so a misconfigured study
# config fails loudly instead of producing a footer like
# "MedDRA Version {{ meddra_version }}".
_PLACEHOLDER_RE = re.compile(r"\{\{[^}]*\}\}")


def assert_no_unresolved(text: str) -> None:
    if _PLACEHOLDER_RE.search(text):
        raise ValidationError(f"Unresolved placeholder in footnote: {text!r}")
