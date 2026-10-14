import {
  adaptFindingReviewState,
  serializeFindingReviewPatch,
} from '@/adapters/finding-review'
import { throwDocumentConsistencyQcResponseError } from '@/api/document-consistency-qc-error'
import type { FindingReviewPatch, FindingReviewStatePayload } from '@/types/finding-review'

const API_BASE = '/api/document-consistency-qc'

export async function fetchFindingReviewState(
  flowRunId: string,
): Promise<FindingReviewStatePayload> {
  const params = new URLSearchParams({
    flow_run_id: flowRunId,
  })
  const response = await fetch(`${API_BASE}/finding-review?${params.toString()}`)
  if (!response.ok) {
    await throwDocumentConsistencyQcResponseError(response, '审阅状态加载失败')
  }
  const payload = await response.json()
  return adaptFindingReviewState(payload)
}

export async function patchFindingReview(
  flowRunId: string,
  findingId: string,
  patch: FindingReviewPatch,
): Promise<FindingReviewStatePayload> {
  const response = await fetch(`${API_BASE}/finding-review`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      flow_run_id: flowRunId,
      finding_id: findingId,
      ...serializeFindingReviewPatch(patch),
    }),
  })
  if (!response.ok) {
    await throwDocumentConsistencyQcResponseError(response, '审阅状态保存失败')
  }
  const payload = await response.json()
  return adaptFindingReviewState(payload)
}
