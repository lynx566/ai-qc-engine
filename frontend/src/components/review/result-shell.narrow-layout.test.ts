// @vitest-environment happy-dom

import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  ResultShellLoaded,
  type ResultShellLoadedProps,
} from '@/components/review/result-shell'
import type { DocumentOutlineEntry } from '@/lib/document-outline'
import type {
  DocumentConsistencyQcResult,
  InternalResultFinding,
  InternalResultScopeResult,
} from '@/types/document-consistency-qc'
import type { DocumentView } from '@/types/document-review'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

const shellSource = readFileSync(resolve(import.meta.dirname, 'result-shell.tsx'), 'utf8')

const document: DocumentView = {
  docId: 'doc_test',
  fileName: 'sample.docx',
  displayName: 'sample.docx',
  blocks: [
    {
      blockId: 'doc_test:C0030',
      sourceBlockId: 'C0030',
      kind: 'heading',
      docOrderIndex: 80,
      headingLevel: 1,
      headingPath: ['4. 临床安全性'],
      displayText: '4. 临床安全性',
    },
    {
      blockId: 'doc_test:B1',
      sourceBlockId: 'B1',
      kind: 'paragraph',
      docOrderIndex: 81,
      headingPath: ['4. 临床安全性'],
      displayText: 'Supporting detail.',
      sentences: [{
        sentenceId: 'B1:S1',
        rawText: 'Supporting detail.',
        normalizedText: 'Supporting detail.',
      }],
    },
    {
      blockId: 'doc_test:B2',
      sourceBlockId: 'B2',
      kind: 'paragraph',
      docOrderIndex: 82,
      headingPath: ['4. 临床安全性'],
      displayText: 'Hidden full-document detail.',
      sentences: [{
        sentenceId: 'B2:S1',
        rawText: 'Hidden full-document detail.',
        normalizedText: 'Hidden full-document detail.',
      }],
    },
  ],
}

const scopeResult: InternalResultScopeResult = {
  slotId: 'source',
  docId: 'doc_test',
  scopeId: 'HS0001',
  headingPath: ['4. 临床安全性'],
  outlineHeadingBlockId: 'C0030',
  semanticModuleId: 'clinical_safety',
  executionStatus: 'partial',
  hasSuccessfulCheck: true,
}

const result: DocumentConsistencyQcResult = {
  flowId: 'document_consistency_qc',
  flowRunId: 'document_consistency_qc_test',
  capabilityId: 'internal_dsur',
  flowStatus: 'success',
  comparisonRunStatus: 'success',
  finalizationStatus: 'completed',
  fallbackComparisonModes: [],
  findings: [],
  scopeResults: [scopeResult],
}

const outlineEntries: DocumentOutlineEntry[] = [
  {
    blockId: 'doc_test:C0030',
    title: '4. 临床安全性',
    headingLevel: 1,
    headingPath: ['4. 临床安全性'],
    docOrderIndex: 80,
  },
]

