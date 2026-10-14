// @vitest-environment happy-dom

import { act, createElement, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'

import {
  ResultShellLoaded,
  type ResultShellLoadedProps,
} from '@/components/review/result-shell'
import type {
  DocumentConsistencyQcResult,
  InternalResultEvidenceRef,
  InternalResultFinding,
} from '@/types/document-consistency-qc'
import type { DocumentView } from '@/types/document-review'
import type { FindingReviewStatePayload } from '@/types/finding-review'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const evidenceA: InternalResultEvidenceRef = {
  slotId: 'source',
  docId: 'doc-a',
  blockId: 'B1',
  sentenceId: 'B1:S1',
  sentenceAlias: 'T1',
}

const evidenceB: InternalResultEvidenceRef = {
  slotId: 'source',
  docId: 'doc-a',
  blockId: 'B1',
  sentenceId: 'B1:S2',
  sentenceAlias: 'T2',
}

const evidenceC: InternalResultEvidenceRef = {
  slotId: 'source',
  docId: 'doc-a',
  blockId: 'B1',
  sentenceId: 'B1:S3',
  sentenceAlias: 'T3',
}

const findingA: InternalResultFinding = {
  findingId: 'A',
  label: 'fail',
  conclusion: 'Finding A',
  comparisonModeId: 'scope_local',
  evidenceRefs: [evidenceA],
}

const findingB: InternalResultFinding = {
  findingId: 'B',
  label: 'fail',
  conclusion: 'Finding B',
  comparisonModeId: 'scope_local',
  evidenceRefs: [evidenceB],
}

const findingC: InternalResultFinding = {
  findingId: 'C',
  label: 'need_review',
  conclusion: 'Finding C',
  comparisonModeId: 'scope_local',
  evidenceRefs: [evidenceC],
}

const sourceDocument: DocumentView = {
  docId: 'doc-a',
  fileName: 'source.docx',
  displayName: 'Source document',
  blocks: [
    {
      blockId: 'doc-a:H1',
      sourceBlockId: 'H1',
      kind: 'heading',
      docOrderIndex: 0,
      headingLevel: 1,
      headingPath: ['Heading'],
      displayText: 'Heading',
    },
    {
      blockId: 'doc-a:B1',
      sourceBlockId: 'B1',
      kind: 'paragraph',
      docOrderIndex: 1,
      headingPath: ['Heading'],
      displayText: 'Alpha. Beta. Gamma.',
      sentences: [
        { sentenceId: 'B1:S1', rawText: 'Alpha.', normalizedText: 'Alpha.' },
        { sentenceId: 'B1:S2', rawText: 'Beta.', normalizedText: 'Beta.' },
        { sentenceId: 'B1:S3', rawText: 'Gamma.', normalizedText: 'Gamma.' },
      ],
    },
  ],
}

const result: DocumentConsistencyQcResult = {
  flowId: 'document_consistency_qc',
  flowRunId: 'run-1',
  capabilityId: 'internal_dsur',
  flowStatus: 'success',
  comparisonRunStatus: 'success',
  finalizationStatus: 'completed',
  fallbackComparisonModes: [],
  findings: [findingA, findingB, findingC],
  scopeResults: [
    {
      slotId: 'source',
      docId: 'doc-a',
      scopeId: 'scope-1',
      headingPath: ['Heading'],
      outlineHeadingBlockId: 'doc-a:H1',
      semanticModuleId: 'module-1',
      executionStatus: 'complete',
      hasSuccessfulCheck: true,
    },
  ],
}

function defaultProps(): ResultShellLoadedProps {
  return {
    taskDisplayName: 'Task',
    functionViewQuery: { mode: 'all' },
    availableSemanticModuleIds: ['module-1'],
    result,
    reviewState: null,
    document: sourceDocument,
    documentStatus: 'ready',
    documentError: null,
    outlineEntries: [{
      blockId: 'doc-a:H1',
      title: 'Heading',
      headingLevel: 1,
      headingPath: ['Heading'],
      docOrderIndex: 0,
    }],
    scopeResultsByOutlineBlockId: new Map(),
    activeOutlineBlockId: null,
    selectedFindingId: null,
    selectedFinding: null,
    selectedEvidenceLocations: [],
    focusedEvidenceLocationKey: null,
    focusedEvidenceLocation: null,
    focusedBlockId: null,
    focusedSentence: null,
    sourceAnnotations: new Map(),
    revisionItems: [],
    commentItems: [],
    activeSourceAnnotationId: null,
    savingAnnotationId: null,
    savingFindingId: null,
    onNavigateRevision: () => {},
    onNavigateComment: () => {},
    onSourceAnnotationActivate: () => {},
    onCreateHighlight: async () => {},
    onDeleteHighlight: async () => {},
    onCreateComment: async () => {},
    onUpdateComment: async () => {},
    onDeleteComment: async () => {},
    onCreateEdit: async () => {},
    onUpdateEdit: async () => {},
    onDeleteEdit: async () => {},
    onSelectHeading: () => {},
    onSelectFinding: () => {},
    onFocusEvidence: () => {},
    onPatchFindingReview: async () => {},
    onClearFocusedSentence: () => {},
    onClearFocusedBlock: () => {},
    onClearActiveSourceAnnotation: () => {},
    onFunctionViewQueryChange: () => {},
  }
}

function WorkspaceHarness({ overrides }: { overrides: Partial<ResultShellLoadedProps> }) {
  const shellResult = overrides.result ?? result
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null)
  const [reviewState, setReviewState] = useState<FindingReviewStatePayload | null>(null)
  const selectedFinding = shellResult.findings.find(finding => finding.findingId === selectedFindingId) ?? null
  return createElement(ResultShellLoaded, {
    ...defaultProps(), ...overrides,
    selectedFindingId, selectedFinding,
    selectedEvidenceLocations: selectedFinding?.evidenceRefs ?? [],
    reviewState: overrides.reviewState ?? reviewState,
    onSelectFinding: setSelectedFindingId,
    onPatchFindingReview: async (findingId, patch) => {
      setReviewState(current => {
        const previous = current?.entriesByFindingId.get(findingId)
        const entries = new Map(current?.entriesByFindingId ?? [])
        entries.set(findingId, {
          findingId, decision: patch.decision ?? previous?.decision ?? 'pending',
          marked: patch.marked ?? previous?.marked ?? false,
          note: patch.note ?? previous?.note, updatedAt: '2026-10-08T00:00:00Z',
        })
        return { flowRunId: shellResult.flowRunId, entriesByFindingId: entries }
      })
    },
  })
}

