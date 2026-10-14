// @vitest-environment happy-dom

import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { TaskQcSetupShell } from '@/components/qc-setup/task-qc-setup-shell'
import type { TaskRunState } from '@/types/task-run'

const workspaceLog = vi.hoisted(() => ({
  flowRunIds: [] as string[],
  resultAvailability: [] as boolean[],
}))

vi.mock('@/components/qc-setup/qc-setup-shell', () => ({
  QcSetupShell: ({
    flowRunId,
    taskDisplayName,
    onProceedToResult,
    taskState,
  }: {
    flowRunId: string
    taskDisplayName: string
    onProceedToResult: () => void
    taskState: TaskRunState
    refreshTaskRunState: () => Promise<TaskRunState>
  }) => {
    workspaceLog.flowRunIds.push(flowRunId)
    workspaceLog.resultAvailability.push(taskState.resultAvailable)
    return createElement(
      'div',
      { 'data-task-qc-setup-context': true },
      createElement('span', null, taskDisplayName),
      createElement(
        'button',
        {
          type: 'button',
          'data-dcqc-qc-setup-workspace': true,
          'data-flow-run-id': flowRunId,
          onClick: onProceedToResult,
        },
        'DCQC capability title',
      ),
    )
  },
}))

describe('TaskQcSetupShell', () => {
  it('owns Product context, passes only Flow context, and navigates by taskRunId', async () => {
    workspaceLog.flowRunIds.length = 0
    workspaceLog.resultAvailability.length = 0
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)
    const productTaskTitle = 'Product Task display name'

    const router = createMemoryRouter(
      [
        {
          path: '/task-runs/:taskRunId/qc-setup',
          element: createElement(TaskQcSetupShell, {
            taskRunId: 'task_run_qc_setup_test',
            taskId: 'internal_ib_qc',
            taskDisplayName: productTaskTitle,
            flowRunId: 'flow_qc_setup_test',
            taskState: {
              inputReady: true,
              productPhase: 'flow_execution_requested',
              productFailure: null,
              allocatedFlow: {
                flowId: 'document_consistency_qc',
                flowRunId: 'flow_qc_setup_test',
              },
              flowOutcome: 'success',
              requiresUserAction: false,
              resultAvailable: true,
            },
            refreshTaskRunState: vi.fn(),
          }),
        },
        {
          path: '/task-runs/:taskRunId/result',
          element: createElement('div', { 'data-result-route': true }),
        },
      ],
      { initialEntries: ['/task-runs/task_run_qc_setup_test/qc-setup'] },
    )

    await act(async () => {
      root.render(createElement(RouterProvider, { router }))
    })

    const taskContext = container.querySelector('[data-task-qc-setup-context]')
    expect(taskContext?.textContent).toContain(productTaskTitle)
    expect(taskContext?.textContent).toContain('DCQC capability title')
    expect(container.querySelector('header')).toBeNull()
    expect(workspaceLog.flowRunIds).toEqual(['flow_qc_setup_test'])
    expect(workspaceLog.resultAvailability).toEqual([true])

    await act(async () => {
      container.querySelector<HTMLButtonElement>('[data-dcqc-qc-setup-workspace]')?.click()
    })

    expect(router.state.location.pathname).toBe(
      '/task-runs/task_run_qc_setup_test/result',
    )
    expect(container.querySelector('[data-result-route]')).not.toBeNull()

    act(() => root.unmount())
    container.remove()
  })
})
