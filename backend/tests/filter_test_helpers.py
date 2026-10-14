from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from artifacts.block_manifest import BLOCK_MANIFEST_FILENAME
from artifacts.coverage_bundle import build_coverage_bundle
from artifacts.prepare_analysis import ANALYSIS_BUNDLE_FILENAME
from core.filtering.jobs import ResolvedFilterJob
from core.filtering.registry import resolve_filter_strategy_for_config
from steps.filter import derive_block_selection_coverage
from tests.block_manifest_test_helpers import build_block_manifest


def resolved_filter_job(config: Any) -> ResolvedFilterJob:
    return ResolvedFilterJob(
        config=config,
        strategy=resolve_filter_strategy_for_config(config),
    )


def write_prepare_analysis_filter_input(
    directory: Path,
    bundle: dict[str, Any],
) -> Path:
    """Persist canonical Filter upstream inputs: analysis_bundle + block_manifest."""
    directory.mkdir(parents=True, exist_ok=True)
    bundle_for_write = dict(bundle)
    analysis_bundle_id = bundle_for_write.get("analysis_bundle_id")
    if not isinstance(analysis_bundle_id, str) or not analysis_bundle_id.strip():
        doc_id = str(bundle_for_write.get("doc_id") or directory.name)
        bundle_for_write["analysis_bundle_id"] = f"prepare_analysis_{doc_id}"
    bundle_path = directory / ANALYSIS_BUNDLE_FILENAME
    bundle_path.write_text(
        json.dumps(bundle_for_write, ensure_ascii=False),
        encoding="utf-8",
    )
    manifest_path = directory / BLOCK_MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(build_block_manifest(bundle_for_write), ensure_ascii=False),
        encoding="utf-8",
    )
    return bundle_path


def build_test_coverage_bundle(
    *,
    block_manifest: dict[str, Any],
    public_filter_result: dict[str, Any],
    zone_key: str,
    filter_run_id: str,
) -> dict[str, Any]:
    """Step-derived selection ledger + artifact envelope (test helper)."""
    coverage = derive_block_selection_coverage(
        block_manifest=block_manifest,
        public_filter_result=public_filter_result,
    )
    return build_coverage_bundle(
        block_manifest=block_manifest,
        coverage=coverage,
        zone_key=zone_key,
        filter_run_id=filter_run_id,
    )