const sessions: Array<{ cleanup: () => void }> = []
function renderWorkspace(initial: Partial<ResultShellLoadedProps> = {}) {
  const host = document.createElement('div'); document.body.append(host)
  const root = createRoot(host)
  let overrides = initial
  const render = () => act(() => root.render(createElement(MemoryRouter, null, createElement(WorkspaceHarness, { overrides }))))
  render()
  const session = {
    host,
    rerender(next: Partial<ResultShellLoadedProps>) { overrides = { ...overrides, ...next }; render() },
    cleanup() { act(() => root.unmount()); host.remove() },
  }
  sessions.push(session)
  return session
}
afterEach(() => { sessions.splice(0).forEach(session => session.cleanup()) })
function click(host: HTMLElement, selector: string) {
  act(() => host.querySelector<HTMLButtonElement>(selector)!.click())
}
function select(host: HTMLElement, id: string) {
  click(host, '[data-finding-queue-item="' + id + '"] [data-finding-queue-select]')
}

// Shared regressions migrated from the former Sequential workspace suite.
describe('ResultShellLoaded Overview workspace', () => {
  it('defaults to the queue head with Source Evidence and no independent review-mode entry', () => {
    const { host } = renderWorkspace()
    expect(host.querySelector('[data-finding-queue-item="A"]')?.getAttribute('data-finding-selected')).toBe('true')
    expect(host.querySelectorAll('[data-source-evidence-viewport]')).toHaveLength(1)
    expect(host.querySelector('[data-document-canvas]')).toBeNull()
    expect(host.textContent).not.toContain('逐条审阅')
    expect(host.querySelector('[data-result-enter-sequential-review]')).toBeNull()
    expect(host.querySelector('[data-result-sequential-current-finding]')).toBeNull()
    expect(host.querySelector('[data-result-show-full-document]')).not.toBeNull()
  })

  it('keeps Overview selection after ordinary rerenders rather than reinitializing', () => {
    const session = renderWorkspace()
    select(session.host, 'B')
    session.rerender({ savingFindingId: 'B' })
    expect(session.host.querySelector('[data-finding-queue-item="B"]')?.getAttribute('data-finding-selected')).toBe('true')
    expect(session.host.querySelector('[data-source-evidence-viewport]')?.textContent).toContain('Beta.')
    expect(session.host.querySelector('[data-result-workspace-toolbar]')).not.toBeNull()
    expect(session.host.querySelector('[data-source-annotation-navigator]')).toBeNull()
  })

  it('renders an empty Result canonically, including after a new empty Result identity', () => {
    const empty = renderWorkspace({ result: { ...result, findings: [] } })
    expect(empty.host.querySelector('[data-document-canvas]')).not.toBeNull()
    expect(empty.host.querySelector('[data-result-show-findings-overview]')).toBeNull()
    const session = renderWorkspace()
    select(session.host, 'B')
    session.rerender({ result: { ...result, flowRunId: 'empty-run', findings: [] } })
    expect(session.host.querySelector('[data-document-canvas]')).not.toBeNull()
    expect(session.host.querySelector('[data-finding-source-document-panel]')).toBeNull()
    expect(session.host.querySelector('[data-result-show-findings-overview]')).toBeNull()
  })

  it('preserves selection, review decisions, marks and notes across Full Document navigation', async () => {
    const { host } = renderWorkspace()
    select(host, 'B')
    await act(async () => { host.querySelector<HTMLButtonElement>('[data-finding-queue-item="B"] [aria-label="确认"]')!.click() })
    await act(async () => { host.querySelector<HTMLButtonElement>('[data-finding-queue-item="B"] [aria-label="标记提醒"]')!.click() })
    click(host, '[data-finding-queue-item="B"] [aria-label="添加笔记"]')
    const input = host.querySelector<HTMLTextAreaElement>('[data-finding-queue-item="B"] textarea')!
    act(() => {
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(input, 'Saved B')
      input.dispatchEvent(new Event('input', { bubbles: true }))
    })
    await act(async () => { [...host.querySelectorAll<HTMLButtonElement>('[data-finding-queue-item="B"] button')].find(button => button.textContent === '保存')!.click() })
    click(host, '[data-result-show-full-document]')
    expect(host.querySelector('[data-document-canvas]')).not.toBeNull()
    expect(host.querySelector('[data-finding-source-document-panel]')).toBeNull()
    click(host, '[data-result-show-findings-overview]')
    const item = host.querySelector<HTMLElement>('[data-finding-queue-item="B"]')!
    expect(item.dataset.findingSelected).toBe('true')
    expect(item.dataset.findingDecision).toBe('confirmed')
    expect(item.dataset.findingMarked).toBe('true')
    expect(item.querySelector('[data-finding-note-preview]')?.textContent).toContain('Saved B')
    expect(host.querySelector('[data-source-evidence-viewport]')?.textContent).toContain('Beta.')
    select(host, 'A'); select(host, 'B')
    expect(item.dataset.findingDecision).toBe('confirmed')
    expect(item.dataset.findingMarked).toBe('true')
    expect(item.querySelector('[data-finding-note-preview]')?.textContent).toContain('Saved B')
  })

  it('keeps the Finding workspace visible through Full Document navigation', () => {
    const { host } = renderWorkspace()
    select(host, 'B')
    click(host, '[data-result-show-full-document]')
    expect(host.querySelector('[data-result-findings-panel]')).toBeNull()
    click(host, '[data-result-show-findings-overview]')
    expect(host.querySelector('[data-result-findings-panel]')?.getAttribute('data-result-findings-panel-open')).toBe('true')
    expect(host.querySelector('[data-result-findings-close]')).toBeNull()
    expect(host.querySelector('[data-result-findings-reopen]')).toBeNull()
    expect(host.querySelector('[data-finding-queue-item="B"]')?.getAttribute('data-finding-selected')).toBe('true')
    expect(host.querySelector('[data-finding-source-document-panel]')).not.toBeNull()
  })

  it('preserves a same-finding draft and keeps different Queue card editors independent', () => {
    const session = renderWorkspace()
    click(session.host, '[data-finding-queue-item="A"] [aria-label="添加笔记"]')
    const input = session.host.querySelector<HTMLTextAreaElement>('[data-finding-queue-item="A"] textarea')!
    act(() => {
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(input, 'Unsaved A')
      input.dispatchEvent(new Event('input', { bubbles: true }))
    })
    session.rerender({ savingFindingId: 'A' })
    expect(session.host.querySelector('[data-finding-queue-item="A"] textarea')).toBe(input)
    expect(input.value).toBe('Unsaved A')
    session.rerender({ savingFindingId: null })
    select(session.host, 'B')
    click(session.host, '[data-finding-queue-item="B"] [aria-label="添加笔记"]')
    expect(session.host.querySelector<HTMLTextAreaElement>('[data-finding-queue-item="B"] textarea')!.value).toBe('')
    expect(input.value).toBe('Unsaved A')
  })

  it('preserves Overview popovers when the Source panel scrolls', () => {
    const annotation = {
      annotationId: 'comment-a', kind: 'comment' as const,
      anchor: { slotId: 'source', docId: 'doc-a', blockId: 'B1', sentenceId: 'B1:S1' },
      range: { startOffset: 0, endOffset: 5 }, content: 'Saved comment', createdAt: 'now', updatedAt: 'now',
    }
    const { host } = renderWorkspace({ sourceAnnotations: new Map([[annotation.annotationId, annotation]]) })
    click(host, '[data-source-comment-icon]')
    expect(document.body.querySelector('[data-source-comment-popover]')).not.toBeNull()
    act(() => host.querySelector('[data-finding-source-document-panel]')!.dispatchEvent(new Event('scroll')))
    expect(document.body.querySelector('[data-source-comment-popover]')).not.toBeNull()
  })
})
