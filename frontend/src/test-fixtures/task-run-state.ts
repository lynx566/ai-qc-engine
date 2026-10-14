import type { TaskRunState } from '@/types/task-run'

const allocatedFlow = {
  flowId: 'document_consistency_qc',
  flowRunId: 'document_consistency_qc_test',
} as const

const requestedState = {
  inputReady: true,
  productPhase: 'flow_execution_requested',
  productFailure: null,
  allocatedFlow,
} as const

export const PAUSED_TASK_STATE = {
  ...requestedState,
  flowOutcome: 'paused_at_candidate_scope',
  requiresUserAction: true,
  resultAvailable: false,
} satisfies TaskRunState

export const SUCCESS_RESULT_TASK_STATE = {
  ...requestedState,
  flowOutcome: 'success',
  requiresUserAction: false,
  resultAvailable: true,
} satisfies TaskRunState

export const SUCCESS_NO_RESULT_TASK_STATE = {
  ...requestedState,
  flowOutcome: 'success',
  requiresUserAction: false,
  resultAvailable: false,
} satisfies TaskRunState

export const FLOW_FAILED_TASK_STATE = {
  ...requestedState,
  flowOutcome: 'failed',
  requiresUserAction: false,
  resultAvailable: false,
} satisfies TaskRunState

export const PRODUCT_FAILED_TASK_STATE = {
  inputReady: false,
  productPhase: 'input_admission',
  productFailure: {
    boundary: 'input_intake',
    message: 'Input intake failed',
  },
  allocatedFlow: null,
  flowOutcome: 'unknown',
  requiresUserAction: null,
  resultAvailable: false,
} satisfies TaskRunState

export const HISTORICAL_UNKNOWN_TASK_STATE = {
  inputReady: false,
  productPhase: 'unknown',
  productFailure: null,
  allocatedFlow: null,
  flowOutcome: 'unknown',
  requiresUserAction: null,
  resultAvailable: false,
} satisfies TaskRunState
