// @vitest-environment happy-dom

import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { TaskRunEntryPage } from '@/pages/task-run-entry-page'
import {
  PAUSED_TASK_STATE,
  SUCCESS_RESULT_TASK_STATE,
} from '@/test-fixtures/task-run-state'
import type { TaskRunReadModel } from '@/types/task-run'

vi.mock('@/api/task-run', () => ({
  fetchTaskRun: vi.fn(),
}))

import { fetchTaskRun } from '@/api/task-run'

const mockFetchTaskRun = vi.mocked(fetchTaskRun)

function taskRun(taskRunId: string, state: TaskRunReadModel['state']): TaskRunReadModel {
  return {
    taskRunId,
    taskId: 'internal_dsur_qc',
    displayName: 'DSUR 质控',
    flowRuns: [{ flowId: 'document_consistency_qc', flowRunId: 'flow_test' }],
    state,
  }
}

describe('TaskRunEntryPage', () => {
  it('redirects paused tasks to qc setup', async () => {
    mockFetchTaskRun.mockResolvedValue(taskRun('task_run_paused', PAUSED_TASK_STATE))

    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)

    const router = createMemoryRouter(
      [
        { path: '/task-runs/:taskRunId', element: createElement(TaskRunEntryPage) },
        {
          path: '/task-runs/:taskRunId/qc-setup',
          element: createElement('div', { 'data-qc-setup-route': true }),
        },
        {
          path: '/task-runs/:taskRunId/result',
          element: createElement('div', { 'data-result-route': true }),
        },
      ],
      { initialEntries: ['/task-runs/task_run_paused'] },
    )

    await act(async () => {
      root.render(createElement(RouterProvider, { router }))
    })

    await act(async () => {
      await Promise.resolve()
    })

    expect(router.state.location.pathname).toBe('/task-runs/task_run_paused/qc-setup')
    expect(container.querySelector('[data-qc-setup-route]')).not.toBeNull()

    act(() => root.unmount())
    container.remove()
  })

  it('redirects completed tasks with result to the result page', async () => {
    mockFetchTaskRun.mockResolvedValue(taskRun('task_run_done', SUCCESS_RESULT_TASK_STATE))

    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)

    const router = createMemoryRouter(
      [
        { path: '/task-runs/:taskRunId', element: createElement(TaskRunEntryPage) },
        {
          path: '/task-runs/:taskRunId/qc-setup',
          element: createElement('div', { 'data-qc-setup-route': true }),
        },
        {
          path: '/task-runs/:taskRunId/result',
          element: createElement('div', { 'data-result-route': true }),
        },
      ],
      { initialEntries: ['/task-runs/task_run_done'] },
    )

    await act(async () => {
      root.render(createElement(RouterProvider, { router }))
    })

    await act(async () => {
      await Promise.resolve()
    })

    expect(router.state.location.pathname).toBe('/task-runs/task_run_done/result')
    expect(container.querySelector('[data-result-route]')).not.toBeNull()

    act(() => root.unmount())
    container.remove()
  })
})
