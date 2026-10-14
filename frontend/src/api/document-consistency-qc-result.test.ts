import { afterEach, describe, expect, it, vi } from 'vitest'

import { fetchDocumentConsistencyQcResult } from '@/api/document-consistency-qc'
import { DocumentConsistencyQcApiError } from '@/api/document-consistency-qc-error'

const rawPayload = {
  flow_id: 'document_consistency_qc',
  flow_run_id: 'document_consistency_qc_test',
  capability_id: 'internal_dsur',
  flow_status: 'success',
  comparison_run_status: 'success',
  finalization_status: 'completed',
  fallback_comparison_modes: [],
  findings: [],
  scope_results: [
    {
      slot_id: 'source',
      doc_id: 'doc_test',
      scope_id: 'HS0001',
      heading_path: ['4. 临床安全性'],
      outline_heading_block_id: 'C0030',
      semantic_module_id: 'clinical_safety',
      execution_status: 'complete',
      has_successful_check: true,
    },
  ],
}

describe('fetchDocumentConsistencyQcResult', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('requests result endpoint with flow_run_id only', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(rawPayload), { status: 200 }),
    )

    const result = await fetchDocumentConsistencyQcResult('document_consistency_qc_test')

    expect(result.flowRunId).toBe('document_consistency_qc_test')
    expect(result.scopeResults[0].outlineHeadingBlockId).toBe('C0030')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/document-consistency-qc/result?flow_run_id=document_consistency_qc_test',
    )
  })

  it('maps failed responses to DocumentConsistencyQcApiError', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ message: 'result is unavailable' }), {
        status: 400,
      }),
    )

    await expect(
      fetchDocumentConsistencyQcResult('document_consistency_qc_test'),
    ).rejects.toBeInstanceOf(DocumentConsistencyQcApiError)
  })

  it('does not convert API failure into an empty result', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ message: 'result is unavailable' }), {
        status: 404,
      }),
    )

    await expect(fetchDocumentConsistencyQcResult('missing_flow')).rejects.toThrow(
      'result is unavailable',
    )
  })
})
