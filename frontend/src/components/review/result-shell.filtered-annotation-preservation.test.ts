// @vitest-environment happy-dom

import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ResultShellLoaded,
  type ResultShellLoadedProps,
} from '@/components/review/result-shell'
import { evidenceLocationKey } from '@/lib/result-review-selection'
import type {
  DocumentConsistencyQcResult,
  InternalResultEvidenceRef,
  InternalResultFinding,
} from '@/types/document-consistency-qc'
import type { DocumentView } from '@/types/document-review'
import type {
  SourceAnnotation,
  SourceSentenceAnchor,
  SourceTextRange,
} from '@/types/source-annotation'

const evidence: InternalResultEvidenceRef = {
  slotId: 'source',
  docId: 'doc-a',
  blockId: 'B1',
  sentenceId: 'B1:S2',
  sentenceAlias: 'T1',
}

const finding: InternalResultFinding = {
  findingId: 'F1',
  label: 'fail',
  conclusion: 'Finding one',
  comparisonModeId: 'scope_local',
  evidenceRefs: [evidence],
}

const documentView: DocumentView = {
  docId: 'doc-a',
  fileName: 'source.docx',
  displayName: 'Source',
  blocks: [{
    blockId: 'doc-a:B1',
    sourceBlockId: 'B1',
    kind: 'paragraph',
    docOrderIndex: 0,
    headingPath: [],
    displayText: 'Leading. Target sentence. Trailing.',
    sentences: [
      { sentenceId: 'B1:S1', rawText: 'Leading.', normalizedText: 'Leading.' },
      {
        sentenceId: 'B1:S2',
        rawText: 'Target sentence.',
        normalizedText: 'Target sentence.',
      },
      { sentenceId: 'B1:S3', rawText: 'Trailing.', normalizedText: 'Trailing.' },
    ],
  }],
}

const result: DocumentConsistencyQcResult = {
  flowId: 'document_consistency_qc',
  flowRunId: 'run-a',
  capabilityId: 'internal_dsur',
  flowStatus: 'success',
  comparisonRunStatus: 'success',
  finalizationStatus: 'completed',
  fallbackComparisonModes: [],
  findings: [finding],
  scopeResults: [],
}

function loadedProps(
  overrides: Partial<ResultShellLoadedProps> = {},
): ResultShellLoadedProps {
  return {
    taskDisplayName: 'Task',
    functionViewQuery: { mode: 'all' },
    availableSemanticModuleIds: [],
    result,
    reviewState: {
      flowRunId: 'run-a',
      entriesByFindingId: new Map([[
        'F1',
        {
          findingId: 'F1',
          decision: 'confirmed',
          marked: true,
          note: 'keep me',
          updatedAt: '2026-01-01T00:00:00Z',
        },
      ]]),
    },
    document: documentView,
    documentStatus: 'ready',
    documentError: null,
    outlineEntries: [],
    scopeResultsByOutlineBlockId: new Map(),
    activeOutlineBlockId: null,
    selectedFindingId: 'F1',
    selectedFinding: finding,
    selectedEvidenceLocations: [evidence],
    focusedEvidenceLocationKey: evidenceLocationKey(evidence),
    focusedEvidenceLocation: evidence,
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
    ...overrides,
  }
}

function setNativeValue(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
  const prototype = element instanceof HTMLTextAreaElement
    ? HTMLTextAreaElement.prototype
    : HTMLInputElement.prototype
  Object.getOwnPropertyDescriptor(prototype, 'value')?.set?.call(element, value)
  element.dispatchEvent(new Event('input', { bubbles: true }))
}

let container: HTMLDivElement
let root: Root

beforeEach(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  vi.spyOn(Range.prototype, 'getBoundingClientRect').mockReturnValue({
    x: 0,
    y: 0,
    top: 0,
    left: 0,
    bottom: 20,
    right: 100,
    width: 100,
    height: 20,
    toJSON: () => ({}),
  } as DOMRect)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.restoreAllMocks()
})

function renderLoaded(overrides: Partial<ResultShellLoadedProps> = {}) {
  act(() => root.render(
    createElement(
      MemoryRouter,
      null,
      createElement(ResultShellLoaded, loadedProps(overrides)),
    ),
  ))
}

function selectTargetText() {
  const sentence = container.querySelector('[data-sentence-id="B1:S2"]') as HTMLElement
  const walker = document.createTreeWalker(sentence, NodeFilter.SHOW_TEXT)
  let text = walker.nextNode() as Text | null
  while (
    text &&
    (
      text.data.length < 6 ||
      text.parentElement?.closest('[data-source-annotation-ui="true"]')
    )
  ) {
    text = walker.nextNode() as Text | null
  }
  expect(text).not.toBeNull()
  const range = document.createRange()
  range.setStart(text!, 0)
  range.setEnd(text!, 6)
  window.getSelection()?.removeAllRanges()
  window.getSelection()?.addRange(range)
  act(() => sentence.dispatchEvent(new MouseEvent('mouseup', { bubbles: true })))
}

function clickButton(rootElement: ParentNode, text: string) {
  const button = [...rootElement.querySelectorAll('button')]
    .find(
      (candidate) =>
        candidate.textContent === text ||
        candidate.getAttribute('aria-label') === text,
    )
  act(() => button?.click())
}

