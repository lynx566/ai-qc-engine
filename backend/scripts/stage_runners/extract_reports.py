from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from application.clinical_trial_doc_consistency_qc.extract_installation import (
    resolve_installed_extract_config_id,
)
from execution_flow.document_processing_sequence import (
    run_document_processing_intake_launch_extract,
)
from runtime.io import load_json
from runtime.run_ids import utc_run_stamp
from runtime.run_layout import build_extract_run_naming
from scripts.stage_runners.common import ensure_project_on_path

RUNS_EXTRACT = PROJECT_ROOT / "runs" / "extract"
RUNS_EXTRACT_DOCX = RUNS_EXTRACT / "docx"
REVIEWS_DIR = RUNS_EXTRACT_DOCX / "reviews"
REPORTS_DIR = RUNS_EXTRACT_DOCX / "reports"

PREVIEW_LIMIT = 3
TEXT_PREVIEW_LEN = 100


def load_extract_test_cases(path: Path) -> dict[str, Any]:
    return load_json(path)


def truncate_text(text: str, limit: int = TEXT_PREVIEW_LEN) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def count_by_kind(blocks: list) -> dict[str, int]:
    counts: dict[str, int] = {}
    for block in blocks:
        counts[block.kind] = counts.get(block.kind, 0) + 1
    return counts


def collect_all_text(bundle) -> str:
    all_blocks = (
        bundle.front_matter_blocks
        + bundle.content_blocks
        + bundle.table_blocks
        + bundle.format_blocks
    )
    return "\n".join(block.normalized_text for block in all_blocks)


def collect_table_ref_candidates(bundle) -> list[str]:
    refs: list[str] = []
    for block in bundle.content_blocks:
        refs.extend(block.meta.get("table_ref_candidates", []))

    seen: set[str] = set()
    out: list[str] = []
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            out.append(ref)
    return out


