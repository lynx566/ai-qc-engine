// @vitest-environment happy-dom

import { act, createElement, useState } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ResultFindingsPanel } from '@/components/review/result-findings-panel'
import { findingReviewQueueActionUsesSemanticColor } from '@/lib/finding-review-presentation'
import { computeFindingQueueSelectionScrollTop } from '@/lib/finding-queue-selection-scroll'
import type { InternalResultFinding } from '@/types/document-consistency-qc'
import type {
  FindingReviewPatch,
  FindingReviewStatePayload,
} from '@/types/finding-review'

const findings: InternalResultFinding[] = [
  {
    findingId: 'F2',
    label: 'need_review',
    conclusion: 'First task in backend order',
    comparisonModeId: 'scope_local',
    evidenceRefs: [],
  },
  {
    findingId: 'F1',
    label: 'fail',
    conclusion: 'Second task in backend order',
    comparisonModeId: 'scope_local',
    evidenceRefs: [],
  },
]

const documentView = {
  docId: 'doc_test',
  fileName: 'sample.docx',
  displayName: 'sample.docx',
  blocks: [],
}

function applyFindingReviewPatch(
  state: FindingReviewStatePayload | null,
  findingId: string,
  patch: FindingReviewPatch,
): FindingReviewStatePayload {
  const flowRunId = state?.flowRunId ?? 'run_test'
  const entriesByFindingId = new Map(state?.entriesByFindingId ?? [])
  const current = entriesByFindingId.get(findingId) ?? {
    findingId,
    decision: 'pending' as const,
    marked: false,
    updatedAt: '2026-10-05T00:00:00Z',
  }
  const next = { ...current, updatedAt: '2026-10-05T00:00:00Z' }
  if (patch.decision !== undefined) {
    next.decision = patch.decision
  }
  if (patch.marked !== undefined) {
    next.marked = patch.marked
  }
  if (patch.note !== undefined) {
    if (patch.note === '' || patch.note === null) {
      delete next.note
    } else {
      next.note = patch.note
    }
  }
  entriesByFindingId.set(findingId, next)
  return { flowRunId, entriesByFindingId }
}

function QueueHarness({
  onPatchFindingReview,
  savingFindingId = null,
  reviewState = null,
}: {
  onPatchFindingReview: (findingId: string, patch: FindingReviewPatch) => Promise<void>
  savingFindingId?: string | null
  reviewState?: FindingReviewStatePayload | null
}) {
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null)

  return createElement(ResultFindingsPanel, {
    taskDisplayName: 'DSUR',
    documentDisplayName: 'sample.docx',
    flowId: 'document_consistency_qc',
    functionViewQuery: { mode: 'all' },
    availableSemanticModuleIds: ['clinical_safety'],
    onFunctionViewQueryChange: () => {},
    activeOutlineBlockId: 'doc_test:C0030',
    findings,
    reviewState,
    savingFindingId,
    selectedFindingId,
    selectedFinding: findings.find((finding) => finding.findingId === selectedFindingId) ?? null,
    selectedEvidenceLocations: [],
    focusedEvidenceLocationKey: 'preserved-focus',
    focusedEvidenceLocation: null,
    onSelectFinding: setSelectedFindingId,
    onFocusEvidence: () => {},
    onPatchFindingReview,
    document: documentView,
  })
}

function StatefulQueueHarness({
  initialReviewState = null,
}: {
  initialReviewState?: FindingReviewStatePayload | null
}) {
  const [reviewState, setReviewState] = useState<FindingReviewStatePayload | null>(
    initialReviewState,
  )

  return createElement(QueueHarness, {
    reviewState,
    onPatchFindingReview: async (findingId, patch) => {
      setReviewState((current) => applyFindingReviewPatch(current, findingId, patch))
    },
  })
}

function RemountQueueHarness() {
  const [open, setOpen] = useState(true)
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>('F1')

  return createElement(
    'div',
    null,
    createElement('button', {
      type: 'button',
      'data-toggle-queue': 'true',
      onClick: () => setOpen((current) => !current),
    }),
    open ? createElement(ResultFindingsPanel, {
      taskDisplayName: 'DSUR',
      documentDisplayName: 'sample.docx',
      flowId: 'document_consistency_qc',
      functionViewQuery: { mode: 'all' },
      availableSemanticModuleIds: ['clinical_safety'],
      onFunctionViewQueryChange: () => {},
      activeOutlineBlockId: null,
      findings,
      reviewState: null,
      savingFindingId: null,
      selectedFindingId,
      selectedFinding: findings.find((finding) => finding.findingId === selectedFindingId) ?? null,
      selectedEvidenceLocations: [],
      focusedEvidenceLocationKey: null,
      focusedEvidenceLocation: null,
      onSelectFinding: setSelectedFindingId,
      onFocusEvidence: () => {},
      onPatchFindingReview: async () => {},
      document: documentView,
    }) : null,
  )
}

let container: HTMLDivElement
let root: Root
let scrollIntoView: ReturnType<typeof vi.fn>

async function flushSelectionScrollFrames() {
  await act(async () => {
    await new Promise<void>((resolve) => {
      requestAnimationFrame(() => resolve())
    })
  })
}

