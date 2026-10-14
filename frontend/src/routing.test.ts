import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('runtime routing boundaries', () => {
  it('defines launcher and task-owned phase routes without slot id', () => {
    const appSource = readFileSync(resolve(import.meta.dirname, 'App.tsx'), 'utf8')
    expect(appSource).toContain('path="/"')
    expect(appSource).not.toContain('/flow-runs/:flowRunId/upload')
    expect(appSource).toContain('/task-runs/:taskRunId/qc-setup')
    expect(appSource).toContain('/task-runs/:taskRunId/result')
    expect(appSource).toContain('path="/task-runs/:taskRunId"')
    expect(appSource).toContain('TaskRunEntryPage')
    expect(appSource).not.toContain('/flow-runs/:flowRunId/qc-setup')
    expect(appSource).not.toContain('/flow-runs/:flowRunId/result')
    expect(appSource).not.toContain(':slotId')
  })

  it('loads qc setup from TaskRun root then child candidate scope', () => {
    const pageSource = readFileSync(
      resolve(import.meta.dirname, 'pages/qc-setup-page.tsx'),
      'utf8',
    )
    const setupSource = readFileSync(
      resolve(import.meta.dirname, 'components/qc-setup/qc-setup-shell.tsx'),
      'utf8',
    )

    expect(pageSource).toContain('useParams')
    expect(pageSource).toContain('taskRunId')
    expect(pageSource).toContain('fetchTaskRun')
    expect(pageSource).toContain('resolveDocumentConsistencyQcFlowRun')
    expect(pageSource).not.toContain('showcase-bootstrap')
    expect(setupSource).not.toContain('showcase-bootstrap')
    expect(setupSource).toContain('fetchCandidateScopeState(flowRunId)')
    expect(setupSource).not.toContain('查看结果')
  })

  it('loads result shell after TaskRun resolves child flow', () => {
    const pageSource = readFileSync(
      resolve(import.meta.dirname, 'pages/result-page.tsx'),
      'utf8',
    )
    const shellSource = readFileSync(
      resolve(import.meta.dirname, 'components/review/result-shell.tsx'),
      'utf8',
    )

    expect(pageSource).toContain('useParams')
    expect(pageSource).toContain('taskRunId')
    expect(pageSource).toContain('fetchTaskRun')
    expect(shellSource).toContain('fetchDocumentConsistencyQcResult(flowRunId)')
    expect(shellSource).toContain('fetchCandidateScopeDocument(flowRunId, activeSlotId)')
  })
})
