// @vitest-environment happy-dom

import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchTaskRun } from '@/api/task-run'
import { QcSetupPage } from '@/pages/qc-setup-page'
import { ResultPage } from '@/pages/result-page'
import {
  FLOW_FAILED_TASK_STATE,
  HISTORICAL_UNKNOWN_TASK_STATE,
  PAUSED_TASK_STATE,
  PRODUCT_FAILED_TASK_STATE,
  SUCCESS_RESULT_TASK_STATE,
} from '@/test-fixtures/task-run-state'
import type { TaskRunReadModel, TaskRunState } from '@/types/task-run'

const renderLog = vi.hoisted(() => ({
  qcSetup: [] as Array<{
    taskRunId: string
    taskId: string
    taskDisplayName: string
    flowRunId: string
    taskState: TaskRunState
  }>,
  qcSetupRefreshes: [] as Array<{
    taskRunId: string
    refresh: () => Promise<TaskRunState | null>
  }>,
  result: [] as Array<{
    taskRunId: string
    taskId: string
    taskDisplayName: string
    flowRunId: string
  }>,
}))

vi.mock('@/api/task-run', () => ({
  fetchTaskRun: vi.fn(),
}))

vi.mock('@/components/qc-setup/task-qc-setup-shell', () => ({
  TaskQcSetupShell: ({ refreshTaskRunState, ...props }: {
    taskRunId: string
    taskId: string
    taskDisplayName: string
    flowRunId: string
    taskState: TaskRunState
    refreshTaskRunState: () => Promise<TaskRunState | null>
  }) => {
    renderLog.qcSetup.push(props)
    renderLog.qcSetupRefreshes.push({ taskRunId: props.taskRunId, refresh: refreshTaskRunState })
    return null
  },
}))

vi.mock('@/components/review/task-result-shell', () => ({
  TaskResultShell: (props: {
    taskRunId: string
    taskId: string
    taskDisplayName: string
    flowRunId: string
  }) => {
    renderLog.result.push(props)
    return null
  },
}))

const mockFetchTaskRun = vi.mocked(fetchTaskRun)

let container: HTMLDivElement
let root: Root

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

function taskRun(
  taskRunId: string,
  taskId: string,
  flowRunId: string,
  displayName?: string,
  stateOverrides: Partial<TaskRunState> = {},
): TaskRunReadModel {
  return {
    taskRunId,
    taskId,
    displayName: displayName ?? `${taskId}-display`,
    flowRuns: [{ flowId: 'document_consistency_qc', flowRunId }],
    state: {
      ...PAUSED_TASK_STATE,
      allocatedFlow: { flowId: 'document_consistency_qc', flowRunId },
      ...stateOverrides,
    },
  }
}

async function flushAsyncWork() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
  })
}