describe('ResultShellLoaded evidence viewport annotation state preservation', () => {
  it('creates comments and revisions and cancels without changing Finding domains', async () => {
    const onSelectFinding = vi.fn()
    const onFocusEvidence = vi.fn()
    const onPatchFindingReview = vi.fn(async () => {})
    const annotations = new Map<string, SourceAnnotation>()
    let commentItems: SourceAnnotation[] = []
    let revisionItems: SourceAnnotation[] = []
    let renderCurrent = () => {}
    const onCreateComment = vi.fn(async (input: {
      anchor: SourceSentenceAnchor
      range: SourceTextRange
      content: string
    }) => {
      const created: SourceAnnotation = {
        annotationId: 'ann-created-comment',
        anchor: input.anchor,
        kind: 'comment',
        range: input.range,
        content: input.content,
        createdAt: '2026-01-01T00:00:00Z',
        updatedAt: '2026-01-01T00:00:00Z',
      }
      annotations.set(created.annotationId, created)
      commentItems = [created]
      renderCurrent()
    })
    const onCreateEdit = vi.fn(async (input: {
      anchor: SourceSentenceAnchor
      range: SourceTextRange
      replacementText: string
    }) => {
      const created: SourceAnnotation = {
        annotationId: 'ann-created-edit',
        anchor: input.anchor,
        kind: 'edit',
        range: input.range,
        replacementText: input.replacementText,
        createdAt: '2026-01-01T00:00:00Z',
        updatedAt: '2026-01-01T00:00:00Z',
      }
      annotations.set(created.annotationId, created)
      revisionItems = [created]
      renderCurrent()
    })
    renderCurrent = () => renderLoaded({
      sourceAnnotations: new Map(annotations),
      commentItems,
      revisionItems,
      onCreateComment,
      onCreateEdit,
      onSelectFinding,
      onFocusEvidence,
      onPatchFindingReview,
    })
    renderCurrent()
    onSelectFinding.mockClear()
    const sentenceMembership = [...container.querySelectorAll('[data-sentence-id]')]
      .map((element) => element.getAttribute('data-sentence-id'))

    selectTargetText()
    clickButton(container, '批注')
    const commentInput = document.body.querySelector(
      '[data-source-comment-popover="true"] textarea',
    ) as HTMLTextAreaElement
    act(() => setNativeValue(commentInput, 'new comment'))
    await act(async () => clickButton(document.body, '保存'))
    expect(onCreateComment).toHaveBeenCalledWith({
      anchor: {
        slotId: 'source',
        docId: 'doc-a',
        blockId: 'B1',
        sentenceId: 'B1:S2',
      },
      range: { startOffset: 0, endOffset: 6 },
      content: 'new comment',
    })
    expect(container.querySelector(
      '[data-source-comment-annotation-id="ann-created-comment"]',
    )).toBeTruthy()

    selectTargetText()
    clickButton(container, '修订')
    const editInput = document.body.querySelector(
      '[data-source-edit-popover="true"] input',
    ) as HTMLInputElement
    act(() => setNativeValue(editInput, 'replacement'))
    await act(async () => clickButton(document.body, '保存'))
    expect(onCreateEdit).toHaveBeenCalledTimes(1)
    expect(container.querySelector(
      '[data-source-annotation-id="ann-created-edit"]',
    )).toBeTruthy()

    selectTargetText()
    clickButton(container, '批注')
    clickButton(document.body, '取消')
    expect(onCreateComment).toHaveBeenCalledTimes(1)

    expect(onSelectFinding).not.toHaveBeenCalled()
    expect(onFocusEvidence).not.toHaveBeenCalled()
    expect(onPatchFindingReview).not.toHaveBeenCalled()
    expect(container.querySelector('[data-focused-finding-target="true"]')).toBeTruthy()
    expect(container.querySelector('[data-finding-source-document-panel="true"]')).not.toBeNull()
    expect([...container.querySelectorAll('[data-sentence-id]')]
      .map((element) => element.getAttribute('data-sentence-id'))).toEqual(
      sentenceMembership,
    )
  })

  it('updates and deletes a visible paragraph comment without changing viewport content or Finding domains', async () => {
    const annotation: SourceAnnotation = {
      annotationId: 'ann-comment',
      anchor: {
        slotId: 'source',
        docId: 'doc-a',
        blockId: 'B1',
        sentenceId: 'B1:S2',
      },
      kind: 'comment',
      range: { startOffset: 0, endOffset: 6 },
      content: 'old',
      createdAt: '2026-01-01T00:00:00Z',
      updatedAt: '2026-01-01T00:00:00Z',
    }
    const onUpdateComment = vi.fn(async () => {})
    const onDeleteComment = vi.fn(async () => {})
    const onSelectFinding = vi.fn()
    const onFocusEvidence = vi.fn()
    const onPatchFindingReview = vi.fn(async () => {})
    renderLoaded({
      sourceAnnotations: new Map([[annotation.annotationId, annotation]]),
      commentItems: [annotation],
      onUpdateComment,
      onDeleteComment,
      onSelectFinding,
      onFocusEvidence,
      onPatchFindingReview,
    })
    onSelectFinding.mockClear()
    const initialFragments = container.querySelectorAll(
      '[data-projected-fragment="true"]',
    ).length

    clickButton(container, '查看批注')
    const input = document.body.querySelector(
      '[data-source-comment-popover="true"] textarea',
    ) as HTMLTextAreaElement
    act(() => setNativeValue(input, 'updated'))
    await act(async () => clickButton(document.body, '保存'))
    expect(onUpdateComment).toHaveBeenCalledWith({
      annotationId: 'ann-comment',
      content: 'updated',
    })

    clickButton(container, '查看批注')
    await act(async () => clickButton(document.body, '删除'))
    expect(onDeleteComment).toHaveBeenCalledWith('ann-comment')
    expect(container.querySelectorAll('[data-projected-fragment="true"]')).toHaveLength(
      initialFragments,
    )
    expect(onSelectFinding).not.toHaveBeenCalled()
    expect(onFocusEvidence).not.toHaveBeenCalled()
    expect(onPatchFindingReview).not.toHaveBeenCalled()
  })
})
