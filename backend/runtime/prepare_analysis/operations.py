"""Canonical Prepare Analysis execution shell shared by CLI and pipeline callers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from artifacts.prepare_analysis import PrepareAnalysisArtifactPaths
from operations.prepare_analysis.contracts import (
    PrepareAnalysisConfigId,
    PrepareAnalysisDomainResolver,
    PrepareAnalysisRequestOptions,
)
from operations.prepare_analysis.registry import PrepareAnalysisConfigRegistry
from steps.prepare_analysis import prepare_analysis_bundle
from runtime.io import load_json
from runtime.prepare_analysis.persistence import (
    PrepareAnalysisArtifactPayloads,
    build_prepare_analysis_artifacts,
    persist_prepare_analysis_artifacts,
    persist_prepare_analysis_failure,
)
from runtime.run_ids import build_session_dir_segment, utc_run_stamp
from runtime.run_index import (
    build_prepare_analysis_index_document,
    resolve_index_root,
    write_run_index,
)
from runtime.run_layout import (
    ANALYSIS_RUN_DIR_LAYOUT,
    build_prepare_analysis_session_run_naming,
    build_stage_run_layout,
    sanitize_run_segment,
)
from runtime.run_provenance import snapshot_git_provenance_before_run


@dataclass(frozen=True)
class PrepareAnalysisExecutionContext:
    project_root: Path
    output_dir: Path | None = None
    run_id: str | None = None
    persist: bool = True
    git_provenance: Mapping[str, str | bool | None] | None = None


@dataclass(frozen=True)
class PrepareAnalysisDocumentResult:
    run_id: str
    source_bundle: dict[str, Any]
    step_result: Any
    artifacts: PrepareAnalysisArtifactPayloads
    paths: PrepareAnalysisArtifactPaths | None
    output_dir: Path | None


@dataclass(frozen=True)
class PrepareAnalysisOperationReport:
    status: str
    documents: tuple[PrepareAnalysisDocumentResult, ...]
    index_path: Path | None
    messages: tuple[str, ...]


def _allocate_session_dir(project_root: Path, stamp) -> Path:
    stage_root = project_root / "runs" / "prepare_analysis"
    stage_root.mkdir(parents=True, exist_ok=True)
    base = build_session_dir_segment(stamp)
    candidate = stage_root / base
    suffix = 1
    while candidate.exists():
        suffix += 1
        candidate = stage_root / f"{base}__{suffix}"
    candidate.mkdir(parents=True)
    return candidate


def _discover_bundle_paths(directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise ValueError(f"bundle_dir must be a directory: {directory}")
    direct = directory / "bundle.json"
    if direct.is_file():
        return [direct.resolve()]
    paths = sorted(
        path.resolve() for path in directory.rglob("bundle.json") if path.is_file()
    )
    if not paths:
        raise ValueError(f"no bundle.json under {directory}")
    return paths


def _load_inputs(
    *,
    bundle: Mapping[str, Any] | None,
    bundle_path: Path | str | None,
    bundle_dir: Path | str | None,
) -> list[tuple[dict[str, Any], Path | None, Path | None, bool]]:
    selected = sum(value is not None for value in (bundle, bundle_path, bundle_dir))
    if selected != 1:
        raise ValueError("pass exactly one of bundle, bundle_path, or bundle_dir")
    if bundle is not None:
        return [(dict(bundle), None, None, False)]
    if bundle_path is not None:
        path = Path(bundle_path).resolve()
        if not path.is_file() or path.name != "bundle.json":
            raise ValueError(f"bundle_path must name bundle.json: {path}")
        return [(load_json(path), path, None, False)]
    return [
        (load_json(path), path, None, False)
        for path in _discover_bundle_paths(Path(bundle_dir).resolve())  # type: ignore[arg-type]
    ]


def _document_output_dir(
    *,
    execution: PrepareAnalysisExecutionContext,
    session_dir: Path,
    layout: Any,
    doc_id: str,
    multi_input: bool,
) -> Path:
    if execution.output_dir is not None:
        root = execution.output_dir.resolve()
        out = root / sanitize_run_segment(doc_id) if multi_input else root
        out.mkdir(parents=True, exist_ok=True)
        return out
    out = layout.artifact_leaf(session_dir)
    out.mkdir(parents=True, exist_ok=True)
    return out


def run_prepare_analysis_operation(
    *,
    execution: PrepareAnalysisExecutionContext,
    prepare_analysis_config_id: PrepareAnalysisConfigId,
    config_registry: PrepareAnalysisConfigRegistry,
    request_options: PrepareAnalysisRequestOptions,
    bundle: Mapping[str, Any] | None = None,
    bundle_path: Path | str | None = None,
    bundle_dir: Path | str | None = None,
    runtime_context_label: str | None = None,
) -> PrepareAnalysisOperationReport:
    """Resolve one explicit static composition and execute the canonical Step."""

    project_root = execution.project_root.resolve()
    stamp = utc_run_stamp()
    session_dir: Path | None = None
    failure_root: Path | None = None
    resolved_operation_run_id = execution.run_id
    try:
        if execution.persist:
            session_dir = (
                execution.output_dir.resolve()
                if execution.output_dir is not None
                else _allocate_session_dir(project_root, stamp)
            )
            session_dir.mkdir(parents=True, exist_ok=True)
            failure_root = session_dir

        git_provenance = (
            dict(execution.git_provenance)
            if execution.git_provenance is not None
            else (
                snapshot_git_provenance_before_run(root=project_root)
                if execution.persist
                else None
            )
        )
        if not isinstance(config_registry, PrepareAnalysisConfigRegistry):
            raise TypeError("config_registry must be a PrepareAnalysisConfigRegistry")
        if not isinstance(request_options, PrepareAnalysisRequestOptions):
            raise TypeError("request_options must be a PrepareAnalysisRequestOptions")
        config = config_registry.resolve(prepare_analysis_config_id)
        resolver = config.domain
        if not isinstance(resolver, PrepareAnalysisDomainResolver):
            raise TypeError(
                "configured domain must satisfy PrepareAnalysisDomainResolver"
            )
        inputs = _load_inputs(
            bundle=bundle,
            bundle_path=bundle_path,
            bundle_dir=bundle_dir,
        )

        results: list[PrepareAnalysisDocumentResult] = []
        index_documents = []
        messages: list[str] = []
        index_root: Path | None = None
        if execution.persist and session_dir is not None:
            index_root = resolve_index_root(
                session_dir=session_dir,
                custom_output_dir=execution.output_dir,
            )

        for bundle_dict, input_bundle, source_docx, write_bundle_copy in inputs:
            resolved_plan = resolver.resolve(
                config=config,
                request_options=request_options,
            )
            context_label = runtime_context_label or str(prepare_analysis_config_id)
            doc_id = str(bundle_dict.get("doc_id") or "unnamed")
            session_name = (
                session_dir.name
                if session_dir is not None
                else build_session_dir_segment(stamp)
            )
            naming = build_prepare_analysis_session_run_naming(
                stamp=stamp,
                context=context_label,
                doc_id=doc_id,
                git_root=project_root,
                session_dir_name=session_name,
            )
            run_id = execution.run_id or naming.run_id
            resolved_operation_run_id = run_id
            layout = build_stage_run_layout(
                stage="prepare_analysis",
                context=context_label,
                doc_id=doc_id,
                stamp=stamp,
                session_dir_name=session_name,
                run_dir_layout=ANALYSIS_RUN_DIR_LAYOUT,
            )
            step_result = prepare_analysis_bundle(
                bundle_dict,
                resolved_plan=resolved_plan,
                analysis_bundle_id=run_id,
            )
            payloads = build_prepare_analysis_artifacts(step_result)
            paths: PrepareAnalysisArtifactPaths | None = None
            out_dir: Path | None = None
            if execution.persist:
                assert session_dir is not None
                out_dir = _document_output_dir(
                    execution=execution,
                    session_dir=session_dir,
                    layout=layout,
                    doc_id=doc_id,
                    multi_input=len(inputs) > 1,
                )
                paths = persist_prepare_analysis_artifacts(
                    payloads=payloads,
                    out_dir=out_dir,
                    run_id=run_id,
                    bundle_dict=bundle_dict,
                    language=str(
                        (bundle_dict.get("document_meta") or {}).get("language") or ""
                    ),
                    input_bundle=input_bundle,
                    source_docx=source_docx,
                    write_bundle_copy=write_bundle_copy,
                    privacy_profile_ref=runtime_context_label,
                    privacy_detectors_configured=list(
                        resolved_plan.requested_detector_ids
                    ),
                    privacy_detectors_used=(
                        list(step_result.mask_result.detectors)
                        if step_result.mask_result is not None
                        else []
                    ),
                    date_shift_offset_days=resolved_plan.date_shift_offset_days,
                    privacy_provenance_stats=resolved_plan.privacy_provenance_stats,
                    plugin_provenance=resolved_plan.provenance_descriptor,
                    git_provenance=git_provenance,
                    paths_base=project_root,
                )
                assert index_root is not None
                index_documents.append(
                    build_prepare_analysis_index_document(
                        analysis_bundle=payloads.analysis_bundle,
                        out_dir=out_dir,
                        index_root=index_root,
                    )
                )
                messages.extend(
                    [
                        f"analysis bundle: {paths.analysis_bundle}",
                        f"block manifest:  {paths.block_manifest}",
                        f"Run summary:     {paths.run_summary}",
                    ]
                )
                if paths.privacy_audit is not None:
                    messages.append(f"privacy audit:   {paths.privacy_audit}")
                if paths.private_audit_bundle is not None:
                    messages.append(f"private audit:   {paths.private_audit_bundle}")
            results.append(
                PrepareAnalysisDocumentResult(
                    run_id=run_id,
                    source_bundle=bundle_dict,
                    step_result=step_result,
                    artifacts=payloads,
                    paths=paths,
                    output_dir=out_dir,
                )
            )

        index_path: Path | None = None
        if execution.persist and index_documents:
            assert index_root is not None
            index_path = write_run_index(
                index_root,
                step="prepare_analysis",
                documents=index_documents,
                run_id=resolved_operation_run_id,
            )
            messages.append(f"Session index: {index_path}")
        return PrepareAnalysisOperationReport(
            status="success",
            documents=tuple(results),
            index_path=index_path,
            messages=tuple(messages),
        )
    except Exception as exc:
        if execution.persist and failure_root is not None:
            persist_prepare_analysis_failure(
                output_dir=failure_root,
                run_id=resolved_operation_run_id,
                error=exc,
            )
        raise


__all__ = [
    "PrepareAnalysisDocumentResult",
    "PrepareAnalysisExecutionContext",
    "PrepareAnalysisOperationReport",
    "run_prepare_analysis_operation",
]