function getQueueScrollViewport(): HTMLElement {
  const scrollRoot = container.querySelector('[data-result-findings-scroll="true"]')
  if (scrollRoot === null) {
    throw new Error('Expected Result findings scroll root')
  }
  const viewport = scrollRoot.querySelector('[data-slot="scroll-area-viewport"]')
  if (viewport === null) {
    throw new Error('Expected Finding Queue scroll viewport')
  }
  return viewport as HTMLElement
}

function stubQueueViewportForScroll(
  viewport: HTMLElement,
  {
    clientHeight,
    scrollHeight,
    scrollTop = 0,
    viewportTop = 40,
  }: {
    clientHeight: number
    scrollHeight: number
    scrollTop?: number
    viewportTop?: number
  },
) {
  const scrollTo = vi.fn((options?: ScrollToOptions) => {
    if (options?.top !== undefined) {
      viewport.scrollTop = options.top
    }
  })
  viewport.scrollTo = scrollTo as typeof viewport.scrollTo
  Object.defineProperty(viewport, 'clientHeight', { configurable: true, value: clientHeight })
  Object.defineProperty(viewport, 'scrollHeight', { configurable: true, value: scrollHeight })
  Object.defineProperty(viewport, 'scrollTop', {
    configurable: true,
    writable: true,
    value: scrollTop,
  })

  viewport.getBoundingClientRect = () => ({
    top: viewportTop,
    left: 0,
    right: 280,
    bottom: viewportTop + clientHeight,
    width: 280,
    height: clientHeight,
    x: 0,
    y: viewportTop,
    toJSON: () => ({}),
  })

  const setItemTopInContent = (item: HTMLElement, topInContent: number) => {
    item.getBoundingClientRect = () => {
      const top = topInContent - viewport.scrollTop + viewportTop
      return {
        top,
        left: 0,
        right: 280,
        bottom: top + 80,
        width: 280,
        height: 80,
        x: 0,
        y: top,
        toJSON: () => ({}),
      }
    }
  }

  return { scrollTo, setItemTopInContent }
}

beforeEach(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  scrollIntoView = vi.fn()
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
    configurable: true,
    value: scrollIntoView,
  })
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe('Finding Queue scroll layout', () => {
  it('keeps function context in the same scroll viewport as the queue without a panel title', () => {
    act(() => root.render(createElement(QueueHarness, {
      onPatchFindingReview: async () => {},
    })))

    const viewport = getQueueScrollViewport()
    expect(viewport.querySelector('[data-result-panel-title="true"]')).toBeNull()
    expect(viewport.querySelector('[data-result-function-context]')).not.toBeNull()
    expect(viewport.querySelector('[data-finding-queue="true"]')).not.toBeNull()
    expect(viewport.querySelector('[data-result-pane-header]')).not.toBeNull()
    expect(container.querySelector('[data-result-findings-scroll="true"]')).not.toBeNull()
  })

  it('constrains the Result scroll content chain to the pane width', () => {
    act(() => root.render(createElement(QueueHarness, {
      onPatchFindingReview: async () => {},
    })))

    const scrollArea = container.querySelector('[data-result-findings-scroll="true"]')!
    const panelRoot = scrollArea.parentElement!
    const viewport = getQueueScrollViewport()
    const queue = viewport.querySelector('[data-finding-queue="true"]')!

    expect(panelRoot.className).toContain('w-full')
    expect(panelRoot.className).toContain('min-w-0')
    expect(panelRoot.className).toContain('max-w-full')
    expect(scrollArea.className).toContain('w-full')
    expect(scrollArea.className).toContain('min-w-0')
    expect(viewport.className).toContain('[&>div]:!block')
    expect(viewport.className).toContain('[&>div]:!w-full')
    expect(viewport.className).toContain('[&>div]:!min-w-0')
    expect(viewport.className).toContain('[&>div]:!max-w-full')
    expect(queue.className).toContain('w-full')
    expect(queue.className).toContain('min-w-0')
    expect(queue.className).toContain('max-w-full')
  })
})