describe('TaskRun-owned phase pages', () => {
  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    renderLog.qcSetup.length = 0
    renderLog.qcSetupRefreshes.length = 0
    renderLog.result.length = 0
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
    vi.clearAllMocks()
  })

  it('never renders TaskRun A contribution under TaskRun B qc-setup route', async () => {
    const taskRunA = deferred<TaskRunReadModel>()
    const taskRunB = deferred<TaskRunReadModel>()
    mockFetchTaskRun.mockImplementation((taskRunId) =>
      taskRunId === 'task_run_A' ? taskRunA.promise : taskRunB.promise,
    )
    const router = createMemoryRouter(
      [
        {
          path: '/task-runs/:taskRunId/qc-setup',
          element: createElement(QcSetupPage),
        },
      ],
      { initialEntries: ['/task-runs/task_run_A/qc-setup'] },
    )
    act(() => root.render(createElement(RouterProvider, { router })))
    taskRunA.resolve(taskRun('task_run_A', 'internal_dsur_qc', 'flow_A'))
    await flushAsyncWork()
    expect(renderLog.qcSetup.at(-1)).toEqual({
      taskRunId: 'task_run_A',
      taskId: 'internal_dsur_qc',
      taskDisplayName: 'DSUR',
      flowRunId: 'flow_A',
      taskState: taskRun('task_run_A', 'internal_dsur_qc', 'flow_A').state,
    })

    const renderCountBeforeNavigation = renderLog.qcSetup.length
    await act(async () => {
      await router.navigate('/task-runs/task_run_B/qc-setup')
    })
    expect(renderLog.qcSetup.slice(renderCountBeforeNavigation)).not.toContainEqual({
      taskRunId: 'task_run_B',
      taskId: 'internal_dsur_qc',
      flowRunId: 'flow_A',
    })

    taskRunB.resolve(taskRun('task_run_B', 'internal_ib_qc', 'flow_B'))
    await flushAsyncWork()
    expect(renderLog.qcSetup.at(-1)).toEqual({
      taskRunId: 'task_run_B',
      taskId: 'internal_ib_qc',
      taskDisplayName: 'IB',
      flowRunId: 'flow_B',
      taskState: taskRun('task_run_B', 'internal_ib_qc', 'flow_B').state,
    })
  })

  it('discards a TaskRun refresh that finishes after navigation to another TaskRun', async () => {
    const initialTaskRunA = taskRun('task_run_A', 'internal_dsur_qc', 'flow_A')
    const refreshTaskRunA = deferred<TaskRunReadModel>()
    const taskRunB = deferred<TaskRunReadModel>()
    let taskRunACalls = 0
    mockFetchTaskRun.mockImplementation((taskRunId) => {
      if (taskRunId === 'task_run_A') {
        taskRunACalls += 1
        return taskRunACalls === 1 ? Promise.resolve(initialTaskRunA) : refreshTaskRunA.promise
      }
      return taskRunB.promise
    })
    const router = createMemoryRouter(
      [{ path: '/task-runs/:taskRunId/qc-setup', element: createElement(QcSetupPage) }],
      { initialEntries: ['/task-runs/task_run_A/qc-setup'] },
    )
    act(() => root.render(createElement(RouterProvider, { router })))
    await flushAsyncWork()

    const refreshA = renderLog.qcSetupRefreshes.at(-1)?.refresh
    expect(refreshA).toBeDefined()
    const staleRefresh = refreshA!()

    await act(async () => {
      await router.navigate('/task-runs/task_run_B/qc-setup')
    })
    taskRunB.resolve(taskRun('task_run_B', 'internal_ib_qc', 'flow_B'))
    await flushAsyncWork()

    refreshTaskRunA.resolve(taskRun('task_run_A', 'internal_dsur_qc', 'flow_A'))
    await expect(staleRefresh).resolves.toBeNull()
    await flushAsyncWork()
    expect(renderLog.qcSetup.at(-1)?.taskRunId).toBe('task_run_B')
  })

  it('reports a missing task display name without calling it a child membership failure', async () => {
    mockFetchTaskRun.mockResolvedValue(
      taskRun('task_run_blank_name', 'internal_dsur_qc', 'flow_blank_name', '   '),
    )
    const router = createMemoryRouter(
      [{ path: '/task-runs/:taskRunId/qc-setup', element: createElement(QcSetupPage) }],
      { initialEntries: ['/task-runs/task_run_blank_name/qc-setup'] },
    )
    act(() => root.render(createElement(RouterProvider, { router })))
    await flushAsyncWork()

    expect(container.textContent).toContain('任务信息加载异常，请重试')
    expect(container.textContent).not.toContain('子流程成员解析失败')
  })

  it('does not mount the Result workspace when Product Result is unavailable', async () => {
    mockFetchTaskRun.mockResolvedValue(
      taskRun('task_run_unavailable', 'internal_dsur_qc', 'flow_unavailable'),
    )
    const router = createMemoryRouter(
      [{ path: '/task-runs/:taskRunId/result', element: createElement(ResultPage) }],
      { initialEntries: ['/task-runs/task_run_unavailable/result'] },
    )
    act(() => root.render(createElement(RouterProvider, { router })))
    await flushAsyncWork()

    expect(renderLog.result).toHaveLength(0)
    expect(container.textContent).toContain('核查结果尚未生成')
  })

  it('shows downstream Flow failure without mounting the Result workspace', async () => {
    mockFetchTaskRun.mockResolvedValue(
      taskRun('task_run_flow_failed', 'internal_dsur_qc', 'flow_failed', undefined, {
        ...FLOW_FAILED_TASK_STATE,
        allocatedFlow: {
          flowId: 'document_consistency_qc',
          flowRunId: 'flow_failed',
        },
      }),
    )
    const router = createMemoryRouter(
      [{ path: '/task-runs/:taskRunId/result', element: createElement(ResultPage) }],
      { initialEntries: ['/task-runs/task_run_flow_failed/result'] },
    )
    act(() => root.render(createElement(RouterProvider, { router })))
    await flushAsyncWork()

    expect(renderLog.result).toHaveLength(0)
    expect(container.textContent).toContain('核查执行失败，暂时无法查看结果')
  })

  it('never renders TaskRun A contribution under TaskRun B result route', async () => {
    const taskRunA = deferred<TaskRunReadModel>()
    const taskRunB = deferred<TaskRunReadModel>()
    mockFetchTaskRun.mockImplementation((taskRunId) =>
      taskRunId === 'task_run_A' ? taskRunA.promise : taskRunB.promise,
    )
    const router = createMemoryRouter(
      [
        {
          path: '/task-runs/:taskRunId/result',
          element: createElement(ResultPage),
        },
      ],
      { initialEntries: ['/task-runs/task_run_A/result'] },
    )
    act(() => root.render(createElement(RouterProvider, { router })))
    taskRunA.resolve(taskRun('task_run_A', 'internal_dsur_qc', 'flow_A', undefined, {
      ...SUCCESS_RESULT_TASK_STATE,
      allocatedFlow: { flowId: 'document_consistency_qc', flowRunId: 'flow_A' },
    }))
    await flushAsyncWork()
    expect(renderLog.result.at(-1)).toEqual({
      taskRunId: 'task_run_A',
      taskId: 'internal_dsur_qc',
      taskDisplayName: 'DSUR',
      flowRunId: 'flow_A',
    })

    const renderCountBeforeNavigation = renderLog.result.length
    await act(async () => {
      await router.navigate('/task-runs/task_run_B/result')
    })
    expect(
      renderLog.result.slice(renderCountBeforeNavigation).map((entry) => entry.flowRunId),
    ).not.toContain('flow_A')

    taskRunB.resolve(taskRun('task_run_B', 'internal_ib_qc', 'flow_B', undefined, {
      ...SUCCESS_RESULT_TASK_STATE,
      allocatedFlow: { flowId: 'document_consistency_qc', flowRunId: 'flow_B' },
    }))
    await flushAsyncWork()
    expect(renderLog.result.at(-1)).toEqual({
      taskRunId: 'task_run_B',
      taskId: 'internal_ib_qc',
      taskDisplayName: 'IB',
      flowRunId: 'flow_B',
    })
  })

  it('shows a Product failure when QC Setup has no attached Flow', async () => {
    mockFetchTaskRun.mockResolvedValue({
      ...taskRun('task_run_failed', 'internal_dsur_qc', 'unused'),
      flowRuns: [],
      state: PRODUCT_FAILED_TASK_STATE,
    })
    const router = createMemoryRouter(
      [{ path: '/task-runs/:taskRunId/qc-setup', element: createElement(QcSetupPage) }],
      { initialEntries: ['/task-runs/task_run_failed/qc-setup'] },
    )
    act(() => root.render(createElement(RouterProvider, { router })))
    await flushAsyncWork()
    expect(container.textContent).toContain('Input intake failed')
    expect(container.textContent).not.toContain('TaskRun has no document_consistency_qc child flow')
  })

  it('describes a zero-child allocation state without exposing the raw Product phase', async () => {
    mockFetchTaskRun.mockResolvedValue({
      ...taskRun('task_run_pending', 'internal_dsur_qc', 'unused'),
      flowRuns: [],
      state: {
        inputReady: false,
        productPhase: 'flow_allocation',
        productFailure: null,
        allocatedFlow: null,
        flowOutcome: 'unknown',
        requiresUserAction: null,
        resultAvailable: false,
      },
    })
    const router = createMemoryRouter(
      [{ path: '/task-runs/:taskRunId/result', element: createElement(ResultPage) }],
      { initialEntries: ['/task-runs/task_run_pending/result'] },
    )
    act(() => root.render(createElement(RouterProvider, { router })))
    await flushAsyncWork()
    expect(container.textContent).toContain('任务正在准备中，请稍后重试')
    expect(container.textContent).not.toContain('flow_allocation')
    expect(container.textContent).not.toContain('TaskRun has no document_consistency_qc child flow')
  })

  it('describes a zero-child unknown state without claiming liveness', async () => {
    mockFetchTaskRun.mockResolvedValue({
      ...taskRun('task_run_unknown', 'internal_dsur_qc', 'unused'),
      flowRuns: [],
      state: HISTORICAL_UNKNOWN_TASK_STATE,
    })
    const router = createMemoryRouter(
      [{ path: '/task-runs/:taskRunId/qc-setup', element: createElement(QcSetupPage) }],
      { initialEntries: ['/task-runs/task_run_unknown/qc-setup'] },
    )
    act(() => root.render(createElement(RouterProvider, { router })))
    await flushAsyncWork()

    expect(container.textContent).toContain('暂时无法获取任务状态，请稍后重试')
    expect(container.textContent).not.toContain('Product phase: unknown')
    expect(container.textContent).not.toContain('正在运行')
    expect(container.textContent).not.toContain('处理中')
  })

  it('prioritizes Product failure over child Flow state on the Result route', async () => {
    mockFetchTaskRun.mockResolvedValue(
      taskRun('task_run_product_failed', 'internal_dsur_qc', 'flow_attached', undefined, {
        ...PRODUCT_FAILED_TASK_STATE,
        allocatedFlow: {
          flowId: 'document_consistency_qc',
          flowRunId: 'flow_attached',
        },
      }),
    )
    const router = createMemoryRouter(
      [{ path: '/task-runs/:taskRunId/result', element: createElement(ResultPage) }],
      { initialEntries: ['/task-runs/task_run_product_failed/result'] },
    )
    act(() => root.render(createElement(RouterProvider, { router })))
    await flushAsyncWork()

    expect(renderLog.result).toHaveLength(0)
    expect(container.textContent).toContain('Input intake failed')
    expect(container.textContent).not.toContain('核查执行失败')
  })
})
