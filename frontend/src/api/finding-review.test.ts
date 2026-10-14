import { afterEach, describe, expect, it, vi } from 'vitest'

import { clearFindingReviewNotePatch } from '@/adapters/finding-review'
import { patchFindingReview } from '@/api/finding-review'

describe('patchFindingReview', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('sends explicit note empty string when clearing note', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          flow_run_id: 'document_consistency_qc_test',
          findings: {
            N1: {
              finding_id: 'N1',
              decision: 'pending',
              marked: true,
              updated_at: '2026-09-13T00:00:00Z',
            },
          },
        }),
        { status: 200 },
      ),
    )

    await patchFindingReview('document_consistency_qc_test', 'N1', clearFindingReviewNotePatch())

    expect(fetchMock).toHaveBeenCalledOnce()
    const [, requestInit] = fetchMock.mock.calls[0]!
    expect(JSON.parse(String(requestInit?.body))).toEqual({
      flow_run_id: 'document_consistency_qc_test',
      finding_id: 'N1',
      note: '',
    })
  })

  it('does not include note when patch omits note field', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          flow_run_id: 'document_consistency_qc_test',
          findings: {},
        }),
        { status: 200 },
      ),
    )

    await patchFindingReview('document_consistency_qc_test', 'N1', { decision: 'confirmed' })

    const [, requestInit] = fetchMock.mock.calls[0]!
    expect(JSON.parse(String(requestInit?.body))).toEqual({
      flow_run_id: 'document_consistency_qc_test',
      finding_id: 'N1',
      decision: 'confirmed',
    })
  })
})
