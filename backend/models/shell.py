"""Pydantic models for the TFL shell registry view."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Conditionality(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    CONDITIONAL = "conditional"


class ShellEntry(BaseModel):
    """One shell as surfaced to the frontend."""
    id: str
    type: str                                 # 'table' | 'figure' | 'generic_layout'
    table_number: str                         # e.g. '14.1.1.1'
    title_line1: str
    title_line2: str
    title_line3: str
    population: str                           # title line 3 normalised
    adam_domains: list[str] = Field(default_factory=list)
    domain_group: str                         # for sidebar grouping
    conditionality: Conditionality
    optional_flag: str | None = None
    selected: bool = False                    # current saved selection state
    available: bool = True                    # false → data missing for this shell
    condition_reason: str | None = None       # tooltip text


class ShellGroup(BaseModel):
    """A grouping shown in the sidebar (one heading)."""
    name: str
    shells: list[ShellEntry]


class ShellListResponse(BaseModel):
    """Shape returned by GET /studies/{id}/shells."""
    groups: list[ShellGroup]
    auto_selected: list[str] = Field(default_factory=list)
    auto_deselected: list[str] = Field(default_factory=list)


class ShellSelections(BaseModel):
    """Body of PUT /studies/{id}/shells.

    The frontend sends back the desired optional_outputs flag map; the
    backend persists into study_config.yaml.
    """
    optional_outputs: dict[str, bool]
