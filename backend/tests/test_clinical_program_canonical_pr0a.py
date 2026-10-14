"""Canonical clinical_program_id persistence and prepare inheritance."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
from artifacts.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.schema import validate_assessment_input
from clinical_program_fixtures import (
    prepare_analysis_bundle_for_test as prepare_analysis_bundle,
)
from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.evidence_form_identity import (
    AGGREGATE_EVIDENCE_FORM_ID,
)
from runtime.date_shift_offset import resolve_effective_date_shift_offset_days
from runtime.evidence_source_preparation.clinical_trial_doc.clinical_safety.aggregate_evidence.prepare import run_prepare
from runtime.prepare_analysis import operations as prepare_analysis_operations
from runtime.upstream_privacy_context import resolve_upstream_privacy_runtime_context
from core.document.sentence_index import build_sentences
from scripts.stage_runners import prepare_analysis_runner
from tests.evidence_source_preparation_phase_test_helpers import installed_prepare_phase_kwargs
from tests.route_runtime_test_helpers import (
    persist_route_artifacts_from_coverage,
    write_upstream_route_fixtures,
)
from plugins.clinical_trial_doc.privacy.profile import CLINICAL_TRIAL_DOC_PRIVACY_PROFILE


def _sample_extract_bundle() -> dict:
    block_id = "C0001"
    text = "????????"
    sentences = build_sentences(
        block_id,
        "paragraph",
        raw_text=text,
        normalized_text=text,
    )
    return {
        "doc_id": "ib_001",
        "file_name": "ib_001.docx",
        "file_hash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        "source_type": "docx",
        "document_meta": {"language": "zh"},
        "content_blocks": [
            {
                "block_id": block_id,
                "kind": "paragraph",
                "text": text,
                "normalized_text": text,
                "sentences": [
                    {
                        "sentence_id": sentence.sentence_id,
                        "normalized_text": sentence.normalized_text,
                    }
                    for sentence in sentences
                ],
            }
        ],
        "front_matter_blocks": [],
        "table_blocks": [],
        "format_blocks": [],
    }

def _run_prepare_analysis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, extra_argv: tuple[str, ...]=()) -> Path:
    extract_dir = tmp_path / 'extract' / 'ib_001'
    extract_dir.mkdir(parents=True)
    bundle_path = extract_dir / 'bundle.json'
    bundle_path.write_text(json.dumps(_sample_extract_bundle()), encoding='utf-8')
    monkeypatch.setattr(prepare_analysis_runner, 'PROJECT_ROOT', tmp_path)
    monkeypatch.setattr(prepare_analysis_operations, 'snapshot_git_provenance_before_run', lambda **_: {'git_commit': 'abc', 'git_dirty': False})
    monkeypatch.setattr(sys, 'argv', ['prepare_analysis_runner.py', '--bundle', str(bundle_path), '--language', 'zh', *extra_argv])
    prepare_analysis_runner.main()
    outputs = list((tmp_path / 'runs' / 'prepare_analysis').glob('*/*/analysis_bundle.json'))
    assert len(outputs) == 1
    return outputs[0].parent

def test_prepare_analysis_identity_run_has_no_program_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_dir = _run_prepare_analysis(tmp_path, monkeypatch)
    analysis_bundle = json.loads((run_dir / 'analysis_bundle.json').read_text(encoding='utf-8'))
    summary = json.loads((run_dir / 'run_summary.json').read_text(encoding='utf-8'))
    assert 'clinical_program_id' not in analysis_bundle
    assert 'clinical_program_id_source' not in analysis_bundle
    assert 'clinical_program_id' not in summary.get('stats', {})

def test_prepare_analysis_registry_run_records_program_in_privacy_stats(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _run_prepare_analysis(
        tmp_path,
        monkeypatch,
        extra_argv=(
            '--clinical-program',
            'clinical_program_001',
            '--privacy-detectors',
            'registry',
        ),
    )
    summary = json.loads((run_dir / 'run_summary.json').read_text(encoding='utf-8'))
    assert summary['stats']['clinical_program_id'] == 'clinical_program_001'

def test_prepare_analysis_registry_requires_clinical_program(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit, match='clinical_program_id must be set for registry'):
        _run_prepare_analysis(
            tmp_path,
            monkeypatch,
            extra_argv=('--privacy-detectors', 'registry'),
        )

def test_resolve_effective_date_shift_offset_uses_profile() -> None:
    offset = resolve_effective_date_shift_offset_days(
        profile=CLINICAL_TRIAL_DOC_PRIVACY_PROFILE,
    )
    assert offset == CLINICAL_TRIAL_DOC_PRIVACY_PROFILE.date_shift_offset_days

def test_prepare_inherits_upstream_artifacts_without_program_field(tmp_path: Path) -> None:
    from tests.route_runtime_test_helpers import persist_route_artifacts_from_coverage

    paths = write_upstream_route_fixtures(tmp_path)
    route_out = tmp_path / 'route_out'
    route_result = persist_route_artifacts_from_coverage(coverage_bundle_path=paths['coverage'], block_manifest_path=paths['block_manifest'], doc_meta_bundle_path=paths['doc_meta_bundle'], analysis_bundle_path=paths['analysis'], output_dir=route_out, run_id='pr0a_route')
    prepare_out = tmp_path / 'prepare_out'
    prepare_result = run_prepare(
        **installed_prepare_phase_kwargs(),
        routed_aggregate_bundle_path=route_result.routed_bundle_paths['aggregate'],
        routing_manifest_path=route_result.routing_manifest_path,
        coverage_bundle_path=paths['coverage'],
        block_manifest_path=paths['block_manifest'],
        doc_meta_bundle_path=paths['doc_meta_bundle'],
        analysis_bundle_path=paths['analysis'],
        output_dir=prepare_out,
        evidence_form_id=AGGREGATE_EVIDENCE_FORM_ID,
    )
    assessment_input = json.loads(prepare_result.assessment_input_path.read_text(encoding='utf-8'))
    runtime_context = json.loads((prepare_out / 'assessment_runtime_context.json').read_text(encoding='utf-8'))
    assert 'clinical_program_id' not in assessment_input
    assert runtime_context['schema_version'] == '0.3.0'
    assert 'temporal_context' not in runtime_context
    assert 'clinical_program_id' not in runtime_context
    validate_assessment_input(assessment_input)

def test_upstream_privacy_reads_date_shift_only(tmp_path: Path) -> None:
    analysis_dir = tmp_path / 'analysis'
    analysis_dir.mkdir()
    analysis_bundle = {'analysis_bundle_id': 'prepare_analysis_test'}
    (analysis_dir / 'analysis_bundle.json').write_text(json.dumps(analysis_bundle), encoding='utf-8')
    (analysis_dir / 'run_summary.json').write_text(
        json.dumps(
            {
                'privacy_transform': {
                    'settings': {'date_shift_offset_days': 7},
                }
            }
        ),
        encoding='utf-8',
    )
    upstream = resolve_upstream_privacy_runtime_context(
        analysis_bundle_path=analysis_dir / 'analysis_bundle.json',
        analysis_bundle=analysis_bundle,
    )
    assert upstream.date_shift_offset_days == 7
    assert not hasattr(upstream, 'clinical_program_id')

def test_prepare_analysis_bundle_for_test_identity_has_no_program_on_bundle() -> None:
    result = prepare_analysis_bundle(
        _sample_extract_bundle(),
        language='zh',
    )
    assert 'clinical_program_id' not in result.analysis_bundle

def test_base_tag_prepare_metadata_builds_without_program_resolver() -> None:
    from plugins.clinical_trial_doc.evidence_source_preparation.clinical_safety.aggregate_evidence.preparation import (
        build_aggregate_shared_metadata,
    )

    coverage = {
        'coverage_bundle_id': 'coverage_test',
        'doc_id': 'doc_test',
        'zone_key': 'ib_clinical_safety_zh',
        'file_hash': 'sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
    }
    block_manifest = {'block_manifest_id': 'block_manifest_test'}
    doc_meta_bundle = {'doc_meta_bundle_id': 'doc_meta_test', 'summary': {'protocol_ids': ['Protocol_001']}}

    metadata = build_aggregate_shared_metadata(
        coverage_bundle=coverage,
        block_manifest=block_manifest,
        doc_meta_bundle=doc_meta_bundle,
    )
    assert 'clinical_program_id' not in metadata
