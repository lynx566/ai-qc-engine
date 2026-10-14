// @vitest-environment happy-dom

import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchCandidateScopeDocument } from '@/api/candidate-scope-document'
import { fetchDocumentConsistencyQcResult } from '@/api/document-consistency-qc'
import { fetchFindingReviewState, patchFindingReview } from '@/api/finding-review'
import {
  createSourceComment,
  createSourceEdit,
  fetchSourceAnnotations,
} from '@/api/source-annotation'
import { ResultShell } from '@/components/review/result-shell'
import type { ResultFindingsPanelProps } from '@/components/review/result-findings-panel'
import { blockDomId, sentenceDomId } from '@/lib/document-anchors'
import { evidenceLocationKey } from '@/lib/result-review-selection'
import { extractSourceTextRangeFromSelection } from '@/lib/source-text-selection'
import type {
  DocumentConsistencyQcResult,
  InternalResultEvidenceRef,
} from '@/types/document-consistency-qc'
import type { FindingReviewEntry, FindingReviewStatePayload } from '@/types/finding-review'

vi.mock('@/api/candidate-scope-document', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/candidate-scope-document')>()),
  fetchCandidateScopeDocument: vi.fn(),
}))

vi.mock('@/api/document-consistency-qc', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/document-consistency-qc')>()),
  fetchDocumentConsistencyQcResult: vi.fn(),
}))

vi.mock('@/api/finding-review', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/finding-review')>()),
  fetchFindingReviewState: vi.fn(),
  patchFindingReview: vi.fn(),
}))

vi.mock('@/api/source-annotation', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/source-annotation')>()),
  createSourceComment: vi.fn(),
  createSourceEdit: vi.fn(),
  fetchSourceAnnotations: vi.fn(),
}))

// The production panel exposes focus callbacks without rendering evidence-focus controls.
// Keep only those controls/state probes here; selection and review actions use the real Queue.
vi.mock('@/components/review/result-findings-panel', async (importOriginal) => {
  const actual = await importOriginal<
    typeof import('@/components/review/result-findings-panel')
  >()
  const { createElement } = await import('react')
  return {
    ...actual,
    ResultFindingsPanel: (props: ResultFindingsPanelProps) =>
      createElement(
        'div',
        { 'data-review-workspace-probe': 'true', className: 'flex min-h-0 flex-1 flex-col' },
        createElement(actual.ResultFindingsPanel, props),
        createElement('span', { 'data-selected-finding': 'true' }, props.selectedFindingId ?? ''),
        createElement(
          'span',
          { 'data-selected-evidence': 'true' },
          props.selectedEvidenceLocations.map((location) => location.sentenceId).join(','),
        ),
        createElement('span', { 'data-focused-evidence': 'true' }, props.focusedEvidenceLocationKey ?? ''),
        createElement('span', { 'data-review-flow-run-id': 'true' }, props.reviewState?.flowRunId ?? ''),
        ...[1, 2].map((index) => createElement(
          'button',
          {
            key: index,
            type: 'button',
            'data-focus-evidence-index': index,
            onClick: () => {
              const location = props.selectedEvidenceLocations[index]
              if (location) props.onFocusEvidence(location)
            },
          },
          index === 1 ? 'focus second evidence' : 'focus non-rendered evidence sentence',
        )),
      ),
  }
})

const evidenceA: InternalResultEvidenceRef = {
  slotId: 'source',
  docId: 'doc_test',
  blockId: 'C0011',
  sentenceId: 'C0011:S001',
  sentenceAlias: 'T0001',
}

const evidenceB: InternalResultEvidenceRef = {
  slotId: 'source',
  docId: 'doc_test',
  blockId: 'C0020',
  sentenceId: 'C0020:S001',
  sentenceAlias: 'T0002',
}

const evidenceWithoutRenderedSentence: InternalResultEvidenceRef = {
  slotId: 'source',
  docId: 'doc_test',
  blockId: 'C0030',
  sentenceId: 'C0030:S999',
  sentenceAlias: 'T0003',
}

