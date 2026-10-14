from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
from artifacts.block_manifest import assert_block_manifest_safe, build_block_manifest_id
from clinical_program_fixtures import (
    prepare_analysis_bundle_for_test as prepare_analysis_bundle,
)
from tests.block_manifest_test_helpers import build_block_manifest
from tests.clinical_program_fixtures import canonical_clinical_program_fields
from tests.extract_test_helpers import extract_docx_for_test
from tests.filter_test_helpers import build_test_coverage_bundle
from tests.route_test_fixtures import _route_units

_FORBIDDEN_SUBSTRINGS = ('normalized_text', 'span_map', 'source_ref', 'document_meta', 'privacy_transforms')
SAFETY_SAMPLE = BACKEND_ROOT / "tests" / "fixtures" / "clinical_trial_doc" / "legacy_ib_v1_0" / 'OOJ-VT8802-01 艾美妥珠单抗研究者手册 V1.0 2024.03.15.docx'
LINEAGE_FILE_HASH = 'sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef'


def _identity_span_map_entry(
    *,
    normalized_text: str,
    analysis_text: str,
) -> dict:
    return {
        'mapping_type': 'identity',
        'analysis_start': 0,
        'analysis_end': len(analysis_text),
        'analysis_text': analysis_text,
        'normalized_start': 0,
        'normalized_end': len(normalized_text),
        'normalized_text': normalized_text,
        'meta': None,
    }


def _identity_sentence_record(
    sentence_id: str,
    *,
    normalized_text: str,
    analysis_text: str,
) -> dict:
    span_entry = _identity_span_map_entry(
        normalized_text=normalized_text,
        analysis_text=analysis_text,
    )
    return {
        'sentence_id': sentence_id,
        'start': 0,
        'end': len(normalized_text),
        'normalized_text': normalized_text,
        'analysis_text': analysis_text,
        'span_map': [span_entry],
    }


def _minimal_analysis_bundle() -> dict:
    c0007_normalized = '六、临床安全性'
    c0008_normalized = '6.1 VT-8802（艾美妥珠单抗）'
    c0008_analysis = '6.1 StudyDrug_001（GenericName_001）'
    c0009_normalized = '累计40例试验参与者接受VT-8802联合顺铂治疗。'
    c0009_analysis = '累计40例试验参与者接受StudyDrug_001联合BackgroundDrug_001治疗。'
    return {
        'analysis_bundle_id': 'prepare_analysis_20260607_180105',
        'doc_id': 'doc_ee52739c-1118-406b-bd0f-9d5e1b2a98e9',
        'file_hash': LINEAGE_FILE_HASH,
        'file_name': 'sample.docx',
        'source_type': 'docx',
        'stage': 'prepare_analysis',
        'pipeline': ['extract', 'prepare_analysis'],
        'privacy_enabled': True,
        'document_meta': {'language': 'zh'},
        'privacy_transforms': {'after_extract': {'applied': True}},
        'content_blocks': [
            {
                'block_id': 'C0007',
                'kind': 'heading',
                'loc': 'BODY:HDG:P7',
                'order': 7,
                'meta': {
                    'heading_level': 1,
                    'heading_number': None,
                    'table_ref_candidates': [],
                },
                'normalized_text': c0007_normalized,
                'analysis_text': c0007_normalized,
                'source_ref': {'source_type': 'docx'},
                'span_map': [],
                'sentences': [
                    _identity_sentence_record(
                        'C0007:S001',
                        normalized_text=c0007_normalized,
                        analysis_text=c0007_normalized,
                    )
                ],
            },
            {
                'block_id': 'C0008',
                'kind': 'heading',
                'loc': 'BODY:HDG:P8',
                'order': 8,
                'meta': {
                    'heading_level': 2,
                    'heading_number': '6.1',
                    'table_ref_candidates': [],
                },
                'normalized_text': c0008_normalized,
                'analysis_text': c0008_analysis,
                'source_ref': {'source_type': 'docx'},
                'span_map': [],
                'sentences': [
                    _identity_sentence_record(
                        'C0008:S001',
                        normalized_text=c0008_normalized,
                        analysis_text=c0008_analysis,
                    )
                ],
            },
            {
                'block_id': 'C0009',
                'kind': 'paragraph',
                'loc': 'BODY:P9',
                'order': 9,
                'meta': {'heading_level': None, 'table_ref_candidates': []},
                'normalized_text': c0009_normalized,
                'analysis_text': c0009_analysis,
                'source_ref': {'source_type': 'docx'},
                'span_map': [],
                'sentences': [
                    _identity_sentence_record(
                        'C0009:S001',
                        normalized_text=c0009_normalized,
                        analysis_text=c0009_analysis,
                    )
                ],
            },
        ],
    }


