// @vitest-environment happy-dom

import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'

import { ResultShellLoaded, type ResultShellLoadedProps } from '@/components/review/result-shell'
import type {
  DocumentConsistencyQcResult,
  InternalResultEvidenceRef,
  InternalResultFinding,
} from '@/types/document-consistency-qc'
import type { DocumentView } from '@/types/document-review'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const sentences = Array.from({ length: 8 }, (_, index) => ({
  sentenceId: `P1:S${index + 1}`,
  rawText: `Sentence ${index + 1}.`,
  normalizedText: `Sentence ${index + 1}.`,
}))
const documentView: DocumentView = {
  docId: 'doc-a', fileName: 'doc-a.docx', displayName: 'Document A',
  blocks: [
    {
      blockId: 'doc-a:H1', sourceBlockId: 'H1', kind: 'heading', docOrderIndex: 0,
      headingLevel: 1, headingPath: ['Section'], displayText: 'Section',
      sentences: [{ sentenceId: 'H1:S1', rawText: 'Section', normalizedText: 'Section' }],
    },
    {
      blockId: 'doc-a:P1', sourceBlockId: 'P1', kind: 'paragraph', docOrderIndex: 1,
      headingPath: ['Section'], displayText: sentences.map((item) => item.rawText).join(' '),
      sentences,
    },
  ],
}
function evidence(index: number): InternalResultEvidenceRef {
  return {
    slotId: 'source', docId: 'doc-a', blockId: 'P1',
    sentenceId: `P1:S${index}`, sentenceAlias: `T${index}`,
  }
}
const finding: InternalResultFinding = {
  findingId: 'F1', label: 'fail', conclusion: 'Finding one',
  comparisonModeId: 'scope_local', evidenceRefs: [evidence(1)],
}
const result: DocumentConsistencyQcResult = {
  flowId: 'document_consistency_qc', flowRunId: 'run-1', capabilityId: 'internal_dsur',
  flowStatus: 'success', comparisonRunStatus: 'success', finalizationStatus: 'completed',
  fallbackComparisonModes: [], findings: [finding],
  scopeResults: [{
    slotId: 'source', docId: 'doc-a', scopeId: 'scope-1', headingPath: ['Section'],
    outlineHeadingBlockId: 'doc-a:H1', semanticModuleId: 'module-1',
    executionStatus: 'complete', hasSuccessfulCheck: true,
  }],
}

function shellProps(overrides: Partial<ResultShellLoadedProps> = {}): ResultShellLoadedProps {
  return {
    taskDisplayName: 'Task', functionViewQuery: { mode: 'all' },
    availableSemanticModuleIds: ['module-1'], result, reviewState: null,
    document: documentView, documentStatus: 'ready', documentError: null,
    outlineEntries: [{ blockId: 'doc-a:H1', title: 'Section', headingLevel: 1, headingPath: ['Section'], docOrderIndex: 0 }],
    scopeResultsByOutlineBlockId: new Map(), activeOutlineBlockId: null,
    selectedFindingId: finding.findingId, selectedFinding: finding,
    selectedEvidenceLocations: finding.evidenceRefs,
    focusedEvidenceLocationKey: null, focusedEvidenceLocation: null,
    focusedBlockId: null, focusedSentence: null, sourceAnnotations: new Map(),
    revisionItems: [], commentItems: [],
    activeSourceAnnotationId: null, savingAnnotationId: null, savingFindingId: null,
    onNavigateRevision: () => {}, onNavigateComment: () => {},
    onSourceAnnotationActivate: () => {}, onCreateHighlight: async () => {},
    onDeleteHighlight: async () => {}, onCreateComment: async () => {},
    onUpdateComment: async () => {}, onDeleteComment: async () => {},
    onCreateEdit: async () => {}, onUpdateEdit: async () => {}, onDeleteEdit: async () => {},
    onSelectHeading: () => {}, onSelectFinding: () => {}, onFocusEvidence: () => {},
    onPatchFindingReview: async () => {}, onClearFocusedSentence: () => {},
    onClearFocusedBlock: () => {}, onClearActiveSourceAnnotation: () => {},
    onFunctionViewQueryChange: () => {},
    ...overrides,
  }
}

const mounted: Array<() => void> = []
afterEach(() => { while (mounted.length) mounted.pop()?.() })
function render(overrides: Partial<ResultShellLoadedProps> = {}) {
  const host = document.createElement('div')
  document.body.append(host)
  const root = createRoot(host)
  act(() => root.render(createElement(MemoryRouter, null,
    createElement(ResultShellLoaded, shellProps(overrides)))))
  mounted.push(() => { act(() => root.unmount()); host.remove() })
  return {
    host,
    rerender(nextOverrides: Partial<ResultShellLoadedProps>) {
      act(() => root.render(createElement(MemoryRouter, null,
        createElement(ResultShellLoaded, shellProps(nextOverrides)))))
    },
  }
}

describe('ResultShellLoaded source evidence viewport production path', () => {
  it('renders evidence viewports by default without legacy expansion controls', () => {
    const { host } = render()
    expect(host.querySelector('[data-finding-source-document-panel="true"]')).not.toBeNull()
    expect(host.querySelectorAll('[data-source-evidence-viewport="true"]')).toHaveLength(1)
    expect(host.querySelector('[data-finding-filtered-document-workspace]')).toBeNull()
    expect(host.textContent).not.toContain('显示更多')
    expect(host.textContent).not.toContain('显示整段')
    expect(host.textContent).not.toContain('展开本节')
    expect(host.textContent).not.toContain('查看全文')
    expect(host.textContent).not.toContain('返回问题上下文')
  })

  it('renders all eight evidence occurrences as independent production viewports', () => {
    const eight = Array.from({ length: 8 }, (_, index) => evidence(index + 1))
    const eightFinding = { ...finding, evidenceRefs: eight }
    const { host } = render({
      selectedFinding: eightFinding,
      selectedEvidenceLocations: eight,
    })
    expect(host.querySelectorAll('[data-source-evidence-viewport="true"]')).toHaveLength(8)
    expect(new Set([...host.querySelectorAll<HTMLElement>('[data-source-evidence-viewport="true"]')]
      .map((item) => item.dataset.viewportKey)).size).toBe(8)
  })

  it('keeps Result Full canonical and free of Finding evidence presentation', () => {
    const session = render()
    const { host } = session
    act(() => host.querySelector<HTMLButtonElement>('[data-result-show-full-document="true"]')?.click())

    const nextFinding: InternalResultFinding = {
      ...finding,
      findingId: 'F2',
      conclusion: 'Finding two',
      evidenceRefs: [evidence(2)],
    }
    session.rerender({
      result: { ...result, findings: [finding, nextFinding] },
      selectedFindingId: nextFinding.findingId,
      selectedFinding: nextFinding,
      selectedEvidenceLocations: nextFinding.evidenceRefs,
    })

    expect(host.querySelector('[data-document-canvas="true"]')).not.toBeNull()
    expect(host.querySelector('[data-source-evidence-viewport="true"]')).toBeNull()
    expect(host.querySelector('[data-finding-target="true"]')).toBeNull()
    expect(host.querySelector('[data-document-annotation-toolbar="true"]')).not.toBeNull()
  })
})
