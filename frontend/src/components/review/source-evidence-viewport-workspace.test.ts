// @vitest-environment happy-dom

import { act, createElement } from 'react'
import { vi } from 'vitest'

vi.mock('@/lib/source-evidence-viewport-evidence-visibility', async (importOriginal) => {
  const actual = await importOriginal<
    typeof import('@/lib/source-evidence-viewport-evidence-visibility')
  >()
  return {
    ...actual,
    shouldShowReturnToEvidenceAnchor: vi.fn(actual.shouldShowReturnToEvidenceAnchor),
  }
})
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import {
  SourceEvidenceViewportWorkspace,
} from '@/components/review/source-evidence-viewport-workspace'
import { shouldShowReturnToEvidenceAnchor } from '@/lib/source-evidence-viewport-evidence-visibility'
import { deriveSourceEvidenceViewportDescriptors, type SourceEvidenceViewportDescriptor } from '@/lib/source-evidence-viewport'
import {
  computeTargetViewportBodyHeightPx,
  measureCanonicalBodyLineHeightPx,
  sourceEvidenceViewportScrollAreaClassName,
} from '@/lib/source-evidence-viewport-presentation'
import type { DocumentBlock, DocumentView } from '@/types/document-review'
import type { SourceAnnotation } from '@/types/source-annotation'

function block(
  sourceBlockId: string,
  kind: DocumentBlock['kind'],
  docOrderIndex: number,
  sentences: string[],
  headingLevel?: DocumentBlock['headingLevel'],
): DocumentBlock {
  return {
    blockId: `doc-a:${sourceBlockId}`,
    sourceBlockId,
    kind,
    docOrderIndex,
    headingLevel,
    headingPath: ['Section one'],
    displayText: sentences.join(' '),
    sentences: sentences.map((text, index) => ({
      sentenceId: `${sourceBlockId}:S${index + 1}`,
      rawText: text,
      normalizedText: text,
    })),
  }
}

const documentView: DocumentView = {
  docId: 'doc-a',
  fileName: 'doc-a.docx',
  displayName: 'Document A',
  blocks: [
    block('H1', 'heading', 0, ['Section one'], 1),
    block('P1', 'paragraph', 1, ['Alpha.', 'Beta.', 'Gamma.']),
    block('P2', 'paragraph', 2, ['After evidence.']),
    block('H2', 'heading', 3, ['Next section'], 1),
  ],
}

function descriptor(
  viewportKey: string,
  evidenceSentenceId: string,
  sourceBlockId = 'P1',
): SourceEvidenceViewportDescriptor {
  return {
    viewportKey,
    slotId: 'source',
    documentId: 'doc-a',
    evidenceLocationKey: `${sourceBlockId}:${evidenceSentenceId}`,
    sourceBlockId,
    sourceBlockIndex: sourceBlockId === 'P1' ? 1 : 2,
    evidenceSentenceId,
    evidenceSentenceIndex: Number(evidenceSentenceId.at(-1)) - 1,
    sectionHeadingSourceBlockId: 'H1',
    sectionStartBlockIndex: 0,
    sectionEndBlockIndexExclusive: 3,
  }
}

