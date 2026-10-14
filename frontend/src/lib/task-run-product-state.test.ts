import { describe, expect, it } from 'vitest'

import {
  QC_FLOW_FAILED_USER_MESSAGE,
  resolveNoChildTaskRunMessage,
  resolveQcSetupProductMessage,
  resolveResultUnavailableMessage,
  RESULT_NOT_READY_USER_MESSAGE,
  TASK_LOADING_USER_MESSAGE,
} from '@/lib/task-run-product-state'
import type { TaskRunState } from '@/types/task-run'

const baseState: TaskRunState = {
  inputReady: false,
  productPhase: 'unknown',
  productFailure: null,
  allocatedFlow: null,
  flowOutcome: 'unknown',
  requiresUserAction: null,
  resultAvailable: false,
}

describe('task-run product user messages', () => {
  it('uses product language for no-child phases', () => {
    expect(
      resolveNoChildTaskRunMessage({ ...baseState, productPhase: 'flow_allocation' }),
    ).toBe('任务正在准备中，请稍后重试')
    expect(resolveNoChildTaskRunMessage({ ...baseState, productPhase: 'unknown' })).toBe(
      '暂时无法获取任务状态，请稍后重试',
    )
  })

  it('uses product language for result and qc setup gates', () => {
    expect(resolveResultUnavailableMessage(baseState)).toBe(RESULT_NOT_READY_USER_MESSAGE)
    expect(
      resolveResultUnavailableMessage({ ...baseState, flowOutcome: 'failed' }),
    ).toContain('核查执行失败')
    expect(
      resolveQcSetupProductMessage({ ...baseState, flowOutcome: 'failed' }),
    ).toBe(QC_FLOW_FAILED_USER_MESSAGE)
  })

  it('exposes short loading copy', () => {
    expect(TASK_LOADING_USER_MESSAGE).toBe('正在加载…')
  })
})
