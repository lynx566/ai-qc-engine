import type { TaskRunState } from '@/types/task-run'

export const TASK_MISSING_ID_USER_MESSAGE = '无法识别当前任务'
export const TASK_LOADING_USER_MESSAGE = '正在加载…'
export const TASK_FETCH_FAILED_USER_MESSAGE = '任务加载失败，请重试'
export const TASK_PRESENTATION_ERROR_USER_MESSAGE = '任务信息加载异常，请重试'
export const TASK_STATE_REFRESH_FAILED_USER_MESSAGE = '状态更新失败，请重试'
export const RESULT_NOT_READY_USER_MESSAGE = '核查结果尚未生成'
export const RESULT_FLOW_FAILED_USER_MESSAGE = '核查执行失败，暂时无法查看结果'
export const QC_FLOW_FAILED_USER_MESSAGE = '核查执行失败'

export function resolveNoChildTaskRunMessage(state: TaskRunState): string {
  if (state.productFailure) {
    return state.productFailure.message
  }

  switch (state.productPhase) {
    case 'unknown':
      return '暂时无法获取任务状态，请稍后重试'
    case 'input_admission':
      return '任务正在准备中，请稍后重试'
    case 'flow_allocation':
      return '任务正在准备中，请稍后重试'
    case 'flow_allocated':
      return '任务正在准备核查，请稍后重试'
    case 'flow_execution_requested':
      return '任务正在准备核查，请稍后重试'
  }
}

export function resolveResultUnavailableMessage(state: TaskRunState): string {
  if (state.productFailure) {
    return state.productFailure.message
  }
  if (state.flowOutcome === 'failed') {
    return RESULT_FLOW_FAILED_USER_MESSAGE
  }
  return RESULT_NOT_READY_USER_MESSAGE
}

export function resolveQcSetupProductMessage(state: TaskRunState): string | null {
  if (state.productFailure) {
    return state.productFailure.message
  }
  if (state.flowOutcome === 'failed') {
    return QC_FLOW_FAILED_USER_MESSAGE
  }
  return null
}
