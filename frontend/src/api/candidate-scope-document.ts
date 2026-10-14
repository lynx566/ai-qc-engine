import type { ExtractBundleDto } from '@/adapters/extract-bundle.dto'
import { throwDocumentConsistencyQcResponseError } from '@/api/document-consistency-qc-error'

const API_BASE = '/api/candidate-scope'

export async function fetchCandidateScopeDocument(
  flowRunId: string,
  slotId: string,
): Promise<ExtractBundleDto> {
  const params = new URLSearchParams({
    flow_run_id: flowRunId,
    slot_id: slotId,
  })
  const response = await fetch(`${API_BASE}/document?${params.toString()}`)
  if (!response.ok) {
    await throwDocumentConsistencyQcResponseError(response, '文档加载失败')
  }
  return (await response.json()) as ExtractBundleDto
}