describe('Finding Queue interactions', () => {
  it('selects a finding when the conclusion or card body blank area is clicked', () => {
    act(() => root.render(createElement(QueueHarness, {
      onPatchFindingReview: async () => {},
    })))

    const first = container.querySelector('[data-finding-queue-item="F1"]')!
    const conclusion = first.querySelector('[data-finding-verdict-title="true"]')!
    const footer = first.querySelector('[data-finding-queue-tier="footer"]')!

    act(() => conclusion.dispatchEvent(new MouseEvent('click', { bubbles: true })))
    expect(first.getAttribute('data-finding-selected')).toBe('true')

    const second = container.querySelector('[data-finding-queue-item="F2"]')!
    act(() => second.querySelector('[data-finding-queue-select="true"]')?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    ))
    expect(first.getAttribute('data-finding-selected')).toBe('false')
    expect(second.getAttribute('data-finding-selected')).toBe('true')

    act(() => footer.dispatchEvent(new MouseEvent('click', { bubbles: true })))
    expect(first.getAttribute('data-finding-selected')).toBe('true')
    expect(second.getAttribute('data-finding-selected')).toBe('false')
    expect(first.querySelector('[data-finding-queue-select="true"]')).not.toBeNull()
    expect(first.className).not.toMatch(/\bmin-h-/)
  })

  it('changes selected-row presentation only when a Finding selection surface is clicked', () => {
    act(() => root.render(createElement(QueueHarness, {
      onPatchFindingReview: async () => {},
    })))

    const first = container.querySelector('[data-finding-queue-item="F1"]')!
    const second = container.querySelector('[data-finding-queue-item="F2"]')!

    expect(first.getAttribute('data-finding-selected')).toBe('false')
    expect(second.getAttribute('data-finding-selected')).toBe('false')

    act(() => first.querySelector('[data-finding-queue-select="true"]')?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    ))
    expect(first.getAttribute('data-finding-selected')).toBe('true')

    act(() => second.querySelector('[data-finding-queue-select="true"]')?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    ))
    expect(first.getAttribute('data-finding-selected')).toBe('false')
    expect(second.getAttribute('data-finding-selected')).toBe('true')
    expect(scrollIntoView).not.toHaveBeenCalled()
  })

  it('scrolls an already-selected row into view when the Queue is remounted', async () => {
    act(() => root.render(createElement(RemountQueueHarness)))

    const f1 = () => container.querySelector('[data-finding-queue-item="F1"]')!
    const f2 = () => container.querySelector('[data-finding-queue-item="F2"]')!
    const stubAndAnchorF1 = () => {
      const { scrollTo, setItemTopInContent } = stubQueueViewportForScroll(getQueueScrollViewport(), {
        clientHeight: 300,
        scrollHeight: 900,
      })
      setItemTopInContent(f1(), 260)
      act(() => f2().querySelector('[data-finding-queue-select="true"]')?.dispatchEvent(
        new MouseEvent('click', { bubbles: true }),
      ))
      scrollTo.mockClear()
      act(() => f1().querySelector('[data-finding-queue-select="true"]')?.dispatchEvent(
        new MouseEvent('click', { bubbles: true }),
      ))
      return scrollTo
    }

    let scrollTo = stubAndAnchorF1()
    await flushSelectionScrollFrames()

    expect(scrollIntoView).not.toHaveBeenCalled()
    expect(scrollTo).toHaveBeenCalledTimes(1)
    expect(scrollTo).toHaveBeenCalledWith({ top: 195, behavior: 'smooth' })

    const toggle = container.querySelector<HTMLButtonElement>('[data-toggle-queue="true"]')!
    act(() => toggle.click())
    act(() => toggle.click())
    scrollTo = stubAndAnchorF1()
    await flushSelectionScrollFrames()

    expect(scrollTo).toHaveBeenCalledTimes(1)
    expect(scrollTo).toHaveBeenCalledWith({ top: 195, behavior: 'smooth' })
  })

  it('anchors the selected finding center to the review anchor axis in the queue viewport', async () => {
    act(() => root.render(createElement(QueueHarness, {
      onPatchFindingReview: async () => {},
    })))

    const viewport = getQueueScrollViewport()
    const { scrollTo, setItemTopInContent } = stubQueueViewportForScroll(viewport, {
      clientHeight: 300,
      scrollHeight: 1200,
    })
    const f1 = container.querySelector('[data-finding-queue-item="F1"]')!
    setItemTopInContent(f1, 450)

    act(() => f1.querySelector('[data-finding-queue-select="true"]')?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    ))
    await flushSelectionScrollFrames()

    expect(scrollIntoView).not.toHaveBeenCalled()
    expect(scrollTo).toHaveBeenCalledTimes(1)
    expect(scrollTo).toHaveBeenCalledWith({ top: 385, behavior: 'smooth' })
    expect(
      computeFindingQueueSelectionScrollTop(300, 1200, 450, 80),
    ).toBe(385)
  })

  it('clamps queue selection anchoring at the top and bottom of the scroll range', async () => {
    act(() => root.render(createElement(QueueHarness, {
      onPatchFindingReview: async () => {},
    })))

    const viewport = getQueueScrollViewport()
    const { scrollTo, setItemTopInContent } = stubQueueViewportForScroll(viewport, {
      clientHeight: 300,
      scrollHeight: 1000,
    })
    const f2 = container.querySelector('[data-finding-queue-item="F2"]')!
    setItemTopInContent(f2, 60)

    act(() => f2.querySelector('[data-finding-queue-select="true"]')?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    ))
    await flushSelectionScrollFrames()
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 0, behavior: 'smooth' })

    scrollTo.mockClear()
    const f1 = container.querySelector('[data-finding-queue-item="F1"]')!
    setItemTopInContent(f1, 950)
    act(() => f1.querySelector('[data-finding-queue-select="true"]')?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    ))
    await flushSelectionScrollFrames()
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 700, behavior: 'smooth' })
  })

  it('does not re-anchor when review state changes without a selection change', async () => {
    act(() => root.render(createElement(StatefulQueueHarness)))

    const viewport = getQueueScrollViewport()
    const { scrollTo, setItemTopInContent } = stubQueueViewportForScroll(viewport, {
      clientHeight: 300,
      scrollHeight: 1200,
    })
    const f1 = container.querySelector('[data-finding-queue-item="F1"]')!
    setItemTopInContent(f1, 420)

    act(() => f1.querySelector('[data-finding-queue-select="true"]')?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    ))
    await flushSelectionScrollFrames()
    expect(scrollTo).toHaveBeenCalledTimes(1)

    scrollTo.mockClear()
    act(() => f1.querySelector('button[aria-label="确认"]')?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    ))
    act(() => f1.querySelector('button[aria-label="标记提醒"]')?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    ))
    act(() => f1.querySelector('button[aria-label="添加笔记"]')?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    ))
    await flushSelectionScrollFrames()

    expect(scrollTo).not.toHaveBeenCalled()
    expect(scrollIntoView).not.toHaveBeenCalled()
  })

  it('renders inset left-edge severity strokes for pending findings by label', () => {
    act(() => root.render(createElement(QueueHarness, {
      onPatchFindingReview: async () => {},
    })))

    const f1 = container.querySelector('[data-finding-queue-item="F1"]')!
    const f2 = container.querySelector('[data-finding-queue-item="F2"]')!
    const f1Edge = f1.querySelector('[data-finding-queue-left-edge-indicator]')!
    const f2Edge = f2.querySelector('[data-finding-queue-left-edge-indicator]')!

    expect(f1.getAttribute('data-finding-queue-left-edge')).toBe('fail')
    expect(f1.className).not.toContain('border-l-red-500')
    expect(f1Edge.className).toContain('bg-red-500')
    expect(f1Edge.className).toContain('top-[8px]')
    expect(f1Edge.getAttribute('style')).toContain('clip-path')
    expect(f1Edge.getAttribute('style')).toContain('drop-shadow')
    expect(f2.getAttribute('data-finding-queue-left-edge')).toBe('need_review')
    expect(f2Edge.className).toContain('bg-amber-400')
  })

  it('applies CJK-friendly justify typography to queue conclusions without clamping text', () => {
    act(() => root.render(createElement(QueueHarness, {
      onPatchFindingReview: async () => {},
    })))

    const conclusion = container.querySelector(
      '[data-finding-queue-item="F1"] [data-finding-verdict-title="true"]',
    )!
    expect(conclusion.className).toContain('text-[15px]')
    expect(conclusion.className).toContain('leading-[1.55]')
    expect(conclusion.className).toContain('text-justify')
    expect(conclusion.className).toContain('[text-justify:inter-character]')
    expect(conclusion.className).toContain('break-normal')
    expect(conclusion.className).not.toContain('text-last-justify')
    expect(conclusion.className).not.toContain('break-all')
    expect(conclusion.className).not.toContain('line-clamp')
    expect(conclusion.textContent).toContain('Second task in backend order')
  })

  it('places review actions in a footer row below the conclusion', () => {
    act(() => root.render(createElement(QueueHarness, {
      onPatchFindingReview: async () => {},
    })))

    const item = container.querySelector('[data-finding-queue-item="F1"]')!
    const primary = item.querySelector('[data-finding-queue-tier="primary"]')!
    const footer = item.querySelector('[data-finding-queue-tier="footer"]')!
    const actions = footer.querySelector('[data-finding-review-actions="true"]')!

    expect(primary.compareDocumentPosition(footer) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(primary.contains(actions)).toBe(false)
    expect(primary.textContent).toContain('Second task in backend order')
    expect(primary.textContent).not.toContain('处原文')
    expect(footer.querySelector('[data-finding-queue-evidence="true"]')).toBeNull()
    expect(footer.textContent).not.toContain('处原文')
    expect(actions.querySelector('button[aria-label="确认"]')?.querySelector('.lucide-check')).not.toBeNull()
    expect(actions.querySelector('.lucide-circle-check-big')).toBeNull()
    expect(actions.querySelector('button[aria-label="忽略"]')).not.toBeNull()
    expect(actions.querySelector('.lucide-eye-closed')).not.toBeNull()
    expect(actions.querySelector('.lucide-eye-off')).toBeNull()
    expect(actions.querySelector('.lucide-circle-off')).toBeNull()
    expect(actions.querySelector('button[aria-label="标记提醒"]')).not.toBeNull()
    expect(actions.querySelector('button[aria-label="添加笔记"]')).not.toBeNull()
  })

  it('keeps review controls outside selection and sends the existing review patches', async () => {
    const onPatchFindingReview = vi.fn(async () => {})
    act(() => root.render(createElement(QueueHarness, { onPatchFindingReview })))

    const first = container.querySelector('[data-finding-queue-item="F1"]')!
    const confirm = first.querySelector('button[aria-label="确认"]')
    const mark = first.querySelector('button[aria-label="标记提醒"]')
    const note = first.querySelector('button[aria-label="添加笔记"]')

    act(() => confirm?.dispatchEvent(new MouseEvent('click', { bubbles: true })))
    act(() => mark?.dispatchEvent(new MouseEvent('click', { bubbles: true })))
    act(() => note?.dispatchEvent(new MouseEvent('click', { bubbles: true })))

    expect(first.getAttribute('data-finding-selected')).toBe('false')
    expect(onPatchFindingReview).toHaveBeenNthCalledWith(1, 'F1', { decision: 'confirmed' })
    expect(onPatchFindingReview).toHaveBeenNthCalledWith(2, 'F1', { marked: true })
    expect(container.querySelector('[data-finding-note-editor="true"]')).not.toBeNull()

    const textarea = container.querySelector('textarea')!
    act(() => {
      Object.getOwnPropertyDescriptor(
        HTMLTextAreaElement.prototype,
        'value',
      )?.set?.call(textarea, '  compact note  ')
      textarea.dispatchEvent(new Event('input', { bubbles: true }))
    })
    const save = [...container.querySelectorAll('button')].find(
      (button) => button.textContent === '保存',
    )
    await act(async () => {
      save?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      await Promise.resolve()
    })

    expect(onPatchFindingReview).toHaveBeenNthCalledWith(3, 'F1', {
      note: 'compact note',
    })
    expect(first.getAttribute('data-finding-selected')).toBe('false')
  })

  it('does not render an inline note preview when the finding has no note', () => {
    act(() => root.render(createElement(QueueHarness, {
      onPatchFindingReview: async () => {},
    })))

    const item = container.querySelector('[data-finding-queue-item="F1"]')!
    expect(item.querySelector('[data-finding-note-preview="true"]')).toBeNull()
    expect(item.querySelector(
      '[data-finding-review-actions="true"] button[aria-label="添加笔记"]',
    )?.getAttribute('aria-pressed')).toBe('false')
  })

  it('renders read-only inline note preview and opens the editor only from the note action', () => {
    act(() => root.render(createElement(QueueHarness, {
      onPatchFindingReview: async () => {},
      reviewState: {
        flowRunId: 'run_test',
        entriesByFindingId: new Map([
          [
            'F1',
            {
              findingId: 'F1',
              decision: 'pending',
              marked: false,
              note: '已与统计表核对，需要进一步确认原始数据。',
              updatedAt: '2026-10-05T00:00:00Z',
            },
          ],
        ]),
      },
    })))

    const item = container.querySelector('[data-finding-queue-item="F1"]')!
    const primary = item.querySelector('[data-finding-queue-tier="primary"]')!
    const preview = item.querySelector('[data-finding-queue-tier="note"]')!
    const footer = item.querySelector('[data-finding-queue-tier="footer"]')!

    expect(preview.textContent).toContain('已与统计表核对')
    const noteLabel = preview.querySelector('[data-finding-note-preview-label="true"]')!
    const noteContent = preview.querySelector('[data-finding-note-preview-content="true"]')!
    expect(noteLabel.textContent).toBe('笔记')
    expect(noteLabel.className).toContain('text-xs')
    expect(noteContent.className).toContain('text-xs')
    expect(preview.querySelector('[data-finding-note-preview-content="true"]')?.textContent)
      .toContain('已与统计表核对')
    expect(preview.querySelector('svg')).toBeNull()
    expect([...preview.children].map((node) => node.getAttribute('data-finding-note-preview-label')
      ?? node.getAttribute('data-finding-note-preview-content'))).toEqual(['true', 'true'])
    expect(primary.compareDocumentPosition(preview) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(preview.compareDocumentPosition(footer) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    const noteAction = item.querySelector(
      '[data-finding-review-actions="true"] button[aria-label="编辑笔记"]',
    )!
    expect(noteAction.getAttribute('aria-pressed')).toBe('true')

    act(() => noteContent.dispatchEvent(new MouseEvent('click', { bubbles: true })))
    expect(item.querySelector('[data-finding-note-editor="true"]')).toBeNull()
    expect(item.querySelector('[data-finding-note-preview="true"]')).not.toBeNull()
    expect(item.getAttribute('data-finding-selected')).toBe('true')

    act(() => noteAction.dispatchEvent(new MouseEvent('click', { bubbles: true })))
    expect(item.querySelector('[data-finding-note-editor="true"]')).not.toBeNull()
    expect(item.querySelector('[data-finding-note-preview="true"]')).toBeNull()
    expect(item.querySelector('[data-finding-queue-item-footer="true"]')).toBeNull()
    expect(item.getAttribute('data-finding-selected')).toBe('true')
  })

  it('hides the queue footer while the note editor is open', async () => {
    act(() => root.render(createElement(StatefulQueueHarness)))

    const item = container.querySelector('[data-finding-queue-item="F1"]')!
    const footer = () => item.querySelector('[data-finding-queue-item-footer="true"]')

    expect(footer()).not.toBeNull()
    expect(footer()?.querySelector('[data-finding-queue-evidence="true"]')).toBeNull()
    expect(footer()?.querySelector('[data-finding-review-actions="true"]')).not.toBeNull()

    act(() => item.querySelector('button[aria-label="添加笔记"]')?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    ))
    expect(footer()).toBeNull()
    expect(item.querySelector('[data-finding-note-editor="true"]')).not.toBeNull()

    const cancel = [...container.querySelectorAll('button')].find(
      (button) => button.textContent === '取消',
    )
    act(() => cancel?.dispatchEvent(new MouseEvent('click', { bubbles: true })))
    expect(footer()).not.toBeNull()
    expect(item.querySelector('[data-finding-note-editor="true"]')).toBeNull()

    act(() => item.querySelector('button[aria-label="添加笔记"]')?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    ))
    expect(footer()).toBeNull()

    const textarea = container.querySelector('textarea')!
    act(() => {
      Object.getOwnPropertyDescriptor(
        HTMLTextAreaElement.prototype,
        'value',
      )?.set?.call(textarea, 'saved after footer returns')
      textarea.dispatchEvent(new Event('input', { bubbles: true }))
    })
    const save = [...container.querySelectorAll('button')].find(
      (button) => button.textContent === '保存',
    )
    await act(async () => {
      save?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      await Promise.resolve()
    })
    expect(footer()).not.toBeNull()
    expect(item.querySelector('[data-finding-note-preview="true"]')?.textContent)
      .toContain('saved after footer returns')

    act(() => item.querySelector('button[aria-label="编辑笔记"]')?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    ))
    expect(footer()).toBeNull()
    const remove = [...container.querySelectorAll('button')].find(
      (button) => button.textContent === '删除',
    )
    await act(async () => {
      remove?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      await Promise.resolve()
    })
    expect(footer()).not.toBeNull()
    expect(item.querySelector('[data-finding-note-preview="true"]')).toBeNull()
  })

  it('clamps long inline note previews to three lines', () => {
    const longNote = Array.from({ length: 12 }, (_, index) => `段落${index + 1}`).join('，')

    act(() => root.render(createElement(QueueHarness, {
      onPatchFindingReview: async () => {},
      reviewState: {
        flowRunId: 'run_test',
        entriesByFindingId: new Map([
          [
            'F1',
            {
              findingId: 'F1',
              decision: 'pending',
              marked: false,
              note: longNote,
              updatedAt: '2026-10-05T00:00:00Z',
            },
          ],
        ]),
      },
    })))

    const previewText = container.querySelector(
      '[data-finding-queue-item="F1"] [data-finding-note-preview-content="true"]',
    )!
    expect(previewText.getAttribute('data-finding-note-preview-lines')).toBe('3')
    expect(previewText.textContent).toBe(longNote)
  })

  it('syncs inline preview and note action state after save and clear', async () => {
    act(() => root.render(createElement(StatefulQueueHarness)))

    const item = container.querySelector('[data-finding-queue-item="F1"]')!
    act(() => item.querySelector('button[aria-label="添加笔记"]')?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    ))

    const textarea = container.querySelector('textarea')!
    act(() => {
      Object.getOwnPropertyDescriptor(
        HTMLTextAreaElement.prototype,
        'value',
      )?.set?.call(textarea, 'queue inline note')
      textarea.dispatchEvent(new Event('input', { bubbles: true }))
    })
    const save = [...container.querySelectorAll('button')].find(
      (button) => button.textContent === '保存',
    )
    await act(async () => {
      save?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      await Promise.resolve()
    })

    expect(item.querySelector('[data-finding-note-preview="true"]')?.textContent)
      .toContain('queue inline note')
    expect(item.querySelector(
      '[data-finding-review-actions="true"] button[aria-label="编辑笔记"]',
    )?.getAttribute('aria-pressed')).toBe('true')

    act(() => item.querySelector(
      '[data-finding-review-actions="true"] button[aria-label="编辑笔记"]',
    )?.dispatchEvent(new MouseEvent('click', { bubbles: true })))
    const remove = [...container.querySelectorAll('button')].find(
      (button) => button.textContent === '删除',
    )
    await act(async () => {
      remove?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      await Promise.resolve()
    })

    expect(item.querySelector('[data-finding-note-preview="true"]')).toBeNull()
    expect(item.querySelector('button[aria-label="添加笔记"]')).not.toBeNull()
  })

  it('disables every review control while any review mutation is pending', () => {
    act(() => root.render(createElement(QueueHarness, {
      onPatchFindingReview: async () => {},
      savingFindingId: 'F1',
    })))

    const secondRowActions = container.querySelector(
      '[data-finding-queue-item="F2"] [data-finding-review-actions="true"]',
    )!
    expect([...secondRowActions.querySelectorAll('button')].every(
      (button) => button.disabled,
    )).toBe(true)
  })

  it('updates left edge on confirm, ignore, and un-confirm without muting verdict', async () => {
    act(() => root.render(createElement(StatefulQueueHarness)))

    const f1 = container.querySelector('[data-finding-queue-item="F1"]')!
    expect(f1.getAttribute('data-finding-queue-left-edge')).toBe('fail')

    act(() => f1.querySelector('button[aria-label="确认"]')?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    ))
    await act(async () => {
      await Promise.resolve()
    })
    expect(f1.getAttribute('data-finding-queue-left-edge')).toBe('confirmed')
    expect(f1.querySelector('[data-finding-queue-left-edge-indicator]')?.className)
      .toContain('bg-slate-400')
    expect(f1.querySelector('[data-finding-verdict="fail"]')).toBeNull()

    act(() => f1.querySelector('button[aria-label="取消确认"]')?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    ))
    await act(async () => {
      await Promise.resolve()
    })
    expect(f1.getAttribute('data-finding-queue-left-edge')).toBe('fail')
    expect(f1.querySelector('[data-finding-queue-left-edge-indicator]')?.className)
      .toContain('bg-red-500')

    act(() => f1.querySelector('button[aria-label="确认"]')?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    ))
    await act(async () => {
      await Promise.resolve()
    })
    act(() => f1.querySelector('button[aria-label="忽略"]')?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    ))
    await act(async () => {
      await Promise.resolve()
    })
    expect(f1.getAttribute('data-finding-queue-left-edge')).toBe('none')
    expect(f1.querySelector('[data-finding-queue-left-edge-indicator]')).toBeNull()
  })

  it('does not render top-right auxiliary status dots', () => {
    act(() => root.render(createElement(QueueHarness, {
      onPatchFindingReview: async () => {},
      reviewState: {
        flowRunId: 'run_test',
        entriesByFindingId: new Map([
          [
            'F1',
            {
              findingId: 'F1',
              decision: 'confirmed',
              marked: true,
              note: 'flagged with note',
              updatedAt: '2026-10-05T00:00:00Z',
            },
          ],
        ]),
      },
    })))

    const item = container.querySelector('[data-finding-queue-item="F1"]')!
    expect(item.querySelector('[data-finding-queue-aux-dots="true"]')).toBeNull()
    expect(item.querySelector('[data-finding-queue-aux-dot]')).toBeNull()
  })

  it('shows yellow flag glyph and blue pencil glyph for flagged findings with notes', () => {
    act(() => root.render(createElement(QueueHarness, {
      onPatchFindingReview: async () => {},
      reviewState: {
        flowRunId: 'run_test',
        entriesByFindingId: new Map([
          [
            'F1',
            {
              findingId: 'F1',
              decision: 'confirmed',
              marked: true,
              note: 'flagged with note',
              updatedAt: '2026-10-05T00:00:00Z',
            },
          ],
        ]),
      },
    })))

    const item = container.querySelector('[data-finding-queue-item="F1"]')!
    const flagButton = item.querySelector(
      '[data-finding-review-actions="true"] button[aria-label="取消标记"]',
    )!
    const noteButton = item.querySelector(
      '[data-finding-review-actions="true"] button[aria-label="编辑笔记"]',
    )!
    const flagGlyph = item.querySelector('[data-finding-queue-flag-glyph="marked"]')!
    const noteGlyph = item.querySelector('[data-finding-queue-note-glyph="has-note"]')!

    expect(flagButton.getAttribute('data-finding-review-action-glyph-tone')).toBe('flagged')
    expect(noteButton.getAttribute('data-finding-review-action-glyph-tone')).toBe('note')
    expect(flagButton.className).toContain('text-amber-500')
    expect(flagButton.className).not.toContain('bg-amber')
    expect(noteButton.className).toContain('text-sky-500')
    expect(noteButton.className).not.toContain('bg-sky')
    expect(flagGlyph.className).toContain('fill-current')
    expect(noteGlyph.className).toContain('fill-current')
    expect(item.querySelector('[data-finding-note-preview="true"]')?.textContent)
      .toContain('flagged with note')
  })

  it('keeps unflagged flag and noteless pencil glyphs neutral', () => {
    act(() => root.render(createElement(QueueHarness, {
      onPatchFindingReview: async () => {},
    })))

    const item = container.querySelector('[data-finding-queue-item="F1"]')!
    const flagButton = item.querySelector('button[aria-label="标记提醒"]')!
    const noteButton = item.querySelector('button[aria-label="添加笔记"]')!

    expect(flagButton.getAttribute('data-finding-review-action-glyph-tone')).toBe('neutral')
    expect(noteButton.getAttribute('data-finding-review-action-glyph-tone')).toBe('neutral')
    expect(flagButton.className).toContain('text-slate-500')
    expect(noteButton.className).toContain('text-slate-500')
    expect(item.querySelector('[data-finding-queue-flag-glyph="neutral"]')).not.toBeNull()
    expect(item.querySelector('[data-finding-queue-note-glyph="neutral"]')).not.toBeNull()
  })

  it('preserves flagged and note glyph colors on button hover classes', () => {
    act(() => root.render(createElement(QueueHarness, {
      onPatchFindingReview: async () => {},
      reviewState: {
        flowRunId: 'run_test',
        entriesByFindingId: new Map([
          [
            'F1',
            {
              findingId: 'F1',
              decision: 'pending',
              marked: true,
              note: 'hover colors',
              updatedAt: '2026-10-05T00:00:00Z',
            },
          ],
        ]),
      },
    })))

    const item = container.querySelector('[data-finding-queue-item="F1"]')!
    const flagButton = item.querySelector(
      '[data-finding-review-actions="true"] button[aria-label="取消标记"]',
    )!
    const noteButton = item.querySelector(
      '[data-finding-review-actions="true"] button[aria-label="编辑笔记"]',
    )!

    expect(flagButton.className).toContain('hover:text-amber-600')
    expect(flagButton.className).not.toContain('hover:text-slate-700')
    expect(noteButton.className).toContain('hover:text-sky-600')
    expect(noteButton.className).not.toContain('hover:text-slate-700')
  })

  it('applies ignored presentation without strikethrough on conclusion', () => {
    act(() => root.render(createElement(QueueHarness, {
      onPatchFindingReview: async () => {},
      reviewState: {
        flowRunId: 'run_test',
        entriesByFindingId: new Map([
          [
            'F1',
            {
              findingId: 'F1',
              decision: 'ignored',
              marked: false,
              updatedAt: '2026-10-05T00:00:00Z',
            },
          ],
        ]),
      },
    })))

    const item = container.querySelector('[data-finding-queue-item="F1"]')!
    expect(item.getAttribute('data-finding-queue-card-treatment')).toBe('default')
    expect(item.querySelector('[data-finding-verdict="fail"]')).toBeNull()
    expect(item.innerHTML).not.toContain('line-through')
    expect(item.getAttribute('data-finding-queue-left-edge')).toBe('none')
    expect(item.querySelector('[data-finding-queue-left-edge-indicator]')).toBeNull()
    const ignoreAction = item.querySelector(
      '[data-finding-review-actions="true"] button[aria-label="取消忽略"]',
    )
    expect(ignoreAction?.getAttribute('data-finding-review-action-pressed')).toBe('true')
    expect(findingReviewQueueActionUsesSemanticColor(ignoreAction?.className ?? '')).toBe(false)
  })

  it('keeps confirm and ignore actions neutral after review toggles', () => {
    act(() => root.render(createElement(StatefulQueueHarness)))

    const f1 = container.querySelector('[data-finding-queue-item="F1"]')!
    const actions = () => [...f1.querySelectorAll('[data-finding-review-actions="true"] button')]
    const decisionActions = () => actions().slice(0, 2)

    for (const action of decisionActions()) {
      expect(action.getAttribute('data-finding-review-action-glyph-tone')).toBe('neutral')
      expect(findingReviewQueueActionUsesSemanticColor(action.className)).toBe(false)
      expect(action.className).toContain('bg-transparent')
      expect(action.className).toContain('hover:bg-slate-200')
      expect(action.className).not.toContain('border-slate-200')
    }

    act(() => actions()[0]?.dispatchEvent(new MouseEvent('click', { bubbles: true })))
    act(() => actions()[2]?.dispatchEvent(new MouseEvent('click', { bubbles: true })))

    for (const action of decisionActions()) {
      expect(findingReviewQueueActionUsesSemanticColor(action.className)).toBe(false)
      expect(action.className).toContain('bg-transparent')
      expect(action.className).toContain('hover:bg-slate-200')
      expect(action.className).not.toContain('border-slate-200')
    }
    expect(actions()[2]?.getAttribute('data-finding-review-action-glyph-tone')).toBe('flagged')
    expect(actions()[2]?.className).toContain('text-amber-500')
  })

  it('keeps selected card treatment when decision is confirmed or ignored', async () => {
    act(() => root.render(createElement(StatefulQueueHarness)))

    const queueItemIds = () =>
      [...container.querySelectorAll('[data-finding-queue-item]')].map(
        (node) => node.getAttribute('data-finding-queue-item'),
      )

    const f1 = container.querySelector('[data-finding-queue-item="F1"]')!
    act(() => f1.querySelector('[data-finding-queue-select="true"]')?.dispatchEvent(
      new MouseEvent('click', { bubbles: true }),
    ))
    expect(f1.getAttribute('data-finding-selected')).toBe('true')

    const actions = () =>
      f1.querySelector('[data-finding-review-actions="true"]')!
    const actionButtons = () => [...actions().querySelectorAll('button')]

    act(() => actionButtons()[0]?.dispatchEvent(new MouseEvent('click', { bubbles: true })))
    await act(async () => {
      await Promise.resolve()
    })
    expect(f1.getAttribute('data-finding-selected')).toBe('true')
    expect(f1.getAttribute('data-finding-decision')).toBe('confirmed')
    expect(f1.getAttribute('data-finding-queue-left-edge')).toBe('confirmed')
    expect(queueItemIds()).toEqual(['F1', 'F2'])

    act(() => actionButtons()[1]?.dispatchEvent(new MouseEvent('click', { bubbles: true })))
    await act(async () => {
      await Promise.resolve()
    })
    expect(f1.getAttribute('data-finding-selected')).toBe('true')
    expect(f1.getAttribute('data-finding-decision')).toBe('ignored')
    expect(f1.getAttribute('data-finding-queue-left-edge')).toBe('none')
    expect(container.querySelector('[data-finding-queue-item="F2"]')
      ?.getAttribute('data-finding-selected')).toBe('false')

    act(() => actionButtons()[0]?.dispatchEvent(new MouseEvent('click', { bubbles: true })))
    await act(async () => {
      await Promise.resolve()
    })
    expect(f1.getAttribute('data-finding-selected')).toBe('true')
    expect(f1.getAttribute('data-finding-queue-card-treatment')).toBe('selected')
    expect(f1.getAttribute('data-finding-decision')).toBe('confirmed')
    expect(f1.className).toContain('bg-[#F2F6FA]')
    expect(f1.className).not.toContain('border-[#2b5ae8]')
    expect(f1.className).not.toContain('bg-[#E3EEF7]')
    expect(f1.getAttribute('data-finding-queue-left-edge')).toBe('confirmed')
    expect(f1.querySelector('[data-finding-queue-left-edge-indicator]')?.className)
      .toContain('bg-slate-400')
  })
})
