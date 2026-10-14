from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.doc_meta_paths import resolve_doc_meta_output_dir
from runtime.doc_meta_stage import run_doc_meta_stage
from application.clinical_trial_doc_consistency_qc.doc_meta_installation import (
    resolve_installed_doc_meta_dependencies,
)
from runtime.io import load_json
from runtime.run_ids import utc_run_stamp
from runtime.run_index import (
    build_doc_meta_index_document,
    resolve_index_root,
    write_run_index,
)
from runtime.run_layout import (
    DOC_META_RUN_DIR_LAYOUT,
    allocate_session_dir,
    build_doc_meta_session_run_naming,
    build_stage_run_layout,
    ensure_stage_doc_run_dir,
    output_leaf_name,
    posix_relative,
)
from runtime.run_provenance import snapshot_git_provenance_before_run
from scripts.stage_runners.common import (
    ANALYSIS_BUNDLE_FILENAME,
    ensure_project_on_path,
    resolve_artifact_dir,
    resolve_artifact_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "doc_meta stage: extract document-level doc_meta_bundle from "
            "analysis_bundle.json only (not extract bundle)."
        )
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--analysis-bundle",
        help="Path to one analysis_bundle.json",
    )
    input_group.add_argument(
        "--analysis-bundle-dir",
        metavar="DIR",
        help="Directory containing analysis_bundle.json under run subdirectories",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Optional output directory (default: "
            "runs/doc_meta/<run_id>/doc_<doc_id>/)"
        ),
    )
    return parser.parse_args()


def main() -> None:
    ensure_project_on_path()
    args = parse_args()

    if args.analysis_bundle:
        bundle_paths = [
            resolve_artifact_file(
                args.analysis_bundle,
                filename=ANALYSIS_BUNDLE_FILENAME,
                flag_name="--analysis-bundle",
            )
        ]
    else:
        bundle_paths = resolve_artifact_dir(
            args.analysis_bundle_dir,
            filename=ANALYSIS_BUNDLE_FILENAME,
            flag_name="--analysis-bundle-dir",
        )

    stamp = utc_run_stamp()
    git_prov = snapshot_git_provenance_before_run(root=PROJECT_ROOT)
    multi_input = len(bundle_paths) > 1
    doc_meta = resolve_installed_doc_meta_dependencies()

    session_dir: Path | None = None
    index_root: Path
    if args.output_dir:
        index_root = resolve_doc_meta_output_dir(
            args.output_dir,
            anchor_root=PROJECT_ROOT,
        )
    else:
        session_dir = allocate_session_dir(
            PROJECT_ROOT / "runs",
            stage="doc_meta",
            context="",
            stamp=stamp,
            run_dir_layout=DOC_META_RUN_DIR_LAYOUT,
        )
        index_root = resolve_index_root(session_dir=session_dir)

    index_documents = []
    session_run_id: str | None = None

    for analysis_bundle_path in bundle_paths:
        bundle_dict = load_json(analysis_bundle_path)
        doc_id = output_leaf_name(analysis_bundle_path, bundle_dict)

        if args.output_dir:
            out_dir = resolve_doc_meta_output_dir(
                args.output_dir,
                anchor_root=PROJECT_ROOT,
            )
            naming = build_doc_meta_session_run_naming(
                stamp=stamp,
                context=doc_id,
                doc_id=doc_id,
                git_root=PROJECT_ROOT,
            )
        else:
            assert session_dir is not None
            layout = build_stage_run_layout(
                stage="doc_meta",
                context=doc_id,
                doc_id=doc_id,
                stamp=stamp,
                session_dir_name=session_dir.name,
                run_dir_layout=DOC_META_RUN_DIR_LAYOUT,
            )
            naming = build_doc_meta_session_run_naming(
                stamp=stamp,
                context=doc_id,
                doc_id=doc_id,
                git_root=PROJECT_ROOT,
                session_dir_name=session_dir.name,
            )
            session_run_id = layout.run_id
            out_dir = ensure_stage_doc_run_dir(
                PROJECT_ROOT / "runs",
                layout,
                session_dir=session_dir,
                multi_input=multi_input,
            )

        result = run_doc_meta_stage(
            analysis_bundle_path=analysis_bundle_path,
            analysis_bundle=bundle_dict,
            output_dir=out_dir,
            profile=doc_meta.profile,
            build_summary=doc_meta.summary_builder,
            git_provenance=git_prov,
            run_id=naming.run_id,
        )

        rel_analysis = posix_relative(analysis_bundle_path, PROJECT_ROOT)
        print(f"input analysis bundle: {rel_analysis}")
        print(f"output dir:        {result['output_dir']}")
        print(f"doc_meta_bundle:   {result['doc_meta_bundle_path']}")
        print(f"context preview:   {result['document_context_preview_path']}")
        print(f"run summary:       {result['run_summary_path']}")

        index_documents.append(
            build_doc_meta_index_document(
                bundle=bundle_dict,
                out_dir=out_dir,
                index_root=index_root,
            )
        )

    if index_documents and session_dir is not None:
        index_path = write_run_index(
            index_root,
            step="doc_meta",
            documents=index_documents,
            run_id=session_run_id,
        )
        print(f"Session index:     {index_path}")


if __name__ == "__main__":
    main()
