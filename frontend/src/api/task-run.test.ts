import { afterEach, describe, expect, it, vi } from 'vitest'

import { fetchTaskRun } from '@/api/task-run'

describe('fetchTaskRun', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('reads a Product TaskRun from the Product namespace', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          task_run_id: 'task_run_test',
          task_id: 'internal_dsur_qc',
          display_name: 'DSUR',
          flow_runs: [
            {
              flow_id: 'document_consistency_qc',
              flow_run_id: 'document_consistency_qc_test',
            },
          ],
          state: {
            input_ready: true,
            product_phase: 'flow_execution_requested',
            product_failure: null,
            allocated_flow: {
              flow_id: 'document_consistency_qc',
              flow_run_id: 'document_consistency_qc_test',
            },
            flow_outcome: 'paused_at_candidate_scope',
            requires_user_action: true,
            result_available: false,
          },
        }),
        { status: 200 },
      ),
    )

    const taskRun = await fetchTaskRun('task/run test')

    expect(taskRun.flowRuns[0]?.flowRunId).toBe('document_consistency_qc_test')
    expect(taskRun.state.requiresUserAction).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/clinical-trial-doc-qc/task-runs/task%2Frun%20test',
    )
  })
})