const loadedShellProps: ResultShellLoadedProps = {
      taskDisplayName: 'DSUR',
      functionViewQuery: { mode: 'all' },
      availableSemanticModuleIds: ['clinical_safety'],
      result,
      reviewState: null,
      document,
      documentStatus: 'ready',
      documentError: null,
      outlineEntries,
      scopeResultsByOutlineBlockId: new Map([['doc_test:C0030', [scopeResult]]]),
      activeOutlineBlockId: 'doc_test:C0030',
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

const selectedFinding: InternalResultFinding = {
  findingId: 'finding-1',
  label: 'fail',
  conclusion: 'Finding',
  comparisonModeId: 'scope_local',
  evidenceRefs: [{
    slotId: 'source',
    docId: 'doc_test',
    blockId: 'B1',
    sentenceId: 'B1:S1',
    sentenceAlias: 'T1',
  }],
}

const resultWithFinding: DocumentConsistencyQcResult = {
  ...result,
  findings: [selectedFinding],
}

function loadedShellElement(overrides: Partial<ResultShellLoadedProps> = {}) {
  return createElement(
    MemoryRouter,
    null,
    createElement(ResultShellLoaded, { ...loadedShellProps, ...overrides }),
  )
}

function renderLoadedShell() {
  return renderToStaticMarkup(loadedShellElement())
}

function findingsShellElement(overrides: Partial<ResultShellLoadedProps> = {}) {
  return loadedShellElement({
    result: resultWithFinding,
    selectedFindingId: selectedFinding.findingId,
    selectedFinding,
    selectedEvidenceLocations: selectedFinding.evidenceRefs,
    ...overrides,
  })
}

function showResultFullDocument(host: HTMLElement) {
  act(() => host.querySelector<HTMLButtonElement>(
    '[data-result-show-full-document="true"]',
  )?.click())
}

function mockViewportWidth(initialWidth: number) {
  let width = initialWidth
  const listeners = new Set<(event: MediaQueryListEvent) => void>()
  vi.spyOn(window, 'matchMedia').mockImplementation((query) => ({
    matches: width >= 840,
    media: query,
    onchange: null,
    addEventListener: (_type: string, listener: EventListenerOrEventListenerObject) => {
      listeners.add(listener as (event: MediaQueryListEvent) => void)
    },
    removeEventListener: (_type: string, listener: EventListenerOrEventListenerObject) => {
      listeners.delete(listener as (event: MediaQueryListEvent) => void)
    },
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => true,
  }))
  return (nextWidth: number) => {
    const crossed = (width >= 840) !== (nextWidth >= 840)
    width = nextWidth
    if (crossed) act(() => listeners.forEach(listener => listener({
      matches: width >= 840, media: '(min-width: 840px)',
    } as MediaQueryListEvent)))
  }
}

afterEach(() => vi.restoreAllMocks())

describe('ResultShell narrow-desktop layout', () => {
  it.each([320, 839.5, 840, 1024])('mirrors the open Directory tracks and canonical surface geometry at %spx', (width) => {
    mockViewportWidth(width)
    const host = window.document.createElement('div')
    const root = createRoot(host)
    try {
      act(() => root.render(findingsShellElement()))
      const toolbar = host.querySelector('[data-result-workspace-toolbar]')!
      expect(toolbar.querySelector('[data-result-toolbar-document-zone]')).toBeNull()
      expect(toolbar.classList.contains('px-3')).toBe(true)
      expect(toolbar.querySelector('[aria-label="结果导航"]')?.classList.contains('mr-2')).toBe(true)
      showResultFullDocument(host)
      expect(host.querySelectorAll('[data-result-workspace-toolbar]')).toHaveLength(1)
      expect(host.querySelector('[data-result-workspace-toolbar]')).toBe(toolbar)
      expect(toolbar.classList.contains('grid')).toBe(true)
      expect(toolbar.classList.contains('min-[840px]:grid-cols-[22.5rem_minmax(0,1fr)]')).toBe(true)
      expect(toolbar.classList.contains('max-[840px]:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]')).toBe(true)
      const directoryZone = toolbar.querySelector('[data-result-toolbar-directory-zone]')!
      const documentZone = toolbar.querySelector('[data-result-toolbar-document-zone]')!
      expect(directoryZone.parentElement).toBe(toolbar)
      expect(documentZone.parentElement).toBe(toolbar)
      const canvas = host.querySelector('[data-document-canvas]')!
      for (const token of ['px-2', 'min-[840px]:px-4', 'min-[840px]:sm:px-8']) {
        expect(documentZone.classList.contains(token)).toBe(true)
        expect(canvas.classList.contains(token)).toBe(true)
      }
      const surface = documentZone.querySelector('[data-result-toolbar-surface]')!
      const article = host.querySelector('article.document-surface')!
      for (const token of ['w-full', 'min-w-0', 'max-w-full', 'mx-auto', 'min-[840px]:max-w-[56rem]']) {
        expect(surface.classList.contains(token)).toBe(true)
        expect(article.classList.contains(token)).toBe(true)
      }
      expect(surface.classList.contains('max-w-[56rem]')).toBe(false)
      const actions = surface.querySelector('[aria-label="结果导航"]')!
      expect(actions.classList.contains('justify-end-safe')).toBe(true)
      expect(actions.classList.contains('overflow-x-auto')).toBe(false)
      expect(actions.classList.contains('flex-wrap')).toBe(true)
      expect(actions.classList.contains('shrink-0')).toBe(false)
      expect(actions.classList.contains('mr-2')).toBe(false)
      const annotations = actions.querySelector('[data-document-annotation-toolbar]')!
      expect(annotations.classList.contains('max-w-full')).toBe(true)
      expect(annotations.classList.contains('overflow-x-auto')).toBe(true)
      expect(annotations.classList.contains('overflow-y-hidden')).toBe(true)
      // Leave room inside the horizontal scroller for the 3px focus ring and pressed offset.
      expect(annotations.classList.contains('p-1')).toBe(true)
      expect(annotations.classList.contains('-m-1')).toBe(true)
      expect(annotations.classList.contains('[&_[data-source-annotation-navigator]]:justify-end-safe')).toBe(true)
      expect(annotations.classList.contains('shrink-0')).toBe(false)
      expect(actions.querySelectorAll('[data-source-annotation-nav]')).toHaveLength(2)
      for (const wrapper of [toolbar, documentZone, surface, actions, annotations]) {
        expect([...wrapper.classList].some(token => /^(overflow|overflow-y)-(auto|scroll)$/.test(token))).toBe(false)
        expect([...wrapper.classList].some(token => /^(max-)?h-/.test(token))).toBe(false)
      }
      expect(surface.classList.contains('flex-wrap')).toBe(true)
      for (const nav of actions.querySelectorAll('[data-source-annotation-nav]')) {
        expect(nav.classList.contains('flex-col')).toBe(true)
        expect(nav.classList.contains('w-5')).toBe(true)
        expect(nav.querySelectorAll('button')).toHaveLength(2)
      }
      const showFindings = actions.querySelector<HTMLButtonElement>('[data-result-show-findings-overview]')!
      expect(showFindings).not.toBeNull()
      act(() => showFindings.focus())
      act(() => showFindings.click())
      expect(toolbar.querySelector('[data-result-toolbar-document-zone]')).toBeNull()
      expect(toolbar.querySelector('[data-result-show-full-document]')).not.toBeNull()
    } finally {
      act(() => root.unmount())
    }
  })

  it.each([320, 839.5, 840, 1024])('centers against the full pane when Directory is collapsed at %spx', (width) => {
    mockViewportWidth(width)
    const host = window.document.createElement('div')
    const root = createRoot(host)
    try {
      act(() => root.render(loadedShellElement()))
      const toolbar = host.querySelector('[data-result-workspace-toolbar]')!
      const reader = host.querySelector('[data-document-canvas]')!
      act(() => host.querySelector<HTMLButtonElement>('[data-result-document-navigator-collapse]')!.click())
      expect(toolbar.classList.contains('grid-cols-1')).toBe(true)
      expect(toolbar.classList.contains('min-[840px]:grid-cols-[22.5rem_minmax(0,1fr)]')).toBe(false)
      const documentZone = toolbar.querySelector('[data-result-toolbar-document-zone]')!
      const surface = documentZone.querySelector('[data-result-toolbar-surface]')!
      const directoryZone = surface.querySelector('[data-result-toolbar-directory-zone]')!
      const reopen = directoryZone.querySelector<HTMLButtonElement>('[data-result-document-navigator-trigger]')!
      expect(documentZone.parentElement).toBe(toolbar)
      expect(toolbar.children).toHaveLength(1)
      expect(surface.classList.contains('w-full')).toBe(true)
      expect(surface.classList.contains('flex-wrap')).toBe(true)
      expect(reopen).not.toBeNull()
      const actions = surface.querySelector('[role="group"]')!
      const annotations = actions.querySelector('[data-document-annotation-toolbar]')!
      expect(actions.classList.contains('flex-wrap')).toBe(true)
      expect(actions.classList.contains('overflow-x-auto')).toBe(false)
      expect(annotations.classList.contains('overflow-y-hidden')).toBe(true)
      for (const wrapper of [toolbar, documentZone, surface, actions, annotations]) {
        expect([...wrapper.classList].some(token => /^(overflow|overflow-y)-(auto|scroll)$/.test(token))).toBe(false)
        expect([...wrapper.classList].some(token => /^(max-)?h-/.test(token))).toBe(false)
      }
      act(() => reopen.click())
      expect(host.querySelector('[data-result-outline-inline]')).not.toBeNull()
      expect(host.querySelector('[data-document-canvas]')).toBe(reader)
      expect(host.querySelector('[data-result-workspace-toolbar]')).toBe(toolbar)
    } finally {
      act(() => root.unmount())
    }
  })

  it.each([320, 839.5, 840, 1024])('shows counts and help without navigation or management in Result at %spx', (width) => {
    mockViewportWidth(width)
    const host = window.document.createElement('div')
    const root = createRoot(host)
    act(() => root.render(findingsShellElement()))
    const toolbar = host.querySelector('[data-result-workspace-toolbar]')!
    expect(toolbar.querySelector('[data-source-annotation-label="revision"]')?.textContent).toBe('修订 0')
    expect(toolbar.querySelector('[data-source-annotation-label="comment"]')?.textContent).toBe('批注 0')
    expect(toolbar.querySelectorAll('[data-source-annotation-help]')).toHaveLength(1)
    expect(toolbar.querySelector('[data-source-annotation-nav]')).toBeNull()
    expect(toolbar.querySelector('[data-source-annotation-menu-trigger]')).toBeNull()
    expect(toolbar.querySelectorAll('button')).toHaveLength(2)
    expect(toolbar.querySelector('[data-result-show-full-document]')).not.toBeNull()
    expect(toolbar.classList.contains('flex-wrap')).toBe(true)
    const annotationContext = toolbar.querySelector('[data-source-annotation-context]')!
    expect(annotationContext.classList.contains('flex-wrap')).toBe(true)
    expect(annotationContext.classList.contains('rounded-[4px]')).toBe(true)
    expect(annotationContext.querySelector('[data-source-annotation-context-separator]')).not.toBeNull()
    const commentWithHelp = annotationContext.querySelector('[data-source-annotation-comment-with-help]')!
    expect(commentWithHelp.querySelector('[data-source-annotation-label="comment"]')).not.toBeNull()
    expect(commentWithHelp.querySelector('[data-source-annotation-help]')).not.toBeNull()
    const resultNav = toolbar.querySelector('[aria-label="结果导航"]')!
    expect(resultNav.contains(annotationContext)).toBe(true)
    const fullDocument = toolbar.querySelector('[data-result-show-full-document]')! as HTMLButtonElement
    expect(fullDocument.getAttribute('data-variant')).toBe('outline')
    expect(fullDocument.getAttribute('data-size')).toBe('default')
    expect(resultNav.contains(fullDocument)).toBe(true)
    expect(
      annotationContext.compareDocumentPosition(fullDocument) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
    act(() => root.unmount())
  })

  it.each(['focus', 'hover'])('reveals the shared annotation guidance on %s in Result', async (interaction) => {
    const host = window.document.createElement('div')
    window.document.body.appendChild(host)
    const root = createRoot(host)
    try {
      act(() => root.render(findingsShellElement()))
      const trigger = host.querySelector<HTMLButtonElement>('[data-source-annotation-help]')!
      expect(trigger).not.toBeNull()
      await act(async () => {
        if (interaction === 'focus') trigger.focus()
        else trigger.dispatchEvent(new PointerEvent('pointermove', { bubbles: true, pointerType: 'mouse' }))
      })
      await vi.waitFor(() => {
        const tooltip = window.document.body.querySelector('[role="tooltip"]')!
        expect(tooltip).not.toBeNull()
        for (const text of [
          '左键选中文字可进行修订或批注，目前仅支持单句内选中。',
          '进行修订或批注不会直接改动上传的源文件，可点击“完整文档”查看全部审阅痕迹。',
        ]) expect(tooltip.textContent).toContain(text)
      })
    } finally {
      act(() => root.unmount())
      host.remove()
    }
  })

  it('keeps one toolbar above content through view switches and breakpoints', () => {
    const setViewportWidth = mockViewportWidth(1024)
    const host = window.document.createElement('div')
    const root = createRoot(host)
    act(() => root.render(findingsShellElement()))

    const toolbar = host.querySelector('[data-result-workspace-toolbar="true"]')!
    expect(toolbar).not.toBeNull()
    expect(toolbar.parentElement?.tagName).toBe('MAIN')
    expect(toolbar.nextElementSibling).toBe(host.querySelector('[data-result-main-content]'))
    expect(toolbar.querySelector('[data-result-show-full-document]')).not.toBeNull()
    expect(toolbar.querySelector('[data-source-annotation-navigator]')).toBeNull()
    showResultFullDocument(host)
    expect(host.querySelector('[data-result-workspace-toolbar]')).toBe(toolbar)
    expect(toolbar.querySelector('[data-result-show-findings-overview]')).not.toBeNull()
    const navigator = toolbar.querySelector('[data-source-annotation-navigator]')!
    expect(navigator).not.toBeNull()

    for (const width of [839.5, 840, 320, 1024]) {
      setViewportWidth(width)
      expect(host.querySelectorAll('[data-result-workspace-toolbar]')).toHaveLength(1)
      expect(host.querySelector('[data-result-workspace-toolbar]')).toBe(toolbar)
      expect(host.querySelectorAll('[data-source-annotation-navigator]')).toHaveLength(1)
      expect(toolbar.querySelector('[data-source-annotation-navigator]')).toBe(navigator)
    }
    expect(host.querySelector('[data-result-document-toolbar]')).toBeNull()
    expect(host.querySelector('[data-result-outline-trigger]')).toBeNull()
    expect(host.querySelector('[data-result-document-view-controls]')).toBeNull()
    expect(host.querySelector('[data-result-outline-inline]')).not.toBeNull()
    act(() => toolbar.querySelector<HTMLButtonElement>('[data-result-show-findings-overview]')!.click())
    expect(host.querySelector('[data-result-workspace-toolbar]')).toBe(toolbar)
    expect(toolbar.querySelector('[data-result-show-full-document]')).not.toBeNull()
    expect(host.querySelector('[data-result-outline-inline]')).toBeNull()
    showResultFullDocument(host)
    expect(host.querySelector('[data-result-outline-inline]')).not.toBeNull()
    act(() => root.unmount())
  })

  it('preserves the canonical reader and its scroll when toolbar utilities and breakpoint change', () => {
    const setViewportWidth = mockViewportWidth(1024)
    const host = window.document.createElement('div')
    const root = createRoot(host)
    act(() => root.render(loadedShellElement()))
    const reader = host.querySelector('[data-document-canvas]')!
    const viewport = reader.closest<HTMLElement>('[data-slot="scroll-area-viewport"]')!
    viewport.scrollTop = 75
    const outlineViewport = host.querySelector<HTMLElement>(
      '[data-result-outline-inline] [data-slot="scroll-area-viewport"]',
    )!
    outlineViewport.scrollTop = 30
    expect(viewport.scrollTop).toBe(75)
    expect(outlineViewport).not.toBe(viewport)
    act(() => host.querySelector<HTMLButtonElement>('[data-result-document-navigator-collapse]')!.click())
    expect(host.querySelector('[data-document-canvas]')).toBe(reader)
    expect(viewport.scrollTop).toBe(75)
    act(() => host.querySelector<HTMLButtonElement>('[data-result-document-navigator-trigger="inline"]')!.click())
    setViewportWidth(839.5)
    setViewportWidth(840)
    act(() => host.querySelector<HTMLButtonElement>('[data-result-document-navigator-collapse]')!.click())
    act(() => root.render(loadedShellElement({ savingAnnotationId: 'annotation-1' })))
    expect(host.querySelector('[data-document-canvas]')).toBe(reader)
    expect(reader.closest('[data-slot="scroll-area-viewport"]')).toBe(viewport)
    expect(viewport.scrollTop).toBe(75)
    expect(host.querySelector('[data-result-show-findings-overview]')).toBeNull()
    act(() => root.unmount())
  })

  it('fills the parent flex remainder without a percentage-height dependency', () => {
    const html = renderLoadedShell()
    const rootClassName = html.match(/^<div class="([^"]*)"/)?.[1]?.split(' ') ?? []

    expect(rootClassName).toContain('flex-1')
    expect(rootClassName).toContain('min-h-0')
    expect(rootClassName).toContain('overflow-hidden')
    expect(rootClassName).not.toContain('h-full')
  })

  it('places Source Evidence left and Finding workspace right in desktop Overview', () => {
    const html = renderToStaticMarkup(findingsShellElement())
    expect(html).not.toContain('data-result-navigation-rail="true"')
    expect(html.indexOf('data-result-findings-panel="true"')).toBeGreaterThan(-1)
    expect(html.indexOf('data-result-findings-panel="true"')).toBeGreaterThan(
      html.indexOf('data-result-document-pane="true"'),
    )
    expect(shellSource).toContain('resultOverviewFindingsWorkspaceGridClassName')
    expect(shellSource).toContain('result-review-stage-layout')
    expect(html).toContain('data-result-finding-reading-column="true"')
    const host = window.document.createElement('div')
    host.innerHTML = html
    const findingsPane = host.querySelector('[data-result-findings-panel="true"]')
    expect(findingsPane?.previousElementSibling?.tagName).toBe('MAIN')
    expect(findingsPane?.classList.contains('border-l')).toBe(true)
    expect(findingsPane?.classList.contains('border-r')).toBe(false)
    expect(host.firstElementChild?.classList.contains(
      'min-[840px]:grid-cols-[minmax(0,1fr)_clamp(28.75rem,34%,35rem)]',
    )).toBe(true)
  })

  it('keeps the evidence viewport panel horizontally contained in Overview', () => {
    const host = window.document.createElement('div')
    const root = createRoot(host)

    act(() => root.render(findingsShellElement()))
    const overviewPanel = host.querySelector('[data-finding-source-document-panel="true"]')
    expect(overviewPanel?.className).toContain('min-w-0')

    act(() => root.unmount())
  })

  it.each([839.5, 840])('keeps the single reopen control in the shared toolbar at %spx', (width) => {
    mockViewportWidth(width)
    const host = window.document.createElement('div')
    const root = createRoot(host)
    act(() => root.render(loadedShellElement()))
    const toolbar = host.querySelector('[data-result-workspace-toolbar]')!
    expect(toolbar.querySelector('[data-result-document-navigator-trigger]')).toBeNull()
    expect(toolbar.querySelector('[data-document-annotation-toolbar]')).not.toBeNull()
    act(() => host.querySelector<HTMLButtonElement>('[data-result-document-navigator-collapse]')!.click())
    const reopen = toolbar.querySelector('[data-result-document-navigator-trigger="inline"]')!
    expect(toolbar.querySelectorAll('[data-result-document-navigator-trigger]')).toHaveLength(1)
    expect(reopen.classList.contains('hidden')).toBe(false)
    expect(reopen.classList.contains('min-[840px]:inline-flex')).toBe(false)
    expect(toolbar.classList.contains('shrink-0')).toBe(true)
    act(() => root.unmount())
  })

  it('keeps Findings and canonical Directory utilities isolated by result view', () => {
    const host = window.document.createElement('div')
    const root = createRoot(host)

    act(() => root.render(findingsShellElement()))
    expect(host.querySelector('[data-result-outline-trigger="true"]')).toBeNull()
    expect(host.querySelector('[data-result-workspace-utilities="true"]')).toBeNull()

    showResultFullDocument(host)
    act(() => host.querySelector<HTMLButtonElement>('[data-result-document-navigator-collapse]')!.click())

    const utilities = host.querySelector('[data-result-workspace-utilities="true"]')
    const controls = Array.from(utilities?.querySelectorAll('button') ?? [])

    expect(controls.map((control) => control.getAttribute('aria-label'))).toEqual(['打开文档目录'])
    expect(controls[0]?.getAttribute('aria-expanded')).toBe('false')
    expect(controls[0]?.querySelector('.lucide-list-tree')).not.toBeNull()

    act(() => root.unmount())
  })

  it('does not render the document filename in the workspace toolbar', () => {
    const host = window.document.createElement('div')
    const root = createRoot(host)

    act(() => root.render(findingsShellElement()))
    showResultFullDocument(host)

    const toolbar = host.querySelector('[data-result-workspace-toolbar="true"]')
    expect(toolbar?.querySelector('[data-result-document-name]')).toBeNull()
    expect(toolbar?.textContent).not.toContain('sample.docx')

    act(() => root.unmount())
  })

  it('does not leave an empty utility row in Findings Overview', () => {
    const host = window.document.createElement('div')
    const root = createRoot(host)

    act(() => root.render(loadedShellElement({
      result: { ...result, findings: [selectedFinding] },
      selectedFindingId: selectedFinding.findingId,
      selectedFinding,
    })))

    expect(host.querySelector('[data-result-workspace-utilities="true"]')).toBeNull()
    expect(host.querySelector('[data-result-outline-trigger="true"]')).toBeNull()

    act(() => root.unmount())
  })

  it('mounts only one annotation toolbar in the shared owner', () => {
    const host = window.document.createElement('div')
    const root = createRoot(host)
    act(() => root.render(loadedShellElement()))
    const toolbar = host.querySelector('[data-result-workspace-toolbar]')!
    expect(host.querySelectorAll('[data-document-annotation-toolbar]')).toHaveLength(1)
    expect(host.querySelectorAll('[data-source-annotation-navigator]')).toHaveLength(1)
    expect(toolbar.contains(host.querySelector('[data-source-annotation-navigator]'))).toBe(true)
    expect(toolbar.querySelector('[data-source-annotation-help]')).toBeNull()
    act(() => root.unmount())
  })

  it('places the desktop Directory trigger in the shared Result toolbar without a separate column', () => {
    const host = window.document.createElement('div')
    const root = createRoot(host)

    act(() => root.render(loadedShellElement()))
    act(() => host.querySelector<HTMLButtonElement>('[data-result-document-navigator-collapse]')!.click())

    const documentToolbar = host.querySelector('[data-result-workspace-toolbar="true"]')
    const desktopTrigger = host.querySelector(
      '[data-result-document-navigator-trigger="inline"]',
    )
    expect(host.querySelector('[data-result-document-navigator-trigger-slot]')).toBeNull()
    expect(documentToolbar?.contains(desktopTrigger)).toBe(true)
    expect(desktopTrigger?.querySelector('.lucide-list-tree')).not.toBeNull()
    expect(desktopTrigger?.querySelector('.lucide-panel-left')).toBeNull()

    act(() => root.unmount())
  })

  it.each([320, 640, 839, 839.5])('shows Source then one Finding pane by default at %spx', (width) => {
    mockViewportWidth(width)
    const host = window.document.createElement('div')
    const root = createRoot(host)

    act(() => root.render(findingsShellElement()))
    const grid = host.firstElementChild!
    const source = grid.firstElementChild!
    const panel = grid.lastElementChild!
    expect(grid.children.length).toBe(2)
    expect(source.tagName).toBe('MAIN')
    expect(source.querySelector('[data-finding-source-document-panel="true"]')).not.toBeNull()
    expect(source.classList.contains('hidden')).toBe(false)
    expect(panel.getAttribute('data-result-findings-panel')).toBe('true')
    expect(panel.classList.contains('hidden')).toBe(false)
    expect(panel.classList.contains('flex')).toBe(true)
    expect(panel.classList.contains('border-l')).toBe(true)
    expect(panel.classList.contains('border-r')).toBe(false)
    expect(panel.getAttribute('data-result-findings-panel-open')).toBe('true')
    expect(panel.querySelector('[data-result-pane-header="true"]')).not.toBeNull()
    expect(panel.querySelector('[data-document-identity]')?.getAttribute('aria-label'))
      .toBe('DSUR · sample.docx')
    expect(host.querySelectorAll('[data-result-findings-scroll="true"]')).toHaveLength(1)
    expect(host.querySelector('[data-result-findings-trigger]')).toBeNull()
    expect(host.querySelector('[data-result-findings-inline-pane]')).toBeNull()
    expect(host.querySelector('[data-findings-open]')).toBeNull()
    expect(host.querySelector('[data-result-findings-close]')).toBeNull()
    expect(host.querySelector('[data-result-findings-reopen]')).toBeNull()
    expect(grid.classList.contains(
      'max-[840px]:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]',
    )).toBe(true)
    expect(host.querySelector('[data-result-main-content="true"]')?.classList.contains('grid')).toBe(false)
    act(() => root.unmount())
  })

  it('uses a bounded Queue column and flexible Document from 840px upward', () => {
    expect(shellSource).toContain('resultOverviewFindingsWorkspaceGridClassName')
    expect(shellSource).toContain('result-review-stage-layout')
    expect(shellSource).toContain('data-result-outline-inline="true"')
    expect(shellSource).toContain('min-[840px]:w-[22.5rem] min-[840px]:shrink-0')
    expect(shellSource).not.toContain('w-[336px]')
    expect(shellSource).not.toContain('xl:w-[360px]')
  })

  it('adds horizontal containment to main while keeping flex-1 min-w-0', () => {
    expect(shellSource).toMatch(
      /<main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden/,
    )
  })

  it('shares workspace divider token on toolbar bottom and findings pane left', () => {
    const toolbarBlock = shellSource.match(
      /data-result-workspace-toolbar="true"[\s\S]*?className=\{cn\([\s\S]*?\)\}/,
    )?.[0]
    const findingsPaneBlock = shellSource.match(
      /data-result-findings-panel="true"[\s\S]*?className=\{cn\([\s\S]*?\)\}/,
    )?.[0]

    expect(toolbarBlock).toContain('resultReviewWorkspaceDividerBorderClassName')
    expect(findingsPaneBlock).toContain('resultReviewWorkspaceDividerBorderClassName')
    expect(toolbarBlock).not.toContain('resultReviewInternalSeparatorBorderClassName')
  })

  it('matches view-switch toolbar controls to the shared outline button treatment', () => {
    const fullDocumentButton = shellSource.match(
      /<Button[\s\S]*?data-result-show-full-document="true"[\s\S]*?<\/Button>/,
    )?.[0]
    const findingsOverviewButton = shellSource.match(
      /<Button[\s\S]*?data-result-show-findings-overview="true"[\s\S]*?<\/Button>/,
    )?.[0]
    const directoryButton = shellSource.match(
      /<Button[\s\S]*?data-result-document-navigator-trigger="inline"[\s\S]*?<\/Button>/,
    )?.[0]

    expect(fullDocumentButton).toContain('variant="outline"')
    expect(fullDocumentButton).toContain('resultReviewContainerBorderClassName')
    expect(findingsOverviewButton).toContain('variant="outline"')
    expect(findingsOverviewButton).toContain('size="default"')
    expect(findingsOverviewButton).toContain('resultReviewContainerBorderClassName')
    expect(directoryButton).toContain('variant="outline"')
    expect(directoryButton).toContain('size="sm"')
    expect(directoryButton).toContain('resultReviewContainerBorderClassName')
  })

  it('uses workspace canvas layout on Result DocumentReader for aligned column tops', () => {
    expect(shellSource).toContain('canvasLayout="workspace"')
  })

  it('renders an empty Result with an expanded desktop Directory without Finding surfaces', () => {
    const html = renderLoadedShell()

    expect(html).not.toContain('data-result-document-navigator-trigger="inline"')
    expect(html).toContain('data-result-outline-inline="true"')
    expect(html).not.toContain('data-result-document-navigator-trigger-slot')
    expect(html).not.toContain('data-result-document-navigator-trigger="narrow"')
    expect(html).not.toContain('data-result-findings-trigger="true"')
    expect(html).toContain('data-source-annotation-navigator="true"')
    expect(html).toContain('data-result-document-pane="true"')
    expect(html).not.toContain('data-result-findings-panel="true"')
    expect(html).not.toContain('data-findings-open')
    expect(html).not.toContain('质控结果')
    expect(html).toContain('4. 临床安全性')
    expect(html).not.toContain('data-result-findings-inline-pane="true"')
    expect(shellSource).not.toContain('data-result-outline-temporary="true"')
    expect(shellSource).not.toContain('data-result-findings-temporary="true"')
  })

  it('renders the inline Directory by default without a narrow Sheet', () => {
    const html = renderLoadedShell()

    expect(html).not.toContain('data-result-navigation-rail="true"')
    expect(html).not.toContain('data-result-document-navigator-trigger="inline"')
    expect(html).not.toContain('data-result-document-navigator-trigger-slot')
    expect(html).not.toContain('data-result-document-navigator-trigger="narrow"')
    expect(html).toContain('data-result-outline-inline="true"')
    expect(html).not.toContain('data-result-outline-temporary="true"')
    expect(shellSource).not.toContain('data-result-outline-temporary="true"')
    expect(shellSource).not.toContain('outlineSheetOpen')
  })

  it.each([839.5, 1024])('preserves left Directory and collapse/reopen preference across views at %spx', (width) => {
    mockViewportWidth(width)
    const host = window.document.createElement('div')
    window.document.body.appendChild(host)
    const root = createRoot(host)

    act(() => root.render(findingsShellElement()))
    expect(host.querySelector('[data-result-outline-inline]')).toBeNull()
    showResultFullDocument(host)
    const documentToolbar = host.querySelector('[data-result-workspace-toolbar="true"]')
    const annotationNavigator = documentToolbar?.querySelector(
      '[data-document-annotation-toolbar="true"]',
    )
    expect(host.querySelector('[data-result-findings-panel="true"]')).toBeNull()
    expect(host.querySelector('[data-result-document-navigator-trigger-slot]')).toBeNull()
    expect(annotationNavigator).not.toBeNull()

    const html = host.innerHTML
    const outlineIndex = html.indexOf('data-result-outline-inline="true"')
    const documentIndex = html.indexOf('data-result-document-pane="true"')
    expect(outlineIndex).toBeGreaterThan(-1)
    expect(documentIndex).toBeGreaterThan(outlineIndex)

    const outline = host.querySelector('[data-result-outline-inline="true"]')
    const documentPane = host.querySelector('[data-result-document-pane="true"]')
    const collapse = outline?.querySelector<HTMLButtonElement>(
      '[data-result-document-navigator-collapse="true"]',
    )
    expect(outline?.className).toContain('min-[840px]:w-[22.5rem]')
    expect(outline?.className).toContain('min-[840px]:shrink-0')
    expect(documentPane?.className).toContain('flex-1')
    expect(documentPane?.className).toContain('min-w-0')
    expect(host.querySelector('[data-result-document-navigator-trigger-slot]')).toBeNull()
    expect(host.querySelector('[data-result-document-navigator-trigger="inline"]')).toBeNull()
    expect(host.querySelector('[data-result-workspace-utilities]')).toBeNull()
    const openDocumentToolbar = host.querySelector('[data-result-workspace-toolbar="true"]')
    expect(openDocumentToolbar?.querySelector('[data-document-annotation-toolbar="true"]'))
      .not.toBeNull()
    expect(host.querySelector('[data-result-findings-panel="true"]')).toBeNull()
    expect(collapse).not.toBeNull()
    expect(outline?.contains(collapse ?? null)).toBe(true)

    collapse?.focus()
    act(() => collapse?.click())
    expect(host.querySelector('[data-result-outline-inline="true"]')).toBeNull()
    expect(host.querySelector('[data-result-document-navigator-trigger-slot]')).toBeNull()
    const restoredTrigger = host.querySelector<HTMLButtonElement>('[data-result-document-navigator-trigger="inline"]')!
    expect(host.querySelector('[data-result-workspace-toolbar="true"]')?.contains(restoredTrigger))
      .toBe(true)
    expect(window.document.activeElement).toBe(restoredTrigger)
    expect(restoredTrigger.className).not.toContain('absolute')
    expect(restoredTrigger.className).not.toContain('translate-x-')
    expect(restoredTrigger.className).not.toMatch(/-m[lr]-/)

    act(() => host.querySelector<HTMLButtonElement>('[data-result-show-findings-overview]')!.click())
    showResultFullDocument(host)
    expect(host.querySelector('[data-result-outline-inline]')).toBeNull()
    const reopen = host.querySelector<HTMLButtonElement>('[data-result-document-navigator-trigger="inline"]')!
    reopen.focus()
    act(() => reopen.click())
    expect(host.querySelector('[data-result-outline-inline]')).not.toBeNull()
    expect(window.document.activeElement).toBe(host.querySelector('[data-result-document-navigator-collapse]'))
    expect(documentToolbar).toBe(host.querySelector('[data-result-workspace-toolbar]'))

    act(() => host.querySelector<HTMLButtonElement>('[data-result-show-findings-overview]')!.click())
    expect(host.querySelector('[data-result-outline-inline]')).toBeNull()
    showResultFullDocument(host)
    expect(host.querySelector('[data-result-outline-inline]')).not.toBeNull()
    expect(host.querySelector('[data-result-document-navigator-trigger="inline"]')).toBeNull()

    act(() => root.unmount())
    host.remove()
  })

  it.each([320, 839.5, 840, 1024])('uses one left inline Directory with responsive pane contracts at %spx', (width) => {
    mockViewportWidth(width)
    const host = window.document.createElement('div')
    window.document.body.appendChild(host)
    const root = createRoot(host)
    act(() => root.render(loadedShellElement()))
    const workspace = host.querySelector('[data-result-document-workspace]')!
    const outline = workspace.firstElementChild!
    expect(outline.getAttribute('data-result-outline-inline')).toBe('true')
    expect(workspace.lastElementChild?.getAttribute('data-result-document-column')).toBe('true')
    expect(host.querySelectorAll('[data-result-document-navigator]')).toHaveLength(1)
    expect(window.document.body.querySelector('[role="dialog"]')).toBeNull()
    expect(window.document.body.querySelector('[data-slot="sheet-content"]')).toBeNull()
    expect(window.document.body.querySelectorAll('[data-result-document-navigator]')).toHaveLength(1)
    expect(outline.classList.contains('hidden')).toBe(false)
    expect(outline.classList.contains('min-[840px]:w-[22.5rem]')).toBe(true)
    expect(outline.classList.contains('w-[22.5rem]')).toBe(false)
    const surface = workspace.querySelector('article.document-surface')!
    expect(surface.classList.contains('min-[840px]:max-w-[56rem]')).toBe(true)
    expect(surface.classList.contains('min-[840px]:sm:px-14')).toBe(true)
    expect(surface.classList.contains('mx-auto')).toBe(true)
    expect(outline.classList.contains('min-[840px]:shrink-0')).toBe(true)
    expect(outline.classList.contains('min-w-0')).toBe(true)
    expect(outline.classList.contains('border-r')).toBe(true)
    expect(workspace.classList.contains('max-[840px]:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]')).toBe(true)
    expect(workspace.classList.contains('max-[840px]:grid')).toBe(true)
    expect(workspace.classList.contains('max-[840px]:grid-rows-[minmax(0,1fr)]')).toBe(true)
    act(() => host.querySelector<HTMLButtonElement>('[data-result-document-navigator-collapse]')!.click())
    expect(workspace.children).toHaveLength(1)
    expect(workspace.classList.contains('max-[840px]:grid')).toBe(false)
    expect(workspace.firstElementChild?.classList.contains('flex-1')).toBe(true)
    const reopen = host.querySelector<HTMLButtonElement>('[data-result-document-navigator-trigger="inline"]')!
    expect(window.document.activeElement).toBe(reopen)
    act(() => reopen.click())
    expect(host.querySelectorAll('[data-result-document-navigator]')).toHaveLength(1)
    expect(window.document.activeElement).toBe(host.querySelector('[data-result-document-navigator-collapse]'))
    act(() => root.unmount())
    host.remove()
  })

  it.each([true, false])('preserves Directory preference and scroll owners across breakpoints with open=%s', (open) => {
    const resize = mockViewportWidth(1024)
    const host = window.document.createElement('div')
    const root = createRoot(host)
    act(() => root.render(loadedShellElement()))
    const outline = host.querySelector('[data-result-outline-inline]')!
    const navigator = outline.querySelector('[data-result-document-navigator]')!
    const directoryScroll = outline.querySelector<HTMLElement>('[data-slot="scroll-area-viewport"]')!
    const canvas = host.querySelector('[data-document-canvas]')!
    const documentScroll = canvas.closest<HTMLElement>('[data-slot="scroll-area-viewport"]')!
    directoryScroll.scrollTop = 30
    documentScroll.scrollTop = 75
    if (!open) act(() => host.querySelector<HTMLButtonElement>('[data-result-document-navigator-collapse]')!.click())
    for (const width of [839.5, 840, 320, 1024]) {
      resize(width)
      expect(host.querySelector('[data-document-canvas]')).toBe(canvas)
      expect(canvas.closest('[data-slot="scroll-area-viewport"]')).toBe(documentScroll)
      expect(documentScroll.scrollTop).toBe(75)
      if (open) {
        expect(host.querySelector('[data-result-outline-inline]')).toBe(outline)
        expect(outline.querySelector('[data-result-document-navigator]')).toBe(navigator)
        expect(outline.querySelector('[data-slot="scroll-area-viewport"]')).toBe(directoryScroll)
        expect(directoryScroll.scrollTop).toBe(30)
      } else {
        expect(host.querySelector('[data-result-outline-inline]')).toBeNull()
        expect(host.querySelector('[data-result-document-navigator-trigger="inline"]')).not.toBeNull()
      }
    }
    act(() => root.unmount())
  })

  it('keeps the narrow Directory open after heading selection', () => {
    mockViewportWidth(839.5)
    const selectHeading = vi.fn()
    const host = window.document.createElement('div')
    const root = createRoot(host)
    act(() => root.render(loadedShellElement({ onSelectHeading: selectHeading })))
    const outline = host.querySelector('[data-result-outline-inline]')!
    const headings = outline.querySelectorAll<HTMLButtonElement>('button')
    act(() => headings[1]!.click())
    expect(selectHeading).toHaveBeenCalledWith(outlineEntries[0], 'canonical')
    expect(host.querySelector('[data-result-outline-inline]')).toBe(outline)
    expect(host.querySelector('[data-result-document-navigator-trigger]')).toBeNull()
    act(() => root.unmount())
  })

  it('preserves Source local scroll and Queue DOM across breakpoints with Finding always visible', () => {
    const setViewportWidth = mockViewportWidth(1024)
    const host = window.document.createElement('div')
    window.document.body.appendChild(host)
    const root = createRoot(host)

    act(() => root.render(findingsShellElement()))
    const source = host.querySelector('[data-finding-source-document-panel]')!
    const localViewport = host.querySelector<HTMLElement>(
      '[data-source-evidence-viewport-scroll] [data-slot="scroll-area-viewport"]',
    )!
    const panel = host.querySelector('[data-result-findings-panel]')!
    const queue = panel.querySelector('[data-finding-queue]')!
    localViewport.scrollTop = 45
    expect(panel.getAttribute('data-result-findings-panel-open')).toBe('true')
    expect(host.querySelector('[data-result-findings-close]')).toBeNull()
    expect(host.querySelector('[data-result-findings-reopen]')).toBeNull()

    setViewportWidth(839.5)
    expect(host.querySelector('[data-finding-source-document-panel]')).toBe(source)
    expect(host.querySelector('[data-source-evidence-viewport-scroll] [data-slot="scroll-area-viewport"]')).toBe(localViewport)
    expect(localViewport.scrollTop).toBe(45)
    expect(host.querySelector('[data-result-findings-panel]')).toBe(panel)
    expect(panel.querySelector('[data-finding-queue]')).toBe(queue)
    expect(panel.getAttribute('data-result-findings-panel-open')).toBe('true')
    expect(panel.classList.contains('hidden')).toBe(false)
    expect(host.querySelectorAll('[data-result-findings-scroll]')).toHaveLength(1)

    setViewportWidth(840)
    expect(host.querySelector('[data-finding-source-document-panel]')).toBe(source)
    expect(localViewport.scrollTop).toBe(45)
    expect(panel.querySelector('[data-finding-queue]')).toBe(queue)
    expect(panel.getAttribute('data-result-findings-panel-open')).toBe('true')
    expect(panel.classList.contains('min-[840px]:hidden')).toBe(false)
    expect(host.querySelector('[data-result-findings-reopen]')).toBeNull()

    act(() => root.unmount())
    host.remove()
  })

  it('keeps loading and error states inside the parent Task composition', () => {
    expect(shellSource).toContain("resultLoadStatus === 'error'")
    expect(shellSource).toContain("resultLoadStatus === 'loading'")
    expect(shellSource).toMatch(
      /resultLoadStatus === 'error'[\s\S]*flex h-full min-h-0 items-center justify-center/,
    )
    expect(shellSource).toMatch(
      /resultLoadStatus === 'loading'[\s\S]*flex h-full min-h-0 items-center justify-center/,
    )
    expect(shellSource).not.toMatch(
      /resultLoadStatus === '(?:error|loading)'[\s\S]*flex h-svh items-center justify-center/,
    )
  })
})
