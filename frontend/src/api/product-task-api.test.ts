import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  ProductTaskStartApiError,
  fetchTaskCatalog,
  startClinicalTrialDocQcTask,
} from '@/api/clinical-trial-doc-qc'

const rawCatalog = {
  tasks: [
    {
      task_id: 'internal_dsur_qc',
      display_name: 'DSUR',
      description: 'desc',
      slots: [
        {
          slot_id: 'source',
          expected_document_type: 'dsur',
          upload_label: 'upload',
          help_text: 'help',
        },
      ],
    },
  ],
}

describe('Product Task API namespace', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('loads the Product Task catalog from the Product namespace', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(rawCatalog), { status: 200 }),
    )

    const catalog = await fetchTaskCatalog()

    expect(catalog.tasks[0]?.taskId).toBe('internal_dsur_qc')
    expect(fetchMock).toHaveBeenCalledWith('/api/clinical-trial-doc-qc/tasks')
  })

  it('starts a Product Task from the Product namespace', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ task_run_id: 'task_run_test' }), { status: 200 }),
    )

    const result = await startClinicalTrialDocQcTask('internal_dsur_qc', new Map())

    expect(result.taskRunId).toBe('task_run_test')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/clinical-trial-doc-qc/task-runs',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('preserves TaskRun identity from a failed Product Start response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          status: 'failed',
          message: 'checkpoint failed',
          task_run_id: 'task_run_failed',
        }),
        { status: 500 },
      ),
    )

    let caught: unknown
    try {
      await startClinicalTrialDocQcTask('internal_dsur_qc', new Map())
    } catch (error) {
      caught = error
    }

    expect(caught).toMatchObject({
      message: 'checkpoint failed',
      taskRunId: 'task_run_failed',
    })
    expect(caught).toBeInstanceOf(ProductTaskStartApiError)
  })

  it('does not invent TaskRun identity for a pre-TaskRun error', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ status: 'failed', message: 'unsupported task_id' }),
        { status: 400 },
      ),
    )

    let caught: unknown
    try {
      await startClinicalTrialDocQcTask('unknown', new Map())
    } catch (error) {
      caught = error
    }

    expect(caught).toMatchObject({ message: 'unsupported task_id' })
    expect(caught).not.toHaveProperty('taskRunId')
  })
})
