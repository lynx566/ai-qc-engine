// @vitest-environment happy-dom

import { act, createElement, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as queueNavigation from '@/lib/finding-queue-selection-navigation'
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


const secondFinding = { ...finding, findingId: 'F2', evidenceRefs: [evidence(2)] }
let frames: Map<number, FrameRequestCallback>
let serial = 0
let session: { host: HTMLDivElement; root: ReturnType<typeof createRoot> }
let sourceTop = 150
let stackHeight = 200
let itemTops: Record<string, number>
const observers: Array<{ nodes: Set<Element>; callback: ResizeObserverCallback }> = []
function tick(count = 1) {
  act(() => { for (let i = 0; i < count; i++) { const pending = [...frames.values()]; frames.clear(); pending.forEach(cb => cb(0)) } })
}
function queueViewport() { return session.host.querySelector<HTMLElement>('[data-result-findings-scroll] [data-slot="scroll-area-viewport"]')! }
function sourceViewport() { return session.host.querySelector<HTMLElement>('[data-overview-source-placement-viewport]')! }
function placement() { return session.host.querySelector<HTMLElement>('[data-result-review-source-placement]')! }
function Harness({ note, identity = 'run-1', documentId = 'doc-a' }: { note?: string; identity?: string; documentId?: string }) {
  const [id, setId] = useState('F1')
  const findings = [finding, secondFinding].map(item => ({
    ...item, evidenceRefs: item.evidenceRefs.map(location => ({ ...location, docId: documentId })),
  }))
  const selected = findings.find(item => item.findingId === id)!
  return createElement(ResultShellLoaded, shellProps({
    result: { ...result, flowRunId: identity, findings,
      scopeResults: result.scopeResults.map(scope => ({ ...scope, docId: documentId })),
    },
    document: { ...documentView, docId: documentId,
      blocks: documentView.blocks.map(block => ({ ...block, blockId: documentId + ':' + block.sourceBlockId })),
    },
    selectedFindingId: id, selectedFinding: selected,
    selectedEvidenceLocations: selected.evidenceRefs, onSelectFinding: setId,
    reviewState: note ? { flowRunId: identity, entriesByFindingId: new Map([['F1', { findingId: 'F1', decision: 'pending', marked: false, note, updatedAt: '2026-10-08T00:00:00Z' }]]) } : null,
  }))
}
function select(id: string) {
  act(() => session.host.querySelector<HTMLButtonElement>('[data-finding-queue-item="'+id+'"] [data-finding-queue-select]')!.click())
}
function resizeNode(node: Element) {
  act(() => { for (const observer of observers) if (observer.nodes.has(node)) observer.callback([], {} as ResizeObserver) })
}
beforeEach(() => {
  frames = new Map(); serial = 0; observers.length = 0
  sourceTop = 150; stackHeight = 200; itemTops = { F1: 350, F2: 1500 }
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => { frames.set(++serial, cb); return serial })
  vi.stubGlobal('cancelAnimationFrame', (id: number) => frames.delete(id))
  vi.stubGlobal('ResizeObserver', class {
    nodes = new Set<Element>()
    constructor(public callback: ResizeObserverCallback) { observers.push(this) }
    observe(node: Element) { this.nodes.add(node) }
    unobserve(node: Element) { this.nodes.delete(node) }
    disconnect() { this.nodes.clear() }
  })
  vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockImplementation(function(this: HTMLElement) {
    if (this.hasAttribute('data-overview-source-placement-viewport')) return 700
    if (this.hasAttribute('data-result-review-source-area-host')) return 800
    if (this.closest('[data-result-findings-scroll]')) return 800
    return 0
  })
  vi.spyOn(HTMLElement.prototype, 'scrollHeight', 'get').mockImplementation(function(this: HTMLElement) {
    if (this.hasAttribute('data-result-review-source-content')) return stackHeight
    if (this.closest('[data-result-findings-scroll]')) return 1800
    return 0
  })
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function(this: HTMLElement) {
    let top = 0, height = 0
    if (this.hasAttribute('data-overview-source-placement-viewport')) { top = sourceTop; height = 700 }
    else if (this.hasAttribute('data-finding-queue-item')) {
      const viewport = this.closest('[data-slot="scroll-area-viewport"]') as HTMLElement
      top = 100 + itemTops[this.dataset.findingQueueItem!] - viewport.scrollTop; height = 100
    } else if (this.closest('[data-result-findings-scroll]')) { top = 100; height = 800 }
    return { top, height, left: 0, right: 500, bottom: top + height, width: 500, x: 0, y: top, toJSON: () => ({}) } as DOMRect
  })
  const host = document.createElement('div'); document.body.append(host)
  session = { host, root: createRoot(host) }
  act(() => session.root.render(createElement(MemoryRouter, null, createElement(Harness))))
})
afterEach(() => { act(() => session.root.unmount()); session.host.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('Overview visual pair integration', () => {
  it.each([
    { identity: 'run-2', documentId: 'doc-a' },
    { identity: 'run-1', documentId: 'doc-b' },
  ])('resets default selection and geometry for workspace $identity/$documentId', ({ identity, documentId }) => {
    queueViewport().scrollTo = options => { queueViewport().scrollTop = (options as ScrollToOptions).top! }
    tick(6)
    select('F2'); tick(6)
    expect(session.host.querySelector('[data-finding-selected="true"]')?.getAttribute('data-finding-queue-item')).toBe('F2')
    expect(placement().style.paddingTop).toBe('400px')
    sourceViewport().scrollTop = 80
    itemTops.F1 = 70; sourceTop = 100
    act(() => session.root.render(createElement(MemoryRouter, null, createElement(Harness, { identity, documentId }))))
    expect(session.host.querySelector('[data-finding-selected="true"]')?.getAttribute('data-finding-queue-item')).toBe('F1')
    expect(placement().style.visibility).toBe('hidden')
    tick(6)
    expect(placement().style.visibility).not.toBe('hidden')
    expect(placement().style.paddingTop).toBe('20px')
    expect(sourceViewport().scrollTop).toBe(0)
    expect(session.host.querySelector('[data-source-evidence-viewport]')?.getAttribute('data-viewport-key')).toContain(encodeURIComponent(documentId))
  })

  it('keeps the workspace mounted while Full Document enables the narrow Directory split', () => {
    const workspace = session.host.querySelector<HTMLElement>('[data-result-document-workspace]')!
    const layout = workspace.className
    expect(layout).toContain('flex min-h-0 min-w-0 flex-1')
    act(() => session.host.querySelector<HTMLButtonElement>('[data-result-show-full-document]')!.click())
    expect(session.host.querySelector('[data-result-document-workspace]')).toBe(workspace)
    expect(workspace.className).toContain(layout)
    expect(workspace.classList.contains('max-[840px]:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]')).toBe(true)
    expect(workspace.querySelector('[data-document-canvas="true"]')).not.toBeNull()
    act(() => session.host.querySelector<HTMLButtonElement>('[data-result-show-findings-overview]')!.click())
    expect(workspace.querySelector('[data-finding-source-document-panel="true"]')).not.toBeNull()
    expect(workspace.className).toBe(layout)
  })

  it('pairs narrow Source immediately and reveals it only after the selected Queue anchor settles', () => {
    vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener() {}, removeEventListener() {} }))
    act(() => { session.root.unmount(); session.root = createRoot(session.host); session.root.render(createElement(MemoryRouter, null, createElement(Harness))) })
    expect(placement().dataset.resultReviewSourcePlacementStatus).toBe('pending')
    expect(placement().style.visibility).toBe('hidden')
    queueViewport().scrollTo = options => { queueViewport().scrollTop = (options as ScrollToOptions).top! }
    tick(6)
    expect(placement().dataset.resultReviewSourcePlacementStatus).toBe('ready')
    expect(placement().style.visibility).not.toBe('hidden')
    expect(placement().dataset.resultReviewSourceAlignmentMode).toBe('finding-anchor')
    // Queue center: 100 + 35% of 800 = 380; Source top 150, half-stack 100.
    expect(placement().style.paddingTop).toBe('130px')
  })

  it('remeasures across layout geometry changes without resetting Source scroll', () => {
    const queue = queueViewport()
    queue.scrollTo = options => { queue.scrollTop = (options as ScrollToOptions).top! }
    tick(6)
    const source = sourceViewport()
    const local = session.host.querySelector<HTMLElement>('[data-source-evidence-viewport-scroll] [data-slot="scroll-area-viewport"]')!
    source.scrollTop = 80
    local.scrollTop = 45

    sourceTop = 170
    resizeNode(source)
    tick(6)
    expect(sourceViewport()).toBe(source)
    expect(queueViewport()).toBe(queue)
    expect(source.scrollTop).toBe(80)
    expect(session.host.querySelector('[data-source-evidence-viewport-scroll] [data-slot="scroll-area-viewport"]')).toBe(local)
    expect(local.scrollTop).toBe(45)
    expect(placement().dataset.resultReviewSourcePlacementStatus).toBe('ready')
    expect(placement().style.paddingTop).toBe('110px')

    sourceTop = 150
    resizeNode(source)
    tick(6)
    expect(sourceViewport()).toBe(source)
    expect(queueViewport()).toBe(queue)
    expect(source.scrollTop).toBe(80)
    expect(local.scrollTop).toBe(45)
    expect(placement().style.paddingTop).toBe('130px')
    expect(session.host.querySelector('[data-result-findings-panel]')?.getAttribute('data-result-findings-panel-open')).toBe('true')
  })

  it('ignores a late old Finding publisher without hiding the already-ready current Source', () => {
    const original = queueNavigation.startFindingQueueSelectionNavigation
    const publishers: Array<(center: number) => void> = []
    vi.spyOn(queueNavigation, 'startFindingQueueSelectionNavigation').mockImplementation((viewport, item, publish) => {
      publishers.push(publish)
      return original(viewport, item, publish)
    })
    queueViewport().scrollTo = options => { queueViewport().scrollTop = (options as ScrollToOptions).top! }
    tick(6)
    const lateA = publishers[0]
    select('F2'); tick(6)
    act(() => lateA(500))
    expect(placement().dataset.resultReviewSourcePlacementStatus).toBe('ready')
    expect(placement().style.visibility).not.toBe('hidden')
    expect(placement().style.paddingTop).toBe('400px')
  })
  it('keeps an interrupted pending navigation hidden and recovers on the next explicit selection', () => {
    queueViewport().scrollTo = options => { queueViewport().scrollTop = (options as ScrollToOptions).top! }
    tick(6)
    select('F2')
    queueViewport().scrollTo = () => {}; tick()
    queueViewport().dispatchEvent(new WheelEvent('wheel'))
    queueViewport().scrollTop = 300; tick(6)
    expect(placement().style.visibility).toBe('hidden')
    select('F1')
    queueViewport().scrollTo = options => { queueViewport().scrollTop = (options as ScrollToOptions).top! }
    tick(6)
    expect(placement().style.visibility).not.toBe('hidden')
    expect(placement().style.paddingTop).toBe('130px')
  })
  it('does not reuse a prior A snapshot when a rapid A to B to A selection interrupts navigation', () => {
    queueViewport().scrollTo = options => { queueViewport().scrollTop = (options as ScrollToOptions).top! }
    tick(6)
    queueViewport().scrollTop = 300
    select('F2')
    select('F1')
    queueViewport().scrollTo = () => {}
    expect(placement().dataset.resultReviewSourcePlacementStatus).toBe('pending')
    expect(placement().style.visibility).toBe('hidden')
    tick(4)
    expect(placement().style.visibility).toBe('hidden')
    act(() => { queueViewport().scrollTop = 120; queueViewport().dispatchEvent(new Event('scrollend')) })
    expect(placement().style.paddingTop).toBe('130px')
    expect(placement().style.visibility).not.toBe('hidden')
  })
  it('hides the new Source before resetting its outer scroll to neutral', () => {
    queueViewport().scrollTo = options => { queueViewport().scrollTop = (options as ScrollToOptions).top! }
    tick(6)
    const resetPresentation: Array<{ top: number; visibility: string }> = []
    let top = 80
    Object.defineProperty(sourceViewport(), 'scrollTop', { configurable: true,
      get: () => top,
      set: (value: number) => { top = value; resetPresentation.push({ top: value, visibility: placement().style.visibility }) },
    })
    select('F2')
    expect(resetPresentation).toEqual([{ top: 0, visibility: 'hidden' }])
  })
  it('keeps new Source mounted but hidden until the current selection settles, then reveals only its final placement', () => {
    queueViewport().scrollTo = options => { queueViewport().scrollTop = (options as ScrollToOptions).top! }
    tick(6)
    expect(placement().style.visibility).not.toBe('hidden')
    sourceViewport().scrollTop = 80
    select('F2')
    const newSource = session.host.querySelector<HTMLElement>('[data-result-review-source-content]')!
    expect(newSource).not.toBeNull()
    expect(newSource.scrollHeight).toBe(200)
    expect(newSource.querySelector('[data-source-evidence-viewport]')!.getAttribute('data-viewport-key')).toContain('F2')
    expect(placement().dataset.resultReviewSourcePlacementStatus).toBe('pending')
    expect(placement().dataset.resultReviewSourceAlignmentMode).toBe('pending')
    expect(placement().style.visibility).toBe('hidden')
    expect(sourceViewport().scrollTop).toBe(0)
    queueViewport().scrollTo = () => {} // new navigation has not settled
    tick(4)
    expect(placement().style.visibility).toBe('hidden')
    act(() => { queueViewport().scrollTop = 1000; queueViewport().dispatchEvent(new Event('scrollend')) })
    expect(placement().dataset.resultReviewSourcePlacementStatus).toBe('ready')
    expect(placement().style.visibility).not.toBe('hidden')
    expect(placement().style.paddingTop).toBe('400px')
    expect(session.host.querySelector('[data-result-review-source-content]')).toBe(newSource)
  })
  it('reveals formal top only after both the settled anchor and a tall stack are ready', () => {
    stackHeight = 800
    queueViewport().scrollTo = () => {}
    tick()
    expect(placement().dataset.resultReviewSourcePlacementStatus).toBe('pending')
    expect(placement().style.visibility).toBe('hidden')
    act(() => { queueViewport().scrollTop = 120; queueViewport().dispatchEvent(new Event('scrollend')) })
    expect(placement().dataset.resultReviewSourcePlacementStatus).toBe('ready')
    expect(placement().dataset.resultReviewSourceAlignmentMode).toBe('top')
    expect(placement().style.visibility).not.toBe('hidden')
    expect(placement().style.paddingTop).toBe('')
  })
  it('keeps a settled Finding hidden until its natural stack has a measurable height', () => {
    stackHeight = 0
    queueViewport().scrollTo = options => { queueViewport().scrollTop = (options as ScrollToOptions).top! }
    tick(6)
    expect(placement().dataset.resultReviewSourcePlacementStatus).toBe('pending')
    expect(placement().style.visibility).toBe('hidden')
    const natural = session.host.querySelector<HTMLElement>('[data-result-review-source-content]')!
    stackHeight = 200; resizeNode(natural)
    expect(placement().dataset.resultReviewSourcePlacementStatus).toBe('ready')
    expect(placement().style.visibility).not.toBe('hidden')
    expect(placement().style.paddingTop).toBe('130px')
  })
  it('does not hide ready Source during ordinary remeasure or manual Queue scroll', () => {
    queueViewport().scrollTo = options => { queueViewport().scrollTop = (options as ScrollToOptions).top! }
    tick(6)
    const natural = session.host.querySelector<HTMLElement>('[data-result-review-source-content]')!
    stackHeight = 300; resizeNode(natural)
    expect(placement().dataset.resultReviewSourcePlacementStatus).toBe('ready')
    expect(placement().style.visibility).not.toBe('hidden')
    queueViewport().scrollTop = 250; queueViewport().dispatchEvent(new Event('scroll'))
    tick(6)
    expect(placement().style.paddingTop).toBe('80px')
    expect(placement().style.visibility).not.toBe('hidden')
    act(() => window.dispatchEvent(new Event('resize')))
    expect(placement().dataset.resultReviewSourcePlacementStatus).toBe('ready')
    expect(placement().style.visibility).not.toBe('hidden')
  })
  it('rejects an old Result snapshot immediately even when the new Result reuses the selected ID', () => {
    queueViewport().scrollTo = options => { queueViewport().scrollTop = (options as ScrollToOptions).top! }
    tick(6)
    act(() => session.root.render(createElement(MemoryRouter, null, createElement(Harness, { identity: 'run-pending' }))))
    expect(placement().dataset.resultReviewSourcePlacementStatus).toBe('pending')
    expect(placement().style.visibility).toBe('hidden')
    tick(6)
    expect(placement().dataset.resultReviewSourcePlacementStatus).toBe('ready')
  })

  it('waits for Queue navigation and aligns in the exact usable Source viewport', () => {
    const viewport = queueViewport()
    viewport.scrollTo = () => {} // smooth navigation remains in flight
    tick()
    expect(placement().style.paddingTop).toBe('')
    expect(sourceViewport()).not.toBeNull()
    expect(sourceViewport().contains(session.host.querySelector('[data-result-workspace-toolbar]'))).toBe(false)
    expect(sourceViewport().contains(placement())).toBe(true)
    act(() => { viewport.scrollTop = 120; viewport.dispatchEvent(new Event('scrollend')) })
    tick()
    expect(placement().dataset.resultReviewSourceAlignmentMode).toBe('finding-anchor')
    expect(placement().style.paddingTop).toBe('130px') // 380 - 150 - 200/2
  })
  it('uses a clamped high Finding actual center, not a second 35 percent axis', () => {
    itemTops.F1 = 70; sourceTop = 100
    queueViewport().scrollTo = options => { queueViewport().scrollTop = (options as ScrollToOptions).top! }
    tick(6)
    expect(queueViewport().scrollTop).toBe(0)
    expect(placement().style.paddingTop).toBe('20px') // actual center 220
  })
  it('keeps the snapshot during manual Queue/Source scroll and rebuilds it on a new selection', () => {
    queueViewport().scrollTo = options => { queueViewport().scrollTop = (options as ScrollToOptions).top! }
    tick(6)
    expect(placement().style.paddingTop).toBe('130px')
    queueViewport().scrollTop = 300; queueViewport().dispatchEvent(new Event('scroll'))
    sourceViewport().scrollTop = 80; sourceViewport().dispatchEvent(new Event('scroll'))
    tick(6)
    expect(placement().style.paddingTop).toBe('130px')
    expect(sourceViewport().scrollTop).toBe(80)
    select('F2'); tick(6)
    expect(queueViewport().scrollTop).toBe(1000)
    expect(sourceViewport().scrollTop).toBe(0)
    expect(placement().style.paddingTop).toBe('400px') // actual last center 650
  })
  it('does not resnapshot a manually moved Queue on review notes or ordinary rerenders', () => {
    queueViewport().scrollTo = options => { queueViewport().scrollTop = (options as ScrollToOptions).top! }
    tick(6)
    queueViewport().scrollTop = 300; sourceViewport().scrollTop = 80
    act(() => session.root.render(createElement(MemoryRouter, null, createElement(Harness, { note: 'review note' }))))
    resizeNode(queueViewport()); tick(6)
    expect(queueViewport().scrollTop).toBe(300)
    expect(sourceViewport().scrollTop).toBe(80)
    expect(placement().style.paddingTop).toBe('130px')
  })
  it('rebuilds the geometry after a layout resize', () => {
    queueViewport().scrollTo = options => { queueViewport().scrollTop = (options as ScrollToOptions).top! }
    tick(6)
    sourceTop = 200
    act(() => window.dispatchEvent(new Event('resize')))
    tick(6)
    expect(placement().style.paddingTop).toBe('80px')
  })
  it('preserves user-owned Source outer scroll on a resize of the same selection', () => {
    queueViewport().scrollTo = options => { queueViewport().scrollTop = (options as ScrollToOptions).top! }
    tick(6)
    sourceViewport().scrollTop = 80
    act(() => window.dispatchEvent(new Event('resize')))
    tick(6)
    expect(sourceViewport().scrollTop).toBe(80)
  })
  it('starts a new Result identity with fresh geometry even when its selected ID is reused', () => {
    queueViewport().scrollTo = options => { queueViewport().scrollTop = (options as ScrollToOptions).top! }
    tick(6)
    itemTops.F1 = 70; sourceTop = 100
    sourceViewport().scrollTop = 80
    act(() => session.root.render(createElement(MemoryRouter, null, createElement(Harness, { identity: 'run-2' }))))
    tick(6)
    expect(queueViewport().scrollTop).toBe(0)
    expect(placement().style.paddingTop).toBe('20px')
    expect(sourceViewport().scrollTop).toBe(0)
  })
  it('measures the natural stack, and top-aligns when the complete stack cannot fit', () => {
    queueViewport().scrollTo = options => { queueViewport().scrollTop = (options as ScrollToOptions).top! }
    tick(6)
    const natural = session.host.querySelector<HTMLElement>('[data-result-review-source-content]')!
    expect(natural.style.paddingTop).toBe('')
    stackHeight = 300; resizeNode(natural)
    expect(placement().style.paddingTop).toBe('80px') // excludes previous padding
    stackHeight = 800; resizeNode(natural)
    expect(placement().dataset.resultReviewSourceAlignmentMode).toBe('top')
    expect(placement().style.paddingTop).toBe('')
  })
  it('preserves evidence viewport DOM and local scroll across same-finding review rerenders and reselection', () => {
    const inner = session.host.querySelector<HTMLElement>('[data-source-evidence-viewport-scroll] [data-slot="scroll-area-viewport"]')!
    inner.scrollTop = 45
    act(() => session.root.render(createElement(MemoryRouter, null, createElement(Harness, { note: 'Review note' }))))
    expect(session.host.querySelector('[data-source-evidence-viewport-scroll] [data-slot="scroll-area-viewport"]')).toBe(inner)
    expect(inner.scrollTop).toBe(45)
    select('F1')
    expect(session.host.querySelector('[data-source-evidence-viewport-scroll] [data-slot="scroll-area-viewport"]')).toBe(inner)
    expect(inner.scrollTop).toBe(45)
  })

  it('accounts for the existing panel padding when measuring the actual inner content box', () => {
    queueViewport().scrollTo = options => { queueViewport().scrollTop = (options as ScrollToOptions).top! }
    tick(6)
    const viewport = sourceViewport()
    viewport.style.paddingTop = '12px'; viewport.style.paddingBottom = '12px'
    resizeNode(viewport)
    expect(placement().style.paddingTop).toBe('118px') // 380 - (150+12) - 200/2
  })

})