const resultFixture: DocumentConsistencyQcResult = {
  flowId: 'document_consistency_qc',
  flowRunId: 'run_1',
  capabilityId: 'clinical_safety',
  flowStatus: 'completed',
  comparisonRunStatus: 'completed',
  finalizationStatus: 'completed',
  fallbackComparisonModes: [],
  findings: [
    {
      findingId: 'F1',
      label: 'fail',
      conclusion: 'Multi-location finding',
      comparisonModeId: 'scope_local',
      evidenceRefs: [evidenceA, evidenceB, evidenceWithoutRenderedSentence],
    },
  ],
  scopeResults: [
    {
      slotId: 'source',
      docId: 'doc_test',
      scopeId: 'scope_1',
      headingPath: ['First section'],
      outlineHeadingBlockId: 'C0010',
      semanticModuleId: 'clinical_safety',
      executionStatus: 'complete',
      hasSuccessfulCheck: true,
    },
  ],
}

const flushAsyncWork = async () => {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
    await Promise.resolve()
  })
}

let container: HTMLDivElement
let root: Root

function selectFinding(findingId = 'F1') {
  const button = container.querySelector<HTMLButtonElement>(
    '[data-finding-queue-item="' + findingId + '"] [data-finding-queue-select]',
  )!
  act(() => button.click())
}

function focusEvidence(index: 1 | 2) {
  act(() => container.querySelector<HTMLButtonElement>(
    '[data-focus-evidence-index="' + index + '"]',
  )!.click())
}

beforeEach(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  vi.mocked(fetchDocumentConsistencyQcResult).mockResolvedValue(resultFixture)
  vi.mocked(fetchFindingReviewState).mockResolvedValue({
    flowRunId: 'run_1',
    entriesByFindingId: new Map(),
  })
  vi.mocked(patchFindingReview).mockResolvedValue({
    flowRunId: 'run_1',
    entriesByFindingId: new Map(),
  })
  vi.mocked(fetchSourceAnnotations).mockResolvedValue({
    flowRunId: 'run_1',
    annotationsById: new Map(),
  })
  vi.mocked(fetchCandidateScopeDocument).mockResolvedValue({
    doc_id: 'doc_test',
    file_name: 'sample.docx',
    display_name: 'sample.docx',
    content_blocks: [
      {
        block_id: 'C0010',
        kind: 'heading',
        raw_text: 'First section',
        normalized_text: 'First section',
        doc_order_index: 10,
        heading_path: ['First section'],
        meta: { heading_level: 1 },
      },
      {
        block_id: 'C0011',
        kind: 'paragraph',
        raw_text: 'First evidence',
        normalized_text: 'First evidence',
        doc_order_index: 11,
        heading_path: ['First section'],
        sentences: [
          {
            sentence_id: 'C0011:S001',
            raw_text: 'First evidence',
            normalized_text: 'First evidence',
          },
        ],
      },
      {
        block_id: 'C0020',
        kind: 'paragraph',
        raw_text: 'Second evidence',
        normalized_text: 'Second evidence',
        doc_order_index: 20,
        heading_path: ['First section'],
        sentences: [
          {
            sentence_id: 'C0020:S001',
            raw_text: 'Second evidence',
            normalized_text: 'Second evidence',
          },
        ],
      },
      {
        block_id: 'C0030',
        kind: 'heading',
        raw_text: 'Second section',
        normalized_text: 'Second section',
        doc_order_index: 30,
        heading_path: ['Second section'],
        meta: { heading_level: 1 },
        sentences: [
          {
            sentence_id: 'C0030:S999',
            raw_text: 'Second section',
            normalized_text: 'Second section',
          },
        ],
      },
    ],
  })

  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
    configurable: true,
    value: vi.fn(),
  })
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.clearAllMocks()
  vi.restoreAllMocks()
})