def check_sample(bundle, expected: dict[str, Any]) -> tuple[bool, list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []

    heading_count = sum(1 for b in bundle.content_blocks if b.kind == "heading")
    table_ref_terms = collect_table_ref_candidates(bundle)
    all_text = collect_all_text(bundle)

    actual = {
        "has_front_matter": len(bundle.front_matter_blocks) > 0,
        "has_toc": bundle.document_meta.get("has_toc", False),
        "has_tables": len(bundle.table_blocks) > 0,
        "has_format_blocks": len(bundle.format_blocks) > 0,
        "heading_blocks": heading_count,
        "content_blocks": len(bundle.content_blocks),
        "table_blocks": len(bundle.table_blocks),
        "format_blocks": len(bundle.format_blocks),
    }

    for key in ["has_front_matter", "has_toc", "has_tables", "has_format_blocks"]:
        if key in expected and actual[key] != expected[key]:
            failures.append(f"{key}: expected={expected[key]}, actual={actual[key]}")

    min_checks = [
        ("min_heading_blocks", heading_count),
        ("min_content_blocks", len(bundle.content_blocks)),
        ("min_table_blocks", len(bundle.table_blocks)),
        ("min_format_blocks", len(bundle.format_blocks)),
    ]

    for key, value in min_checks:
        if key in expected and value < expected[key]:
            failures.append(f"{key}: expected>={expected[key]}, actual={value}")

    for term in expected.get("expected_text_terms", []):
        if term not in all_text:
            failures.append(f"missing expected_text_term: {term}")

    for term in expected.get("expected_toc_terms", []):
        toc_text = "\n".join(
            b.normalized_text for b in bundle.front_matter_blocks if b.kind == "toc"
        )
        if term not in toc_text:
            failures.append(f"missing expected_toc_term: {term}")

    for term in expected.get("expected_table_ref_terms", []):
        if term not in table_ref_terms:
            failures.append(f"missing expected_table_ref_term: {term}")

    for term in expected.get("expected_format_terms", []):
        format_text = "\n".join(b.normalized_text for b in bundle.format_blocks)
        if term not in format_text:
            failures.append(f"missing expected_format_term: {term}")

    if len(bundle.content_blocks) == 0:
        warnings.append("content_blocks is empty")

    return len(failures) == 0, failures, warnings


def render_block_preview(block, index: int) -> list[str]:
    lines = [
        f"[{index}] {block.kind} | {block.loc}",
        f"    text: {truncate_text(block.normalized_text)}",
    ]

    meta_bits: list[str] = []

    if block.meta.get("heading_level") is not None:
        meta_bits.append(f"heading_level={block.meta.get('heading_level')}")

    if block.meta.get("style_name"):
        meta_bits.append(f"style={block.meta.get('style_name')}")

    if block.meta.get("title_candidate"):
        meta_bits.append("title_candidate=True")

    if block.meta.get("table_ref_candidates"):
        meta_bits.append(
            f"table_ref_candidates={block.meta.get('table_ref_candidates')}"
        )

    if meta_bits:
        lines.append(f"    meta: {', '.join(meta_bits)}")

    return lines


def render_block_group(
    name: str, blocks: list, limit: int | None = PREVIEW_LIMIT
) -> list[str]:
    lines: list[str] = [f"### {name} ({len(blocks)})"]

    if not blocks:
        lines.append("_empty_")
        return lines

    shown = blocks if limit is None else blocks[:limit]
    for i, block in enumerate(shown, 1):
        lines.extend(render_block_preview(block, i))

    if limit is not None and len(blocks) > limit:
        lines.append(f"... {len(blocks) - limit} more")

    return lines


def render_bundle_review(
    bundle,
    *,
    title: str,
    limit: int | None = PREVIEW_LIMIT,
    parser_type: str | None = None,
    parser_version: str | None = None,
    bundle_schema_version: str | None = None,
) -> list[str]:
    section = "preview" if limit is not None else "all"
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- doc_id: `{bundle.doc_id}`")
    lines.append(f"- file_name: `{bundle.file_name}`")
    display_name = getattr(bundle, "display_name", None)
    if display_name:
        lines.append(f"- display_name: `{display_name}`")
    lines.append(f"- source_type: `{bundle.source_type}`")
    language = (bundle.document_meta or {}).get("language")
    if language is not None:
        lines.append(f"- language: `{language}`")
    if bundle_schema_version is not None:
        lines.append(f"- bundle_schema_version: {bundle_schema_version}")
    if parser_type is not None or parser_version is not None:
        parser_str = " ".join(filter(None, [parser_type, parser_version]))
        lines.append(f"- parser: {parser_str}")
    lines.append(f"- front_matter_blocks: {len(bundle.front_matter_blocks)}")
    lines.append(f"- content_blocks: {len(bundle.content_blocks)}")
    lines.append(f"- table_blocks: {len(bundle.table_blocks)}")
    lines.append(f"- format_blocks: {len(bundle.format_blocks)}")
    lines.append(f"- content kinds: `{count_by_kind(bundle.content_blocks)}`")
    lines.append(f"- front matter kinds: `{count_by_kind(bundle.front_matter_blocks)}`")
    lines.append(f"- document_meta: `{bundle.document_meta}`")
    lines.append("")
    lines.extend(
        render_block_group(
            f"front_matter_blocks {section}", bundle.front_matter_blocks, limit=limit
        )
    )
    lines.append("")
    lines.extend(
        render_block_group(
            f"content_blocks {section}", bundle.content_blocks, limit=limit
        )
    )
    lines.append("")
    lines.extend(
        render_block_group(f"table_blocks {section}", bundle.table_blocks, limit=limit)
    )
    lines.append("")
    lines.extend(
        render_block_group(
            f"format_blocks {section}", bundle.format_blocks, limit=limit
        )
    )
    return lines


def render_verbose_dump(bundle) -> list[str]:
    lines = ["## Verbose dump"]

    for group_name, blocks in [
        ("front_matter_blocks", bundle.front_matter_blocks),
        ("content_blocks", bundle.content_blocks),
        ("table_blocks", bundle.table_blocks),
        ("format_blocks", bundle.format_blocks),
    ]:
        lines.append(f"### {group_name}")
        for block in blocks:
            lines.append("```json")
            lines.append(json.dumps(asdict(block), ensure_ascii=False, indent=2))
            lines.append("```")

    return lines


def render_sample_report(
    sample: dict[str, Any],
    bundle,
    passed: bool,
    failures: list[str],
    warnings: list[str],
    *,
    verbose: bool,
    parser_version: str | None = None,
) -> list[str]:
    file_name = sample["file"]
    sample_id = sample.get("id", "")
    label = sample.get("label", "")
    focus = sample.get("focus") or []

    lines: list[str] = []
    lines.append("---")
    title = f"{sample_id} | {file_name}" if sample_id else file_name
    lines.append(f"# {'PASS' if passed else 'FAIL'} | {title}")

    if label:
        lines.append(f"**Label:** {label}")
    if focus:
        lines.append(f"**Focus:** {', '.join(focus)}")

    meta = bundle.document_meta
    bs = meta.get("bundle_schema_version")
    pt = meta.get("parser_type")
    pv = meta.get("parser_version") or meta.get("handler_version")
    lines.append("")
    lines.extend(
        render_bundle_review(
            bundle,
            title="Extract Review",
            bundle_schema_version=f"v{bs}" if bs else None,
            parser_type=pt or None,
            parser_version=f"v{pv}" if pv else parser_version,
        )[2:]
    )

    if failures:
        lines.append("")
        lines.append("## Failures")
        for failure in failures:
            lines.append(f"- ❌ {failure}")

    if warnings:
        lines.append("")
        lines.append("## Warnings")
        for warning in warnings:
            lines.append(f"- ⚠️ {warning}")

    if verbose or not passed:
        lines.append("")
        lines.extend(render_verbose_dump(bundle))

    return lines


def run_extract(file_path: Path, *, git_provenance: dict[str, str | bool | None] | None = None):
    sequence = run_document_processing_intake_launch_extract(
        project_root=PROJECT_ROOT,
        source_file=file_path,
        extract_config_id=resolve_installed_extract_config_id(),
        git_provenance=git_provenance,
    )
    return sequence.extract_report.result.document.bundle


def write_single_review(
    file_path: Path,
    *,
    stamp: datetime | None = None,
    git_provenance: dict[str, str | bool | None] | None = None,
) -> Path:
    bundle = run_extract(file_path, git_provenance=git_provenance)
    stamp = stamp or utc_run_stamp()
    naming = build_extract_run_naming(
        stamp=stamp, sample_slug=bundle.doc_id, git_root=PROJECT_ROOT
    )
    session = naming.session_dir_name
    if session is None:
        raise RuntimeError("build_extract_run_naming must set session_dir_name")
    out_dir = REVIEWS_DIR / session
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = bundle.document_meta
    schema_v = meta.get("bundle_schema_version")
    pt = meta.get("parser_type")
    pv = meta.get("parser_version") or meta.get("handler_version")
    stem = naming.artifact_stem or naming.export_dir_name
    out_path = out_dir / f"{stem}_review.md"

    lines = render_bundle_review(
        bundle,
        title=f"Extract Inspect | {file_path.name}",
        limit=None,
        bundle_schema_version=f"v{schema_v}" if schema_v else None,
        parser_type=pt or None,
        parser_version=f"v{pv}" if pv else None,
    )
    lines.append("")
    lines.extend(render_verbose_dump(bundle))
    out_path.write_text("\n".join(lines), encoding="utf-8")

    return out_path


def run_extract_test_cases_report(
    test_cases_path: Path,
    *,
    verbose: bool,
    stamp: datetime | None = None,
    git_provenance: dict[str, str | bool | None] | None = None,
) -> Path:
    stamp = stamp or utc_run_stamp()
    session = stamp.strftime("%Y-%m-%d_%H%M%S")
    report_path = REPORTS_DIR / session / "validate_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    test_cases = load_extract_test_cases(test_cases_path)
    samples = test_cases["samples"]

    ensure_project_on_path()
    from core.document.document_schema import BUNDLE_SCHEMA_VERSION
    from core.document.docx.handlers import DOCX_HANDLERS_VERSION

    report_lines: list[str] = []
    report_lines.append("# Extract Validate Report")
    report_lines.append("")
    report_lines.append(f"- bundle_schema_version: v{BUNDLE_SCHEMA_VERSION}")
    report_lines.append(f"- parser: docx_handlers v{DOCX_HANDLERS_VERSION}")
    report_lines.append(f"- session_dir: {session}")
    report_lines.append(f"- generated_at: {stamp.strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"- test_cases: `{test_cases_path}`")
    report_lines.append(f"- verbose: {verbose}")
    report_lines.append(f"- preview_limit: {PREVIEW_LIMIT}")

    passed_count = 0
    failed_count = 0
    warned_count = 0

    for sample in samples:
        file_path = test_cases_path.parent / sample["file"]
        expected = sample.get("expected", {})

        try:
            bundle = run_extract(file_path, git_provenance=git_provenance)
            passed, failures, warnings = check_sample(bundle, expected)
        except Exception as exc:
            passed = False
            failures = [f"exception: {type(exc).__name__}: {exc}"]
            warnings = []
            bundle = None

        if passed:
            passed_count += 1
        else:
            failed_count += 1

        if warnings:
            warned_count += 1

        if bundle is None:
            report_lines.append("---")
            report_lines.append(f"# FAIL | {sample['file']}")
            for failure in failures:
                report_lines.append(f"- ❌ {failure}")
            continue

        report_lines.extend(
            render_sample_report(
                sample=sample,
                bundle=bundle,
                passed=passed,
                failures=failures,
                warnings=warnings,
                verbose=verbose,
                parser_version=f"v{DOCX_HANDLERS_VERSION}",
            )
        )

    report_lines.insert(1, "")
    report_lines.insert(2, "## Overall")
    report_lines.insert(3, f"- total: {len(samples)}")
    report_lines.insert(4, f"- passed: {passed_count}")
    report_lines.insert(5, f"- failed: {failed_count}")
    report_lines.insert(6, f"- warned: {warned_count}")
    report_lines.insert(7, "")

    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    return report_path
