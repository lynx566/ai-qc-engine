import type { ProductTaskStartResult } from '@/types/clinical-trial-doc-qc'

type ApiProductTaskStartResult = {
  task_run_id: string
}

export function adaptProductTaskStartResult(
  payload: ApiProductTaskStartResult,
): ProductTaskStartResult {
  return {
    taskRunId: payload.task_run_id,
  }
}
