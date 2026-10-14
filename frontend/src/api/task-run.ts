import { adaptTaskRunReadModel } from '@/adapters/task-run'
import { throwDocumentConsistencyQcResponseError } from '@/api/document-consistency-qc-error'
import type { TaskRunReadModel } from '@/types/task-run'

const API_BASE = '/api/clinical-trial-doc-qc'

export async function fetchTaskRun(taskRunId: string): Promise<TaskRunReadModel> {
  const response = await fetch(`${API_BASE}/task-runs/${encodeURIComponent(taskRunId)}`)
  if (!response.ok) {
    await throwDocumentConsistencyQcResponseError(response, '任务加载失败，请重试')
  }
  const payload = await response.json()
  return adaptTaskRunReadModel(payload)
}
