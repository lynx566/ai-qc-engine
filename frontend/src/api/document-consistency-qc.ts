import { adaptDocumentConsistencyQcResult } from '@/adapters/document-consistency-qc-result'
import { throwDocumentConsistencyQcResponseError } from '@/api/document-consistency-qc-error'
import type { DocumentConsistencyQcResult } from '@/types/document-consistency-qc'

export { DocumentConsistencyQcApiError } from '@/api/document-consistency-qc-error'

const API_BASE = '/api/document-consistency-qc'

export async function fetchDocumentConsistencyQcResult(
  flowRunId: string,
): Promise<DocumentConsistencyQcResult> {
  const params = new URLSearchParams({
    flow_run_id: flowRunId,
  })
  const response = await fetch(`${API_BASE}/result?${params.toString()}`)
  if (!response.ok) {
    await throwDocumentConsistencyQcResponseError(response, '结果加载失败')
  }
  const payload = await response.json()
  return adaptDocumentConsistencyQcResult(payload)
}