describe('SourceEvidenceViewportWorkspace', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
    vi.restoreAllMocks()
  })

  async function render(
    descriptors: SourceEvidenceViewportDescriptor[],
    props: Record<string, unknown> = {},
  ) {
    await act(async () => {
      root.render(createElement(SourceEvidenceViewportWorkspace, {
        document: documentView,
        descriptors,
        ...props,
      }))
      await Promise.resolve()
      await Promise.resolve()
    })
  }

  function highlight(sentenceId = 'P1:S1'): SourceAnnotation {
    return {
      annotationId: `highlight-${sentenceId}`,
      kind: 'highlight',
      anchor: { slotId: 'source', docId: 'doc-a', blockId: sentenceId.split(':')[0]!, sentenceId },
      range: { startOffset: 0, endOffset: 5 },
      createdAt: '2026-01-01T00:00:00Z',
      updatedAt: '2026-01-01T00:00:00Z',
    }
  }

  it('renders one ordered viewport for each evidence occurrence', async () => {
    const descriptors = Array.from({ length: 8 }, (_, index) =>
      descriptor(`viewport-${index + 1}`, `P1:S${(index % 3) + 1}`),
    )

    await render(descriptors)

    const viewports = [...container.querySelectorAll<HTMLElement>('[data-source-evidence-viewport]')]
    expect(viewports).toHaveLength(8)
    expect(viewports.map((viewport) => viewport.dataset.viewportKey)).toEqual(
      descriptors.map((item) => item.viewportKey),
    )
  })

  it('renders projected source order with separate same-section cards and unchanged anchor context', async () => {
    const refs = ['P2:S1', 'P1:S3', 'P1:S1'].map((sentenceId, index) => ({
      slotId: 'source', docId: 'doc-a', blockId: sentenceId.split(':')[0]!,
      sentenceId, sentenceAlias: `T${index + 1}`,
    }))
    const project = (evidenceLocations: typeof refs) => deriveSourceEvidenceViewportDescriptors({
      findingId: 'finding-a', slotId: 'source', document: documentView, evidenceLocations,
    })
    const descriptors = project(refs)
    const annotation = highlight()
    const props = { sourceAnnotations: new Map([[annotation.annotationId, annotation]]) }
    await render(descriptors, props)

    const viewports = [...container.querySelectorAll<HTMLElement>('[data-source-evidence-viewport]')]
    expect(viewports).toHaveLength(3)
    expect(viewports.map((viewport) =>
      viewport.querySelector('[data-focused-finding-target="true"]')?.getAttribute('data-sentence-id'),
    )).toEqual(['P1:S1', 'P1:S3', 'P2:S1'])
    for (const viewport of viewports) {
      expect(viewport.querySelector('[data-source-evidence-viewport-chrome="true"]')?.textContent)
        .toContain('Section one')
      expect([...viewport.querySelectorAll('[data-sentence-id]')].map((node) => node.getAttribute('data-sentence-id')))
        .toEqual(['P1:S1', 'P1:S2', 'P1:S3', 'P2:S1'])
      expect(viewport.querySelectorAll('[data-focused-finding-target="true"]')).toHaveLength(1)
      expect(viewport.querySelectorAll('[data-source-persisted-mark="true"]')).toHaveLength(1)
      expect(viewport.textContent).not.toContain('Next section')
    }

    await render(project([refs[2]!, refs[1]!, refs[0]!]), props)
    expect([...container.querySelectorAll('[data-source-evidence-viewport]')]).toEqual(viewports)
  })

  it('keeps same-section occurrences complete, separately focused, and DOM-id unique', async () => {
    await render([
      descriptor('viewport-a', 'P1:S1'),
      descriptor('viewport-b', 'P1:S3'),
    ])

    const instances = [...container.querySelectorAll<HTMLElement>('[data-source-evidence-viewport]')]
    expect(instances).toHaveLength(2)
    for (const instance of instances) {
      expect(instance.textContent).toContain('Section one')
      expect(instance.textContent).toContain('Alpha.')
      expect(instance.textContent).toContain('After evidence.')
      expect(instance.textContent).not.toContain('Next section')
      expect(instance.querySelectorAll('[data-block-id]')).toHaveLength(2)
      expect(instance.querySelectorAll('[data-focused-finding-target="true"]')).toHaveLength(1)
    }
    expect(instances[0]!.querySelector('[data-focused-finding-target="true"]')?.getAttribute('data-sentence-id')).toBe('P1:S1')
    expect(instances[1]!.querySelector('[data-focused-finding-target="true"]')?.getAttribute('data-sentence-id')).toBe('P1:S3')

    const ids = [...container.querySelectorAll<HTMLElement>('[id]')].map((element) => element.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('positions each viewport locally once and reinitializes only for a new key', async () => {
    const originalGetComputedStyle = window.getComputedStyle.bind(window)
    vi.spyOn(window, 'getComputedStyle').mockImplementation((element, pseudo) => {
      if (
        element instanceof HTMLElement &&
        element.matches('[data-source-canonical-body="true"]')
      ) {
        return { lineHeight: '20px', fontSize: '14px' } as CSSStyleDeclaration
      }
      return originalGetComputedStyle(element, pseudo)
    })
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function () {
      if (this.getAttribute('data-slot') === 'scroll-area-viewport') {
        return { top: 100, bottom: 200, left: 0, right: 400, width: 400, height: 100, x: 0, y: 100, toJSON: () => ({}) }
      }
      const sentenceId = this.getAttribute('data-sentence-id')
      const top = sentenceId === 'P1:S1' ? 360 : sentenceId === 'P1:S3' ? 520 : 100
      return { top, bottom: top + 20, left: 0, right: 100, width: 20, x: 0, y: top, toJSON: () => ({}) }
    })
    vi.spyOn(HTMLElement.prototype, 'scrollHeight', 'get').mockImplementation(function () {
      if (this.getAttribute('data-slot') === 'scroll-area-viewport') {
        return 2000
      }
      return 0
    })

    const first = descriptor('viewport-a', 'P1:S1')
    const second = descriptor('viewport-b', 'P1:S3')
    await render([first, second])

    const scrollViewports = [...container.querySelectorAll<HTMLElement>('[data-slot="scroll-area-viewport"]')]
    expect(scrollViewports.map((viewport) => viewport.scrollTop)).toEqual([220, 380])

    scrollViewports[0]!.scrollTop = 42
    await render([{ ...first }, { ...second }])
    expect(scrollViewports.map((viewport) => viewport.scrollTop)).toEqual([42, 380])

    await render([{ ...first, viewportKey: 'viewport-a-new' }, second])
    const nextScrollViewports = [...container.querySelectorAll<HTMLElement>('[data-slot="scroll-area-viewport"]')]
    expect(nextScrollViewports.map((viewport) => viewport.scrollTop)).toEqual([220, 380])
  })

  it('uses compact viewport chrome without repeating document label or section heading', async () => {
    await render([descriptor('viewport-a', 'P1:S2')])

    const viewport = container.querySelector<HTMLElement>('[data-source-evidence-viewport]')!
    expect(viewport.textContent).not.toContain('Document A')
    expect(viewport.querySelector('[data-source-evidence-viewport-chrome="true"]')).not.toBeNull()
    const scrollRoot = viewport.querySelector('[data-source-evidence-viewport-scroll="true"]')
    expect(scrollRoot?.className).toContain('min-h-0')
    expect(scrollRoot?.getAttribute('data-source-evidence-viewport-readable-sizing')).toBe('true')
    expect(sourceEvidenceViewportScrollAreaClassName).not.toContain('h-36')
    expect(viewport.querySelectorAll('[data-block-id="H1"]')).toHaveLength(0)
    expect(viewport.querySelector('[data-source-evidence-viewport-chrome="true"]')?.textContent)
      .toContain('Section one')
    expect(
      [...viewport.querySelectorAll<HTMLElement>('[data-sentence-id]')]
        .filter((node) => node.textContent?.includes('Section one')),
    ).toHaveLength(0)
  })

  it('sizes viewport body from evidence rendered height plus four body line-heights', async () => {
    await render([descriptor('viewport-a', 'P1:S2')])
    const scrollViewport = container.querySelector<HTMLElement>('[data-slot="scroll-area-viewport"]')!
    const evidence = container.querySelector<HTMLElement>('[data-focused-finding-target="true"]')!
    const body = container.querySelector<HTMLElement>('[data-source-canonical-body="true"]')!
    const lineHeight = measureCanonicalBodyLineHeightPx(body)
    const evidenceHeight = evidence.getBoundingClientRect().height
    const expectedBodyHeight = computeTargetViewportBodyHeightPx(
      evidenceHeight,
      lineHeight,
    )
    expect(Number(scrollViewport.dataset.sourceEvidenceViewportBodyHeightPx))
      .toBeCloseTo(expectedBodyHeight, 0)
    expect(scrollViewport.parentElement?.getAttribute('style')).toContain('height')
  })

  it('keeps two evidence occurrences in the same paragraph as independent viewports', async () => {
    await render([
      descriptor('viewport-a', 'P1:S1'),
      descriptor('viewport-b', 'P1:S2'),
    ])
    const viewports = [...container.querySelectorAll('[data-source-evidence-viewport="true"]')]
    expect(viewports).toHaveLength(2)
    expect(container.querySelectorAll('[data-focused-finding-target="true"]')).toHaveLength(2)
  })

  it('does not truncate evidence sentences in the readable viewport', async () => {
    await render([descriptor('viewport-a', 'P1:S2')])
    const evidence = container.querySelector<HTMLElement>('[data-focused-finding-target="true"]')!
    expect(evidence.className).not.toMatch(/line-clamp|truncate|ellipsis/)
    expect(evidence.textContent).toContain('Beta.')
  })

  it('uses one interaction owner and synchronizes source annotations across duplicate instances', async () => {
    const annotation = highlight()
    await render([
      descriptor('viewport-a', 'P1:S1'),
      descriptor('viewport-b', 'P1:S1'),
    ], {
      sourceAnnotations: new Map([[annotation.annotationId, annotation]]),
    })

    expect(container.querySelectorAll('[data-source-document-interaction="true"]')).toHaveLength(1)
    expect(container.querySelectorAll('[data-source-persisted-mark="true"]')).toHaveLength(2)
  })

  it('rejects a selection spanning two viewport instances', async () => {
    await render([
      descriptor('viewport-a', 'P1:S1'),
      descriptor('viewport-b', 'P1:S1'),
    ])
    const sentences = container.querySelectorAll<HTMLElement>('[data-sentence-id="P1:S1"]')
    const range = document.createRange()
    range.setStart(sentences[0]!.firstChild as Text, 0)
    range.setEnd(sentences[1]!.firstChild as Text, 5)
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)

    act(() => {
      container.querySelector('[data-source-document-interaction="true"]')
        ?.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
    })

    expect(container.textContent).not.toContain('修订')
    expect(container.textContent).not.toContain('批注')
  })

  it('evaluates active annotation visibility across the committed viewport set', async () => {
    const onClearActiveSourceAnnotation = vi.fn()
    const annotation = highlight('H2:S1')
    const firstSection = descriptor('viewport-a', 'P1:S1')
    const secondSection: SourceEvidenceViewportDescriptor = {
      ...descriptor('viewport-b', 'H2:S1', 'H2'),
      sourceBlockIndex: 3,
      evidenceSentenceIndex: 0,
      sectionHeadingSourceBlockId: 'H2',
      sectionStartBlockIndex: 3,
      sectionEndBlockIndexExclusive: 4,
    }
    const props = {
      sourceAnnotations: new Map([[annotation.annotationId, annotation]]),
      activeSourceAnnotationId: annotation.annotationId,
      onClearActiveSourceAnnotation,
    }

    await render([firstSection, secondSection], props)
    expect(onClearActiveSourceAnnotation).not.toHaveBeenCalled()

    await render([secondSection], props)
    expect(onClearActiveSourceAnnotation).not.toHaveBeenCalled()

    await render([firstSection], props)
    expect(onClearActiveSourceAnnotation).toHaveBeenCalledTimes(1)
  })

  it('shows return-to-anchor only after scrolling evidence out of the local viewport', async () => {
    vi.mocked(shouldShowReturnToEvidenceAnchor).mockImplementation(
      (viewport) => viewport.scrollTop > 80,
    )

    await render([descriptor('viewport-a', 'P1:S2')])
    const scrollViewport = container.querySelector<HTMLElement>('[data-slot="scroll-area-viewport"]')!
    expect(container.querySelector('[data-source-evidence-return-to-anchor="true"]')).toBeNull()
    scrollViewport.scrollTop = 120
    await act(async () => {
      scrollViewport.dispatchEvent(new Event('scroll'))
      await Promise.resolve()
    })
    expect(shouldShowReturnToEvidenceAnchor).toHaveBeenCalled()
    const returnButton = container.querySelector<HTMLElement>(
      '[data-source-evidence-return-to-anchor="true"]',
    )
    expect(returnButton).not.toBeNull()
    expect(returnButton?.closest('[data-source-evidence-viewport-chrome="true"]')).not.toBeNull()
    expect(returnButton?.getAttribute('aria-label')).toBe('回到原句')
    expect(returnButton?.textContent).not.toContain('回到原句')
    expect(container.querySelector('.absolute.right-2.top-2')).toBeNull()
  })

  it('returns only the current viewport to its readable evidence anchor', async () => {
    vi.mocked(shouldShowReturnToEvidenceAnchor).mockImplementation(
      (viewport) => viewport.scrollTop > 80,
    )

    await render([
      descriptor('viewport-a', 'P1:S1'),
      descriptor('viewport-b', 'P1:S3'),
    ])
    const scrollViewports = [...container.querySelectorAll<HTMLElement>('[data-slot="scroll-area-viewport"]')]
    scrollViewports[0]!.scrollTop = 500
    scrollViewports[1]!.scrollTop = 88
    await act(async () => {
      scrollViewports[0]!.dispatchEvent(new Event('scroll'))
      await Promise.resolve()
    })
    const returnButton = container.querySelector<HTMLElement>(
      '[data-source-evidence-return-to-anchor="true"]',
    )
    expect(returnButton).not.toBeNull()
    act(() => returnButton?.click())
    expect(scrollViewports[0]!.scrollTop).toBeLessThan(500)
    expect(scrollViewports[1]!.scrollTop).toBe(88)
  })

  it('preserves user scroll when annotation state rerenders stable viewport keys', async () => {
    const viewportDescriptor = descriptor('viewport-a', 'P1:S1')
    await render([viewportDescriptor])
    const scrollViewport = container.querySelector<HTMLElement>('[data-slot="scroll-area-viewport"]')!
    scrollViewport.scrollTop = 91
    const annotation = highlight()

    await render([{ ...viewportDescriptor }], {
      sourceAnnotations: new Map([[annotation.annotationId, annotation]]),
    })

    expect(scrollViewport.scrollTop).toBe(91)
  })
})
