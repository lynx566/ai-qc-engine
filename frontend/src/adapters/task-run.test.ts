import { describe, expect, it } from 'vitest'

import { adaptTaskRunReadModel } from '@/adapters/task-run'

describe('adaptTaskRunReadModel', () => {
  it('maps TaskRun page context fields', () => {
    const model = adaptTaskRunReadModel({
      task_run_id: 'task_run_test',
      task_id: 'internal_dsur_qc',
      display_name: '研发期间安全性更新报告（DSUR）',
      flow_runs: [
        {
          flow_id: 'document_consistency_qc',
          flow_run_id: 'document_consistency_qc_test',
        },
      ],
      state: {
        input_ready: false,
        product_phase: 'flow_allocated',
        product_failure: null,
        allocated_flow: { flow_id: 'document_consistency_qc', flow_run_id: 'flow_1' },
        flow_outcome: 'unknown',
        requires_user_action: null,
        result_available: false,
      },
    })

    expect(model.taskRunId).toBe('task_run_test')
    expect(model.taskId).toBe('internal_dsur_qc')
    expect(model.displayName).toBe('研发期间安全性更新报告（DSUR）')
    expect(model.flowRuns).toEqual([
      {
        flowId: 'document_consistency_qc',
        flowRunId: 'document_consistency_qc_test',
      },
    ])
    expect(model.state).toEqual({
      inputReady: false,
      productPhase: 'flow_allocated',
      productFailure: null,
      allocatedFlow: { flowId: 'document_consistency_qc', flowRunId: 'flow_1' },
      flowOutcome: 'unknown',
      requiresUserAction: null,
      resultAvailable: false,
    })
  })
})
