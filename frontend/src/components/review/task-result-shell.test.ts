import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { TaskResultShell } from '@/components/review/task-result-shell'

const workspaceLog = vi.hoisted(() => ({
  flowRunIds: [] as string[],
}))

vi.mock('@/components/review/result-shell', () => ({
  ResultShell: ({
    flowRunId,
    taskDisplayName,
  }: {
    flowRunId: string
    taskDisplayName: string
  }) => {
    workspaceLog.flowRunIds.push(flowRunId)
    return createElement(
      'div',
      {
        'data-task-result-context': true,
        'data-dcqc-result-workspace': true,
        'data-flow-run-id': flowRunId,
      },
      taskDisplayName,
    )
  },
}))

describe('TaskResultShell', () => {
  it('owns dynamic viewport height and contains page-level overflow', () => {
    const html = renderToStaticMarkup(
      createElement(TaskResultShell, {
        taskRunId: 'task_run_result_test',
        taskId: 'internal_ib_qc',
        taskDisplayName: 'Result task',
        flowRunId: 'flow_result_test',
      }),
    )
    const rootClassName = html.match(/^<div class="([^"]*)"/)?.[1]?.split(' ') ?? []

    expect(rootClassName).toContain('h-dvh')
    expect(rootClassName).toContain('min-h-0')
    expect(rootClassName).toContain('overflow-hidden')
    expect(rootClassName).not.toContain('h-svh')
  })

  it('renders Product Task display name and passes flowRunId to DCQC workspace', () => {
    workspaceLog.flowRunIds.length = 0
    const productTaskTitle = 'IB 撰写准确性与一致性'
    // Negative fixture: obsolete capability wording is not a Product Task title.
    const capabilityTitle = '内部 IB 一致性检查'

    const html = renderToStaticMarkup(
      createElement(TaskResultShell, {
        taskRunId: 'task_run_result_test',
        taskId: 'internal_ib_qc',
        taskDisplayName: productTaskTitle,
        flowRunId: 'flow_result_test',
      }),
    )

    expect(html).toContain('data-task-result-context="true"')
    expect(html).toContain(productTaskTitle)
    expect(html).not.toContain(capabilityTitle)
    expect(html).not.toContain('<header')
    expect(html).toContain('data-task-run-id="task_run_result_test"')
    expect(html).toContain('data-task-id="internal_ib_qc"')
    expect(html).toContain('data-flow-run-id="flow_result_test"')
    expect(workspaceLog.flowRunIds).toEqual(['flow_result_test'])
  })
})
