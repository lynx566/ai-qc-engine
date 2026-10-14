export type TaskRunFlowRef = {
  flowId: string
  flowRunId: string
}

export type ProductPhase = 'unknown' | 'input_admission' | 'flow_allocation' |
  'flow_allocated' | 'flow_execution_requested'

export type ProductFailureBoundary = 'source_materialization' | 'input_intake' |
  'task_input_persistence' | 'flow_prepare_or_allocation' | 'membership_attach'

export type FlowOutcome = 'unknown' | 'paused_at_candidate_scope' |
  'success' | 'partial' | 'failed'

export type TaskRunState = {
  inputReady: boolean
  productPhase: ProductPhase
  productFailure: { boundary: ProductFailureBoundary; message: string } | null
  allocatedFlow: TaskRunFlowRef | null
  flowOutcome: FlowOutcome
  requiresUserAction: boolean | null
  resultAvailable: boolean
}

export type TaskRunReadModel = {
  taskRunId: string
  taskId: string
  displayName: string
  flowRuns: TaskRunFlowRef[]
  state: TaskRunState
}