def _analysis_bundle_with_raw_table_heading_path() -> dict:
    bundle = _minimal_analysis_bundle()
    for block in bundle['content_blocks']:
        block['doc_order_index'] = block['order']
        if block['block_id'] == 'C0008':
            c0008_normalized = '6.1 VT8802 I期研究'
            c0008_analysis = '6.1 StudyDrug_001 I期研究'
            block['normalized_text'] = c0008_normalized
            block['analysis_text'] = c0008_analysis
            block['sentences'] = [
                _identity_sentence_record(
                    'C0008:S001',
                    normalized_text=c0008_normalized,
                    analysis_text=c0008_analysis,
                )
            ]
    bundle['table_blocks'] = [
        {
            'block_id': 'T0001',
            'kind': 'table',
            'doc_order_index': 10,
            'heading_path': ['六、临床安全性', '6.1 VT8802 I期研究'],
            'normalized_text': 'SOC | n\nADR | 1',
            'analysis_text': 'SOC | n\nADR | 1',
            'text': 'SOC | n\nADR | 1',
            'meta': {'row_count': 2, 'column_count': 2},
        }
    ]
    return bundle

def _zone_result_including_table(*, block_id: str='T0001') -> dict:
    return {'matched_zones': [{'zone_id': 'Z_SAFETY', 'match': {'match_type': 'heading', 'matched_term': '临床安全性', 'matched_heading_block_id': 'C0007'}, 'blocks': [], 'table_blocks': [{'block_id': block_id}]}]}

def _minimal_doc_meta_bundle(*, doc_id: str) -> dict:
    return {'doc_meta_bundle_id': 'doc_meta_test', 'doc_id': doc_id, 'file_hash': LINEAGE_FILE_HASH, 'summary': {'doc_type': 'IB', 'study_drug': 'StudyDrug_001'}}

def _coverage_row_heading_path(coverage_bundle: dict, block_id: str) -> list[str]:
    for row in coverage_bundle['coverage']:
        if row['block_id'] == block_id:
            return list(row['heading_path'])
    raise AssertionError(f'missing coverage row {block_id!r}')

def test_table_heading_path_uses_masked_content_headings() -> None:
    bundle = _analysis_bundle_with_raw_table_heading_path()
    result = build_block_manifest(bundle)
    t0001 = _table_block_by_id(result, 'T0001')
    c0008 = _block_by_id(result, 'C0008')
    assert t0001['heading_path'] == c0008['heading_path']
    assert 'StudyDrug_001' in t0001['heading_path'][-1]
    assert 'VT8802' not in json.dumps(t0001['heading_path'], ensure_ascii=False)
    assert 'VT8802' not in json.dumps(result['table_blocks'], ensure_ascii=False)

def test_table_heading_path_propagates_to_coverage_and_route_unit() -> None:
    bundle = _analysis_bundle_with_raw_table_heading_path()
    block_manifest = build_block_manifest(bundle)
    coverage_bundle = build_test_coverage_bundle(block_manifest=block_manifest, public_filter_result=_zone_result_including_table(), zone_key='ib_clinical_safety_zh', filter_run_id='filter_table_heading_privacy_test')
    routed = _route_units(coverage=coverage_bundle, manifest=block_manifest)
    coverage_path = _coverage_row_heading_path(coverage_bundle, 'T0001')
    assert 'StudyDrug_001' in coverage_path[-1]
    assert 'VT8802' not in json.dumps(coverage_path, ensure_ascii=False)
    table_units = routed.units_by_route['table']
    assert len(table_units) == 1
    assert table_units[0]['heading_path'] == coverage_path
    assert 'VT8802' not in json.dumps(table_units[0], ensure_ascii=False)

def _block_by_id(payload: dict, block_id: str) -> dict:
    for block in payload['blocks']:
        if block['block_id'] == block_id:
            return block
    raise AssertionError(f'missing block {block_id!r}')

def _table_block_by_id(payload: dict, block_id: str) -> dict:
    for block in payload.get('table_blocks') or []:
        if block['block_id'] == block_id:
            return block
    raise AssertionError(f'missing table block {block_id!r}')

