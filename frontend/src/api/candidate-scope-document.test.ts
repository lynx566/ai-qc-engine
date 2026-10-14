import { afterEach, describe, expect, it, vi } from 'vitest'

import { fetchCandidateScopeDocument } from '@/api/candidate-scope-document'
import { DocumentConsistencyQcApiError } from '@/api/document-consistency-qc-error'

describe('fetchCandidateScopeDocument', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('requests runtime document for flow and slot', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          doc_id: 'doc_test',
          file_name: 'sample.docx',
          display_name: 'sample',
          content_blocks: [],
        }),
        { status: 200 },
      ),
    )

    const bundle = await fetchCandidateScopeDocument('flow_1', 'source_a')

    expect(bundle.doc_id).toBe('doc_test')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/candidate-scope/document?flow_run_id=flow_1&slot_id=source_a',
    )
  })

  it('maps failed responses to DocumentConsistencyQcApiError', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ message: 'extract bundle is missing' }), {
        status: 404,
      }),
    )

    await expect(fetchCandidateScopeDocument('flow_1', 'source')).rejects.toBeInstanceOf(
      DocumentConsistencyQcApiError,
    )
  })
})
