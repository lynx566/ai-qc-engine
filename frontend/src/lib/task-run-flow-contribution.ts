import { DOCUMENT_CONSISTENCY_QC_FLOW_ID } from '@/lib/launcher-presentation'
import type { TaskRunFlowRef } from '@/types/task-run'

export class TaskRunDcqcFlowResolutionError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'TaskRunDcqcFlowResolutionError'
  }
}

/**
 * Resolve the current installed Product phase contribution.
 *
 * TaskRun artifacts may contain repeated flow_id values, but the current installed
 * DCQC phase contract is intentionally narrower: exactly one DCQC child contributes
 * to QC Setup and Result. Retry/active-contribution selection is out of scope.
 */
export function resolveDocumentConsistencyQcFlowRun(flowRuns: readonly TaskRunFlowRef[]): string {
  const matches = flowRuns.filter(
    (flowRun) => flowRun.flowId === DOCUMENT_CONSISTENCY_QC_FLOW_ID,
  )
  if (matches.length === 0) {
    throw new TaskRunDcqcFlowResolutionError(
      'TaskRun has no document_consistency_qc child flow',
    )
  }
  if (matches.length > 1) {
    throw new TaskRunDcqcFlowResolutionError(
      'TaskRun has multiple document_consistency_qc child flows',
    )
  }
  return matches[0].flowRunId
}