def test_build_block_manifest_minimal_fixture() -> None:
    bundle = _minimal_analysis_bundle()
    result = build_block_manifest(bundle)
    assert result['block_manifest_id'] == build_block_manifest_id(analysis_bundle_id=bundle['analysis_bundle_id'])
    assert result['block_manifest_id'] == 'block_manifest_prepare_analysis_20260607_180105'
    assert result['doc_id'] == bundle['doc_id']
    assert result['file_hash'] == bundle['file_hash']
    assert result['analysis_bundle_ref'] == {'analysis_bundle_id': 'prepare_analysis_20260607_180105'}
    assert result['table_blocks'] == []
    for block in result['blocks']:
        assert block['text_ref'] == {'analysis_bundle_id': 'prepare_analysis_20260607_180105', 'block_id': block['block_id']}
    c0007 = _block_by_id(result, 'C0007')
    c0008 = _block_by_id(result, 'C0008')
    c0009 = _block_by_id(result, 'C0009')
    assert c0007['heading_path'] == ['六、临床安全性']
    assert c0008['heading_path'] == ['六、临床安全性', '6.1 StudyDrug_001（GenericName_001）']
    assert c0009['heading_path'] == c0008['heading_path']
    assert c0008['heading_number'] == '6.1'
    assert c0009['heading_number'] is None
    assert 'StudyDrug_001' in c0008['analysis_text']
    assert 'StudyDrug_001' in c0009['analysis_text']
    assert 'VT-8802' not in c0008['analysis_text']
    assert 'VT-8802' not in c0009['analysis_text']
    for src_block in bundle['content_blocks']:
        out_block = _block_by_id(result, src_block['block_id'])
        assert out_block['analysis_text'] == src_block['analysis_text']
    serialized = json.dumps(result, ensure_ascii=False)
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert forbidden not in serialized
    assert_block_manifest_safe(result)

def test_build_block_manifest_includes_table_blocks_from_safety_sample() -> None:
    bundle = extract_docx_for_test(SAFETY_SAMPLE)
    analysis = prepare_analysis_bundle(asdict(bundle), profile=None, language='zh', **canonical_clinical_program_fields())
    analysis_bundle = dict(analysis.analysis_bundle)
    analysis_bundle['analysis_bundle_id'] = 'prepare_analysis_test'
    result = build_block_manifest(analysis_bundle)
    t0001 = _table_block_by_id(result, 'T0001')
    assert t0001['kind'] == 'table'
    assert t0001['text']
    assert t0001['doc_order_index'] is not None
    assert any('临床安全性' in item for item in t0001['heading_path'])
    assert any('6.1' in item for item in t0001['heading_path'])
    assert t0001['meta']['row_count'] == 10
    assert t0001['meta']['column_count'] == 3
    assert 'analysis_text' not in t0001
    c0009 = _block_by_id(result, 'C0009')
    assert t0001['heading_path'] == c0009['heading_path']
    table_indices = [block['doc_order_index'] for block in result['table_blocks'] if block.get('doc_order_index') is not None]
    assert table_indices == sorted(table_indices)
    serialized = json.dumps(result, ensure_ascii=False)
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert forbidden not in serialized
    assert_block_manifest_safe(result)

def test_table_meta_drops_raw_rows_and_allows_masked_rows() -> None:
    bundle = {'analysis_bundle_id': 'prepare_analysis_table_meta_hardening', 'doc_id': 'doc_table_meta_hardening', 'file_hash': LINEAGE_FILE_HASH, 'content_blocks': [], 'table_blocks': [{'block_id': 'T0001', 'kind': 'table', 'doc_order_index': 1, 'analysis_text': 'A | B\n1 | 2', 'meta': {'row_count': 2, 'column_count': 2, 'non_empty_row_count': 2, 'raw_rows': [['A', 'B'], ['1', '2']], 'masked_rows': [['A', 'B'], ['1', '<<SUBJECT>>']], 'raw_text_before_normalize': 'A  B  1  2'}}]}
    result = build_block_manifest(bundle)
    table = _table_block_by_id(result, 'T0001')
    meta = table['meta']
    assert 'raw_rows' not in meta
    assert 'raw_text_before_normalize' not in meta
    assert meta['row_count'] == 2
    assert meta['column_count'] == 2
    assert meta['non_empty_row_count'] == 2
    assert meta['masked_rows'] == [['A', 'B'], ['1', '<<SUBJECT>>']]

def test_build_block_manifest_requires_analysis_bundle_id() -> None:
    bundle = _minimal_analysis_bundle()
    bundle.pop('analysis_bundle_id')
    with pytest.raises(ValueError, match='analysis_bundle_id'):
        build_block_manifest(bundle)