describe('ResultShell R1 review workspace selection', () => {
  it('updates shared toolbar counts from Source creation and keeps annotations visible across views', async () => {
    vi.spyOn(Range.prototype, 'getBoundingClientRect').mockReturnValue({
      top: 0, left: 0, bottom: 20, right: 100, width: 100, height: 20,
    } as DOMRect)
    const anchor = { slotId: 'source', docId: 'doc_test', blockId: 'C0011', sentenceId: 'C0011:S001' }
    vi.mocked(createSourceComment).mockResolvedValueOnce({
      annotationId: 'shared-comment', kind: 'comment', anchor,
      range: { startOffset: 0, endOffset: 5 }, content: 'Shared comment',
      createdAt: '2026-10-09T00:00:00Z', updatedAt: '2026-10-09T00:00:00Z',
    })
    vi.mocked(createSourceEdit).mockResolvedValueOnce({
      annotationId: 'shared-edit', kind: 'edit', anchor,
      range: { startOffset: 0, endOffset: 5 }, replacementText: 'Replacement',
      createdAt: '2026-10-09T00:00:00Z', updatedAt: '2026-10-09T00:00:00Z',
    })
    act(() => root.render(createElement(ResultShell, { flowRunId: 'run_1', taskDisplayName: 'Document consistency' })))
    await flushAsyncWork()
    selectFinding()
    const toolbar = container.querySelector('[data-result-workspace-toolbar]')!
    expect(toolbar.querySelector('[data-source-annotation-label="revision"]')?.textContent).toBe('修订 0')
    expect(toolbar.querySelector('[data-source-annotation-label="comment"]')?.textContent).toBe('批注 0')

    for (const kind of ['comment', 'edit'] as const) {
      const sentence = container.querySelector('[data-sentence-id="C0011:S001"][data-sentence-range-enabled="true"]')!
      const walker = document.createTreeWalker(sentence, NodeFilter.SHOW_TEXT)
      let text = walker.nextNode() as Text | null
      while (text && text.data.length < 5) text = walker.nextNode() as Text | null
      expect(text).not.toBeNull()
      const range = document.createRange()
      range.setStart(text!, 0)
      range.setEnd(text!, 5)
      window.getSelection()?.removeAllRanges()
      window.getSelection()?.addRange(range)
      act(() => container.querySelector('[data-source-document-interaction]')!.dispatchEvent(new MouseEvent('mouseup', { bubbles: true })))
      const action = [...container.querySelectorAll<HTMLButtonElement>('[data-source-mark-action] button')]
        .find(button => button.textContent === (kind === 'comment' ? '批注' : '修订'))!
      act(() => action.click())
      const popover = document.body.querySelector(`[data-source-${kind}-popover]`)!
      const input = popover.querySelector<HTMLInputElement | HTMLTextAreaElement>('input, textarea')!
      Object.getOwnPropertyDescriptor(kind === 'comment' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype, 'value')!.set!.call(input, kind === 'comment' ? 'Shared comment' : 'Replacement')
      act(() => input.dispatchEvent(new Event('input', { bubbles: true })))
      await act(async () => [...popover.querySelectorAll<HTMLButtonElement>('button')].find(button => button.textContent === '保存')!.click())
      expect(toolbar.querySelector(`[data-source-annotation-label="${kind === 'comment' ? 'comment' : 'revision'}"]`)?.textContent)
        .toBe(kind === 'comment' ? '批注 1' : '修订 1')
    }
    expect(container.querySelector('[data-source-comment-annotation-id="shared-comment"]')).not.toBeNull()
    expect(container.querySelector('[data-source-annotation-id="shared-edit"]')).not.toBeNull()
    act(() => toolbar.querySelector<HTMLButtonElement>('[data-result-show-full-document]')!.click())
    expect(container.querySelector('[data-result-workspace-toolbar]')).toBe(toolbar)
    expect(toolbar.querySelectorAll('[data-source-annotation-navigator]')).toHaveLength(1)
    expect(toolbar.querySelector('[data-source-annotation-label="comment"]')?.textContent).toBe('批注 1')
    expect(toolbar.querySelector('[data-source-annotation-label="revision"]')?.textContent).toBe('修订 1/1')
    expect(toolbar.querySelectorAll('[data-source-annotation-nav]')).toHaveLength(2)
    expect(toolbar.querySelectorAll('button')).toHaveLength(5)
    expect(container.querySelector('[data-source-comment-annotation-id="shared-comment"]')).not.toBeNull()
    expect(container.querySelector('[data-source-annotation-id="shared-edit"]')).not.toBeNull()
    act(() => toolbar.querySelector<HTMLButtonElement>('[data-result-show-findings-overview]')!.click())
    expect(container.querySelector('[data-result-workspace-toolbar]')).toBe(toolbar)
    expect(toolbar.querySelectorAll('[data-source-annotation-context]')).toHaveLength(1)
    expect(toolbar.querySelector('[data-source-annotation-navigator]')).toBeNull()
    expect(toolbar.querySelector('[data-source-annotation-label="revision"]')?.textContent).toBe('修订 1')
    expect(toolbar.querySelector('[data-source-annotation-label="comment"]')?.textContent).toBe('批注 1')
    expect(container.querySelector('[data-source-comment-annotation-id="shared-comment"]')).not.toBeNull()
    expect(container.querySelector('[data-source-annotation-id="shared-edit"]')).not.toBeNull()
  })

  it('initializes to the fail queue head even when need-review appears first in the Result', async () => {
    vi.mocked(fetchDocumentConsistencyQcResult).mockResolvedValue({
      ...resultFixture,
      findings: [
        { ...resultFixture.findings[0]!, label: 'need_review' },
        { ...resultFixture.findings[0]!, findingId: 'F2', conclusion: 'Fail first in Queue' },
      ],
    })
    act(() => root.render(createElement(ResultShell, { flowRunId: 'run_1', taskDisplayName: 'Document consistency' })))
    await flushAsyncWork()
    expect(container.querySelector('[data-selected-finding]')?.textContent).toBe('F2')
    expect([...container.querySelectorAll('[data-finding-queue-item]')].map(item => item.getAttribute('data-finding-queue-item'))).toEqual(['F2', 'F1'])
    expect(container.querySelector('[data-finding-queue-item="F2"]')?.getAttribute('data-finding-selected')).toBe('true')
  })

  it('selects the queue head after async Result loading settles', async () => {
    act(() => root.render(createElement(ResultShell, {
      flowRunId: 'run_1',
      taskDisplayName: 'Document consistency',
    })))
    await flushAsyncWork()

    expect(container.querySelector('[data-selected-finding]')?.textContent).toBe('F1')
    expect(container.querySelector('[data-result-findings-panel-open="true"]')).not.toBeNull()
  })

  it('keeps all finding evidence selected while focusing one reader sentence', async () => {
    act(() => root.render(createElement(ResultShell, {
      flowRunId: 'run_1',
      taskDisplayName: 'Document consistency',
    })))
    await flushAsyncWork()

    selectFinding()
    focusEvidence(1)

    expect(container.querySelector('[data-selected-finding]')?.textContent).toBe('F1')
    expect(container.querySelector('[data-selected-evidence]')?.textContent).toBe(
      'C0011:S001,C0020:S001,C0030:S999',
    )
    expect(container.querySelector('[data-focused-evidence]')?.textContent).toBe(
      evidenceLocationKey(evidenceB),
    )
    const pane = container.querySelector('[data-result-document-pane]')
    const viewports = [...pane!.querySelectorAll<HTMLElement>('[data-source-evidence-viewport="true"]')]
    expect(viewports).toHaveLength(3)
    expect(viewports.map((viewport) =>
      viewport.querySelector('[data-focused-finding-target="true"]')?.getAttribute('data-sentence-id'),
    )).toEqual(['C0011:S001', 'C0020:S001', 'C0030:S999'])
  })

  it('reconciles evidence focus when selection changes through the real Queue', async () => {
    vi.mocked(fetchDocumentConsistencyQcResult).mockResolvedValue({
      ...resultFixture,
      findings: [...resultFixture.findings, {
        ...resultFixture.findings[0]!, findingId: 'F2', conclusion: 'Single-location finding', evidenceRefs: [evidenceA],
      }],
    })
    act(() => root.render(createElement(ResultShell, { flowRunId: 'run_1', taskDisplayName: 'Document consistency' })))
    await flushAsyncWork()
    focusEvidence(1)
    expect(container.querySelector('[data-focused-evidence]')?.textContent).toBe(evidenceLocationKey(evidenceB))
    selectFinding('F2')
    expect(container.querySelector('[data-selected-finding]')?.textContent).toBe('F2')
    expect(container.querySelector('[data-selected-evidence]')?.textContent).toBe('C0011:S001')
    expect(container.querySelector('[data-focused-evidence]')?.textContent).toBe('')
    expect(container.querySelector('[data-finding-queue-item="F2"]')?.getAttribute('data-finding-selected')).toBe('true')
  })

  it('does not use page-wide full-reader anchors for filtered evidence focus', async () => {
    const outsideAnchor = document.createElement('span')
    const outsideScrollIntoView = vi.fn()
    outsideAnchor.id = sentenceDomId('doc_test', evidenceB.sentenceId)
    Object.defineProperty(outsideAnchor, 'scrollIntoView', {
      configurable: true,
      value: outsideScrollIntoView,
    })
    document.body.appendChild(outsideAnchor)

    act(() => root.render(createElement(ResultShell, {
      flowRunId: 'run_1',
      taskDisplayName: 'Document consistency',
    })))
    await flushAsyncWork()

    selectFinding()
    focusEvidence(1)

    expect(container.querySelector('[data-focused-evidence]')?.textContent).toBe(
      evidenceLocationKey(evidenceB),
    )
    expect(outsideScrollIntoView).not.toHaveBeenCalled()
    outsideAnchor.remove()
  })

  it('retains canonical evidence focus for a projected heading target', async () => {
    act(() => root.render(createElement(ResultShell, {
      flowRunId: 'run_1',
      taskDisplayName: 'Document consistency',
    })))
    await flushAsyncWork()

    selectFinding()
    focusEvidence(2)

    expect(container.querySelector('[data-selected-finding]')?.textContent).toBe('F1')
    expect(container.querySelector('[data-focused-evidence]')?.textContent).toBe(
      evidenceLocationKey(evidenceWithoutRenderedSentence),
    )
  })

  it('preserves finding evidence focus without a findings-mode document navigator', async () => {
    act(() => root.render(createElement(ResultShell, {
      flowRunId: 'run_1',
      taskDisplayName: 'Document consistency',
    })))
    await flushAsyncWork()

    selectFinding()
    focusEvidence(1)

    expect(container.querySelector('[data-result-document-navigator]')).toBeNull()
    expect(container.querySelector('[data-finding-source-document-panel="true"]')).not.toBeNull()

    expect(container.querySelector('[data-selected-finding]')?.textContent).toBe('F1')
    expect(container.querySelector('[data-selected-evidence]')?.textContent).toBe(
      'C0011:S001,C0020:S001,C0030:S999',
    )
    expect(container.querySelector('[data-focused-evidence]')?.textContent).toBe(
      evidenceLocationKey(evidenceB),
    )
  })

  it.each([839.5, 840])('preserves dormant Finding evidence focus during canonical outline navigation at %spx', async (width) => {
    vi.spyOn(window, 'matchMedia').mockReturnValue({
      matches: width >= 840, media: '(min-width: 840px)', onchange: null,
      addEventListener: vi.fn(), removeEventListener: vi.fn(),
      addListener: vi.fn(), removeListener: vi.fn(), dispatchEvent: () => true,
    })
    act(() => root.render(createElement(ResultShell, {
      flowRunId: 'run_1',
      taskDisplayName: 'Document consistency',
    })))
    await flushAsyncWork()

    focusEvidence(1)
    act(() => container.querySelector<HTMLButtonElement>(
      '[data-result-show-full-document="true"]',
    )?.click())
    const outline = container.querySelector('[data-result-outline-inline]')!
    const headingButton = [...container.querySelectorAll<HTMLButtonElement>(
      '[data-result-document-navigator] button',
    )].find((button) => button.textContent?.includes('First section'))
    act(() => headingButton?.click())
    const target = document.getElementById(blockDomId('doc_test:C0010'))!
    expect(target.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' })
    expect(document.activeElement).toBe(target)
    expect(container.querySelector('[data-result-outline-inline]')).toBe(outline)
    act(() => container.querySelector<HTMLButtonElement>(
      '[data-result-show-findings-overview="true"]',
    )?.click())

    expect(container.querySelector('[data-focused-evidence]')?.textContent).toBe(
      evidenceLocationKey(evidenceB),
    )
  })

  it.each([839.5, 840])('preserves dormant Finding evidence focus during canonical annotation navigation at %spx', async (width) => {
    vi.spyOn(window, 'matchMedia').mockReturnValue({
      matches: width >= 840, media: '(min-width: 840px)', onchange: null,
      addEventListener: vi.fn(), removeEventListener: vi.fn(),
      addListener: vi.fn(), removeListener: vi.fn(), dispatchEvent: () => true,
    })
    vi.mocked(fetchSourceAnnotations).mockResolvedValue({
      flowRunId: 'run_1',
      annotationsById: new Map([[
        'edit-1',
        {
          annotationId: 'edit-1',
          anchor: {
            slotId: 'source',
            docId: 'doc_test',
            blockId: 'C0011',
            sentenceId: 'C0011:S001',
          },
          kind: 'edit',
          range: { startOffset: 0, endOffset: 5 },
          replacementText: 'Edited',
          createdAt: '2026-01-01T00:00:00Z',
          updatedAt: '2026-01-01T00:00:00Z',
        },
      ]]),
    })
    act(() => root.render(createElement(ResultShell, {
      flowRunId: 'run_1',
      taskDisplayName: 'Document consistency',
    })))
    await flushAsyncWork()

    focusEvidence(1)
    act(() => container.querySelector<HTMLButtonElement>(
      '[data-result-show-full-document="true"]',
    )?.click())
    act(() => container.querySelector<HTMLButtonElement>('[aria-label="下一条修订"]')?.click())
    const annotationTarget = container.querySelector<HTMLElement>(
      '[data-result-document-pane] [data-source-annotation-id="edit-1"]',
    )!
    expect(annotationTarget).not.toBeNull()
    expect(annotationTarget.scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' })
    expect(document.activeElement).toBe(annotationTarget)
    expect(container.querySelector('[data-result-outline-inline]')).not.toBeNull()
    act(() => container.querySelector<HTMLButtonElement>(
      '[data-result-show-findings-overview="true"]',
    )?.click())

    expect(container.querySelector('[data-focused-evidence]')?.textContent).toBe(
      evidenceLocationKey(evidenceB),
    )
  })

  it('preserves finding and evidence focus across confirm, mark, and saved note interactions in the Queue', async () => {
    let entry: FindingReviewEntry = {
      findingId: 'F1', decision: 'pending', marked: false, updatedAt: '2026-10-08T00:00:00Z',
    }
    vi.mocked(patchFindingReview).mockImplementation(async (_flowRunId, findingId, patch) => {
      entry = { ...entry, ...patch, note: patch.note ?? entry.note }
      return { flowRunId: 'run_1', entriesByFindingId: new Map([[findingId, { ...entry }]]) }
    })
    act(() => root.render(createElement(ResultShell, {
      flowRunId: 'run_1', taskDisplayName: 'Document consistency',
    })))
    await flushAsyncWork()
    selectFinding()
    focusEvidence(1)

    const item = container.querySelector<HTMLElement>('[data-finding-queue-item="F1"]')!
    act(() => item.querySelector<HTMLButtonElement>('[aria-label="确认"]')!.click())
    await flushAsyncWork()
    expect(item.dataset.findingDecision).toBe('confirmed')
    expect(item.querySelector('[aria-label="取消确认"]')).not.toBeNull()
    act(() => item.querySelector<HTMLButtonElement>('[aria-label="标记提醒"]')!.click())
    await flushAsyncWork()
    expect(item.dataset.findingMarked).toBe('true')
    act(() => item.querySelector<HTMLButtonElement>('[aria-label="添加笔记"]')!.click())
    const textarea = item.querySelector<HTMLTextAreaElement>('textarea')!
    act(() => {
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(textarea, 'Review note')
      textarea.dispatchEvent(new Event('input', { bubbles: true }))
    })
    const save = [...item.querySelectorAll<HTMLButtonElement>('button')].find(button => button.textContent === '保存')!
    await act(async () => { save.click(); await Promise.resolve() })
    await flushAsyncWork()

    expect(item.dataset.findingHasNote).toBe('true')
    expect(item.querySelector('[data-finding-note-preview]')?.textContent).toContain('Review note')
    expect(container.querySelector('[data-selected-finding]')?.textContent).toBe('F1')
    expect(container.querySelector('[data-selected-evidence]')?.textContent).toBe('C0011:S001,C0020:S001,C0030:S999')
    expect(container.querySelector('[data-focused-evidence]')?.textContent).toBe(evidenceLocationKey(evidenceB))
    expect(patchFindingReview).toHaveBeenNthCalledWith(1, 'run_1', 'F1', { decision: 'confirmed' })
    expect(patchFindingReview).toHaveBeenNthCalledWith(2, 'run_1', 'F1', { marked: true })
    expect(patchFindingReview).toHaveBeenNthCalledWith(3, 'run_1', 'F1', { note: 'Review note' })
  })

  it('does not change selected finding after confirm decision patch', async () => {
    vi.mocked(patchFindingReview).mockImplementation(async (_flowRunId, findingId, patch) => {
      const decision = patch.decision ?? 'pending'
      return {
        flowRunId: 'run_1',
        entriesByFindingId: new Map([
          [
            findingId,
            {
              findingId,
              decision,
              marked: false,
              updatedAt: '2026-10-05T00:00:00Z',
            },
          ],
        ]),
      }
    })

    act(() => root.render(createElement(ResultShell, {
      flowRunId: 'run_1',
      taskDisplayName: 'Document consistency',
    })))
    await flushAsyncWork()

    selectFinding()

    const card = container.querySelector('[data-finding-review-card="true"]')
    const confirmButton = card?.querySelector('button[aria-label="确认"]')
    act(() => confirmButton?.dispatchEvent(new MouseEvent('click', { bubbles: true })))
    await flushAsyncWork()

    expect(container.querySelector('[data-selected-finding]')?.textContent).toBe('F1')
    expect(patchFindingReview).toHaveBeenCalledWith('run_1', 'F1', { decision: 'confirmed' })
  })

  it('ignores a review PATCH response that completes after the Result flow changes', async () => {
    let resolveOldPatch: ((payload: FindingReviewStatePayload) => void) | undefined
    vi.mocked(patchFindingReview).mockImplementationOnce(
      () => new Promise((resolve) => {
        resolveOldPatch = resolve
      }),
    )

    act(() => root.render(createElement(ResultShell, {
      flowRunId: 'run_1',
      taskDisplayName: 'Document consistency',
    })))
    await flushAsyncWork()

    selectFinding()
    const resolveButton = container.querySelector(
      '[data-finding-review-card="true"] button[aria-label="确认"]',
    )
    act(() => resolveButton?.dispatchEvent(new MouseEvent('click', { bubbles: true })))

    vi.mocked(fetchFindingReviewState).mockResolvedValue({
      flowRunId: 'run_2',
      entriesByFindingId: new Map(),
    })
    act(() => root.render(createElement(ResultShell, {
      flowRunId: 'run_2',
      taskDisplayName: 'Document consistency',
    })))
    await flushAsyncWork()
    expect(container.querySelector('[data-review-flow-run-id]')?.textContent).toBe('run_2')

    await act(async () => {
      resolveOldPatch?.({
        flowRunId: 'run_1',
        entriesByFindingId: new Map(),
      })
      await Promise.resolve()
    })

    expect(container.querySelector('[data-review-flow-run-id]')?.textContent).toBe('run_2')
  })

  it('ignores a source annotation create response that completes after the Result flow changes', async () => {
    let resolveOldCreate:
      | ((annotation: Awaited<ReturnType<typeof createSourceComment>>) => void)
      | undefined
    vi.mocked(createSourceComment).mockImplementationOnce(
      () => new Promise((resolve) => {
        resolveOldCreate = resolve
      }),
    )
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

    act(() => root.render(createElement(ResultShell, {
      flowRunId: 'run_1',
      taskDisplayName: 'Document consistency',
    })))
    await flushAsyncWork()
    selectFinding()

    const sentence = container.querySelector(
      '[data-result-document-pane] [data-sentence-id="C0011:S001"][data-sentence-range-enabled="true"]',
    ) as HTMLElement
    expect(sentence).toBeTruthy()
    const textWalker = document.createTreeWalker(sentence, NodeFilter.SHOW_TEXT)
    let sourceText = textWalker.nextNode() as Text | null
    while (sourceText && sourceText.data.length < 5) {
      sourceText = textWalker.nextNode() as Text | null
    }
    expect(sourceText).not.toBeNull()
    const range = document.createRange()
    range.setStart(sourceText!, 0)
    range.setEnd(sourceText!, 5)
    window.getSelection()?.removeAllRanges()
    window.getSelection()?.addRange(range)
    const interactionRoot = container.querySelector(
      '[data-source-document-interaction="true"]',
    ) as HTMLElement
    expect(extractSourceTextRangeFromSelection(window.getSelection(), {
      containmentRoot: interactionRoot,
    })).toMatchObject({ supported: true })
    act(() => interactionRoot.dispatchEvent(new MouseEvent('mouseup', { bubbles: true })))
    const commentAction = [...container.querySelectorAll('button')]
      .find((button) => button.textContent === '批注')
    expect(commentAction).toBeTruthy()
    act(() => commentAction?.click())

    const input = document.body.querySelector(
      '[data-source-comment-popover="true"] textarea',
    ) as HTMLTextAreaElement
    expect(input).toBeTruthy()
    Object.getOwnPropertyDescriptor(
      HTMLTextAreaElement.prototype,
      'value',
    )?.set?.call(input, 'old-flow comment')
    act(() => input.dispatchEvent(new Event('input', { bubbles: true })))
    const save = [...document.body.querySelectorAll(
      '[data-source-comment-popover="true"] button',
    )].find((button) => button.textContent === '保存')
    act(() => save?.click())
    expect(createSourceComment).toHaveBeenCalledTimes(1)

    vi.mocked(fetchSourceAnnotations).mockResolvedValue({
      flowRunId: 'run_2',
      annotationsById: new Map(),
    })
    vi.mocked(fetchFindingReviewState).mockResolvedValue({
      flowRunId: 'run_2',
      entriesByFindingId: new Map(),
    })
    act(() => root.render(createElement(ResultShell, {
      flowRunId: 'run_2',
      taskDisplayName: 'Document consistency',
    })))
    await flushAsyncWork()

    await act(async () => {
      resolveOldCreate?.({
        annotationId: 'ann-old-flow',
        anchor: {
          slotId: 'source',
          docId: 'doc_test',
          blockId: 'C0011',
          sentenceId: 'C0011:S001',
        },
        kind: 'comment',
        range: { startOffset: 0, endOffset: 5 },
        content: 'old-flow comment',
        createdAt: '2026-01-01T00:00:00Z',
        updatedAt: '2026-01-01T00:00:00Z',
      })
      await Promise.resolve()
    })

    expect(container.querySelector(
      '[data-source-comment-annotation-id="ann-old-flow"]',
    )).toBeNull()
  })
})
