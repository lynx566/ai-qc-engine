import type {
  FlowOutcome,
  ProductFailureBoundary,
  ProductPhase,
  TaskRunFlowRef,
  TaskRunReadModel,
} from '@/types/task-run'

type ApiTaskRunFlowRef = {
  flow_id: string
  flow_run_id: string
}

type ApiTaskRunReadModel = {
  task_run_id: string
  task_id: string
  display_name: string
  flow_runs: ApiTaskRunFlowRef[]
  state: {
    input_ready: boolean
    product_phase: ProductPhase
    product_failure: { boundary: ProductFailureBoundary; message: string } | null
    allocated_flow: ApiTaskRunFlowRef | null
    flow_outcome: FlowOutcome
    requires_user_action: boolean | null
    result_available: boolean
  }
}

function adaptFlowRef(raw: ApiTaskRunFlowRef): TaskRunFlowRef {
  return {
    flowId: raw.flow_id,
    flowRunId: raw.flow_run_id,
  }
}

export function adaptTaskRunReadModel(payload: ApiTaskRunReadModel): TaskRunReadModel {
  return {
    taskRunId: payload.task_run_id,
    taskId: payload.task_id,
    displayName: payload.display_name,
    flowRuns: payload.flow_runs.map(adaptFlowRef),
    state: {
      inputReady: payload.state.input_ready,
      productPhase: payload.state.product_phase,
      productFailure: payload.state.product_failure,
      allocatedFlow: payload.state.allocated_flow
        ? adaptFlowRef(payload.state.allocated_flow)
        : null,
      flowOutcome: payload.state.flow_outcome,
      requiresUserAction: payload.state.requires_user_action,
      resultAvailable: payload.state.result_available,
    },
  }
}
