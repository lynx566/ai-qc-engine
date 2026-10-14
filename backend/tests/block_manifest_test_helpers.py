"""Test adapter that supplies the semantic heading projection explicitly."""

from __future__ import annotations

from typing import Any

from artifacts.block_manifest import build_block_manifest as build_artifact
from core.document.structure.analysis_heading_projection import (
    project_analysis_heading_paths,
)


def build_block_manifest(analysis_bundle: dict[str, Any]) -> dict[str, Any]:
    return build_artifact(
        analysis_bundle,
        heading_projection=project_analysis_heading_paths(analysis_bundle),
    )
