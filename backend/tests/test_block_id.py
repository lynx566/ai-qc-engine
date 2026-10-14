from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from unittest.mock import patch
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
from core.document.document_schema import BUNDLE_SCHEMA_VERSION
from tests.extract_test_helpers import extract_docx_for_test
from core.document.docx.handlers import build_block_id
from clinical_program_fixtures import (
    prepare_analysis_bundle_for_test as prepare_analysis_bundle,
)
from tests.clinical_program_fixtures import canonical_clinical_program_fields
FIXED_DOC_ID = 'doc_00000000-0000-4000-8000-000000000001'
LEGACY_BLOCK_ID_RE = re.compile('^doc_[0-9a-f-]+-C\\d{4}$|^.+-C\\d{4}$')
LOCAL_BLOCK_ID_RE = re.compile('^[CTFM]\\d{4}$')
SAMPLE = BACKEND_ROOT / "tests" / "fixtures" / "clinical_trial_doc" / "tag_integration" / 'ib_safety_tag_integration_001.docx'

def test_build_block_id_local_format() -> None:
    assert build_block_id('C', 0) == 'C0001'
    assert build_block_id('T', 2) == 'T0003'

@patch('core.document.doc_identity.generate_doc_id', return_value=FIXED_DOC_ID)
def test_extract_bundle_block_ids_local(_mock_gen) -> None:
    bundle = extract_docx_for_test(SAMPLE)
    assert bundle.doc_id == FIXED_DOC_ID
    assert bundle.doc_id.startswith('doc_')
    assert bundle.document_meta.get('bundle_schema_version') == BUNDLE_SCHEMA_VERSION
    assert BUNDLE_SCHEMA_VERSION == '0.2.1'
    all_blocks = bundle.content_blocks + bundle.table_blocks + bundle.format_blocks + bundle.front_matter_blocks
    assert all_blocks
    first = all_blocks[0]
    assert first.block_id == 'C0001'
    assert FIXED_DOC_ID not in first.block_id
    assert bundle.display_name not in first.block_id
    assert bundle.file_name not in first.block_id
    for block in all_blocks:
        assert LOCAL_BLOCK_ID_RE.match(block.block_id), block.block_id
        assert FIXED_DOC_ID not in block.block_id
        assert LEGACY_BLOCK_ID_RE.match(block.block_id) is None

def test_mask_preserves_local_block_ids_from_bundle_dict() -> None:
    """Mask step copies block_id through; no doc_id prefix rewrites."""
    bundle_dict = {'doc_id': FIXED_DOC_ID, 'file_name': 'secret.docx', 'display_name': 'secret', 'file_hash': 'sha256:abc', 'source_type': 'docx', 'document_meta': {'language': 'zh'}, 'content_blocks': [{'block_id': 'C0001', 'kind': 'paragraph', 'text': '测试文本', 'loc': 'p0', 'source_ref': {'source_type': 'docx', 'locator_type': 'paragraph', 'locator_payload': {'para_index': 0}}}], 'table_blocks': [], 'format_blocks': [], 'front_matter_blocks': []}
    result = prepare_analysis_bundle(bundle_dict, profile=None, language='zh', **canonical_clinical_program_fields())
    masked = result.analysis_bundle
    assert masked['doc_id'] == FIXED_DOC_ID
    assert masked['content_blocks'][0]['block_id'] == 'C0001'
    assert FIXED_DOC_ID not in masked['content_blocks'][0]['block_id']
    serialized = json.dumps(masked, ensure_ascii=False)
    assert f'{FIXED_DOC_ID}-C0001' not in serialized
    assert 'secret-C0001' not in serialized
