import { adaptProductTaskStartResult } from '@/adapters/product-task-start'
import { adaptTaskCatalog } from '@/adapters/task-catalog'
import {
  DocumentConsistencyQcApiError,
  throwDocumentConsistencyQcResponseError,
} from '@/api/document-consistency-qc-error'
import type { ProductTaskStartResult } from '@/types/clinical-trial-doc-qc'
import type { TaskCatalog } from '@/types/document-consistency-qc'

export { DocumentConsistencyQcApiError } from '@/api/document-consistency-qc-error'

const PRODUCT_TASK_API_BASE = '/api/clinical-trial-doc-qc'

export class ProductTaskStartApiError extends DocumentConsistencyQcApiError {
  declare readonly taskRunId?: string

  constructor(message: string, taskRunId?: string) {
    super(message)
    this.name = 'ProductTaskStartApiError'
    if (taskRunId) {
      this.taskRunId = taskRunId
    }
  }
}

async function throwProductTaskStartResponseError(response: Response): Promise<never> {
  const body = (await response.json().catch(() => null)) as {
    message?: unknown
    task_run_id?: unknown
  } | null
  const message =
    typeof body?.message === 'string' ? body.message : '任务启动失败'
  const taskRunId =
    typeof body?.task_run_id === 'string' && body.task_run_id.trim()
      ? body.task_run_id
      : undefined
  throw new ProductTaskStartApiError(message, taskRunId)
}

export async function fetchTaskCatalog(): Promise<TaskCatalog> {
  const response = await fetch(`${PRODUCT_TASK_API_BASE}/tasks`)
  if (!response.ok) {
    await throwDocumentConsistencyQcResponseError(response, '任务目录加载失败')
  }
  const payload = await response.json()
  return adaptTaskCatalog(payload)
}

export function buildStartTaskFormData(
  taskId: string,
  slotFiles: ReadonlyMap<string, File>,
): FormData {
  const formData = new FormData()
  formData.append('task_id', taskId)
  for (const [slotId, file] of slotFiles) {
    formData.append(slotId, file)
  }
  return formData
}

export async function startClinicalTrialDocQcTask(
  taskId: string,
  slotFiles: ReadonlyMap<string, File>,
): Promise<ProductTaskStartResult> {
  const response = await fetch(`${PRODUCT_TASK_API_BASE}/task-runs`, {
    method: 'POST',
    body: buildStartTaskFormData(taskId, slotFiles),
  })

  if (!response.ok) {
    await throwProductTaskStartResponseError(response)
  }

  const payload = await response.json()
  return adaptProductTaskStartResult(payload)
}
