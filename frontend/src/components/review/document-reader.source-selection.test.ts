// @vitest-environment happy-dom

import { createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { act } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { composeDocumentBlockId } from '@/adapters/extract-document'
import { DocumentReader } from '@/components/review/document-reader'
import { extractSourceTextRangeFromSelection } from '@/lib/source-text-selection'
import type { SourceAnnotation, SourceTextRange } from '@/types/source-annotation'
import type { DocumentView } from '@/types/document-review'

const sentenceId = 'C0009:S001'
const blockId = composeDocumentBlockId('doc_test', 'C0009')
const displayText = '30 例晚期实体'

const anchor = {
  slotId: 'source',
  docId: 'doc_test',
  blockId: 'C0009',
  sentenceId,
}

const editAnnotation: SourceAnnotation = {
  annotationId: 'ann_edit',
  anchor,
  kind: 'edit',
  range: { startOffset: 6, endOffset: 8 },
  replacementText: '顶顶顶',
  createdAt: '2026-09-13T00:00:00Z',
  updatedAt: '2026-09-13T00:00:00Z',
}

const legacyCommentAnnotation: SourceAnnotation = {
  annotationId: 'ann_comment',
  anchor,
  kind: 'comment',
  content: 'note',
  createdAt: '2026-09-13T00:00:00Z',
  updatedAt: '2026-09-13T00:00:00Z',
}

function buildDocument(): DocumentView {
  return {
    docId: 'doc_test',
    fileName: 'sample.docx',
    displayName: 'sample.docx',
    blocks: [
      {
        blockId,
        sourceBlockId: 'C0009',
        kind: 'paragraph',
        docOrderIndex: 1,
        headingPath: ['Scope'],
        displayText,
        sentences: [
          {
            sentenceId,
            rawText: displayText,
            normalizedText: displayText,
          },
        ],
      },
    ],
  }
}

type MountOptions = {
  sourceAnnotations?: Map<string, SourceAnnotation>
  onSourceAnnotationActivate?: (annotationId: string) => void
}

function sourceTextNodes(sentenceSpan: HTMLElement): Text[] {
  const nodes: Text[] = []
  const walker = document.createTreeWalker(sentenceSpan, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (node.parentElement?.closest('[data-source-annotation-ui="true"]')) {
        return NodeFilter.FILTER_REJECT
      }
      return NodeFilter.FILTER_ACCEPT
    },
  })
  let current = walker.nextNode()
  while (current) {
    if (current.nodeType === Node.TEXT_NODE) {
      nodes.push(current as Text)
    }
    current = walker.nextNode()
  }
  return nodes
}

function querySelectionToolbar(container: HTMLElement): HTMLElement | null {
  return container.querySelector('[data-source-mark-action="true"]')
}

function queryEditPopover(): HTMLElement | null {
  return document.body.querySelector('[data-source-edit-popover="true"]')
}

function setBrowserSelection(range: Range) {
  const selection = window.getSelection()
  selection?.removeAllRanges()
  selection?.addRange(range)
  return selection
}

function dispatchMouseUp(target: EventTarget) {
  act(() => {
    ;(target as HTMLElement).dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
  })
}

describe('DocumentReader source selection finalization', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
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
    act(() => {
      root?.unmount()
    })
    container.remove()
    document.body.innerHTML = ''
    vi.restoreAllMocks()
  })

  function mountReader(options: MountOptions = {}) {
    root = createRoot(container)
    act(() => {
      root.render(
        createElement(DocumentReader, {
          document: buildDocument(),
          slotId: 'source',
          sourceAnnotations: options.sourceAnnotations ?? new Map([['ann_edit', editAnnotation]]),
          onCreateEdit: vi.fn(),
          onCreateComment: vi.fn(),
          onSourceAnnotationActivate: options.onSourceAnnotationActivate,
        }),
      )
    })
    return container
  }

  function getSentenceSpan(mounted: HTMLElement): HTMLElement {
    const sentenceSpan = mounted.querySelector(`[data-sentence-id="${sentenceId}"]`)
    expect(sentenceSpan).toBeInstanceOf(HTMLElement)
    return sentenceSpan as HTMLElement
  }

  function getEditSourceText(sentenceSpan: HTMLElement): Text {
    const editSourceNode = sentenceSpan.querySelector('[data-source-edit-source="true"]')
    expect(editSourceNode?.firstChild).toBeInstanceOf(Text)
    return editSourceNode!.firstChild as Text
  }

  function selectPlainToEdit(sentenceSpan: HTMLElement) {
    const nodes = sourceTextNodes(sentenceSpan)
    const editSourceText = getEditSourceText(sentenceSpan)
    const range = document.createRange()
    range.setStart(nodes[0]!, 0)
    range.setEnd(editSourceText, editSourceText.data.length)
    return setBrowserSelection(range)
  }

  function selectEditToPlain(sentenceSpan: HTMLElement) {
    const nodes = sourceTextNodes(sentenceSpan)
    const editSourceText = getEditSourceText(sentenceSpan)
    const range = document.createRange()
    range.setStart(nodes[0]!, 0)
    range.setEnd(editSourceText, editSourceText.data.length)
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)
    selection?.setBaseAndExtent(editSourceText, editSourceText.data.length, nodes[0]!, 0)
    return selection
  }

  function selectInsideEdit(
    sentenceSpan: HTMLElement,
    direction: 'forward' | 'backward',
  ): Selection | null {
    const editSourceText = getEditSourceText(sentenceSpan)
    const range = document.createRange()
    if (direction === 'forward') {
      range.setStart(editSourceText, 0)
      range.setEnd(editSourceText, editSourceText.data.length)
      return setBrowserSelection(range)
    }
    range.setStart(editSourceText, 0)
    range.setEnd(editSourceText, editSourceText.data.length)
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)
    selection?.setBaseAndExtent(editSourceText, editSourceText.data.length, editSourceText, 0)
    return selection
  }

  function selectPlain(sentenceSpan: HTMLElement, direction: 'forward' | 'backward'): Selection | null {
    const nodes = sourceTextNodes(sentenceSpan)
    const plainNode = nodes[0]!
    const range = document.createRange()
    range.setStart(plainNode, 0)
    range.setEnd(plainNode, 2)
    if (direction === 'forward') {
      return setBrowserSelection(range)
    }
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)
    selection?.setBaseAndExtent(plainNode, 2, plainNode, 0)
    return selection
  }

  function extractedRange(selection: Selection | null): SourceTextRange | null {
    const extracted = extractSourceTextRangeFromSelection(selection)
    return extracted.supported ? extracted.range : null
  }

  it('A. forward plain → edit source shows toolbar when mouseup lands on edit source', () => {
    const onSourceAnnotationActivate = vi.fn()
    const mounted = mountReader({ onSourceAnnotationActivate })
    const sentenceSpan = getSentenceSpan(mounted)
    const editSourceText = getEditSourceText(sentenceSpan)

    selectPlainToEdit(sentenceSpan)
    dispatchMouseUp(editSourceText)

    const toolbar = querySelectionToolbar(mounted)
    expect(toolbar).toBeTruthy()
    expect(toolbar?.textContent).toContain('修订')
    expect(toolbar?.textContent).toContain('批注')
    expect(queryEditPopover()).toBeNull()
    expect(onSourceAnnotationActivate).not.toHaveBeenCalled()
  })

  it('B. backward edit source → plain shows toolbar for the same interval', () => {
    const mounted = mountReader()
    const sentenceSpan = getSentenceSpan(mounted)
    const plainNode = sourceTextNodes(sentenceSpan)[0]!

    selectEditToPlain(sentenceSpan)
    dispatchMouseUp(plainNode)

    const toolbar = querySelectionToolbar(mounted)
    expect(toolbar).toBeTruthy()
    expect(toolbar?.textContent).toContain('修订')
    expect(toolbar?.textContent).toContain('批注')
  })

  it('C. forward and backward resolve to identical canonical offsets', () => {
    const mounted = mountReader()
    const sentenceSpan = getSentenceSpan(mounted)

    selectPlainToEdit(sentenceSpan)
    const forwardRange = extractedRange(window.getSelection())

    selectEditToPlain(sentenceSpan)
    const backwardRange = extractedRange(window.getSelection())

    expect(forwardRange).toEqual({ startOffset: 0, endOffset: 8 })
    expect(backwardRange).toEqual(forwardRange)
  })

  it('D. inside edit forward drag shows toolbar', () => {
    const mounted = mountReader()
    const sentenceSpan = getSentenceSpan(mounted)
    const editSourceText = getEditSourceText(sentenceSpan)

    selectInsideEdit(sentenceSpan, 'forward')
    dispatchMouseUp(editSourceText)

    expect(querySelectionToolbar(mounted)).toBeTruthy()
    expect(queryEditPopover()).toBeNull()
  })

  it('E. inside edit backward drag shows toolbar with same canonical range', () => {
    const mounted = mountReader()
    const sentenceSpan = getSentenceSpan(mounted)
    const editSourceText = getEditSourceText(sentenceSpan)

    selectInsideEdit(sentenceSpan, 'backward')
    const range = extractedRange(window.getSelection())
    dispatchMouseUp(editSourceText)

    expect(range).toEqual({ startOffset: 6, endOffset: 8 })
    expect(querySelectionToolbar(mounted)).toBeTruthy()
  })

  it('F. plain forward and backward share eligibility', () => {
    const mounted = mountReader()
    const sentenceSpan = getSentenceSpan(mounted)
    const plainNode = sourceTextNodes(sentenceSpan)[0]!

    selectPlain(sentenceSpan, 'forward')
    const forwardRange = extractedRange(window.getSelection())
    dispatchMouseUp(plainNode)
    expect(querySelectionToolbar(mounted)).toBeTruthy()

    act(() => {
      root.unmount()
    })
    mountReader()

    const sentenceSpan2 = getSentenceSpan(container)
    selectPlain(sentenceSpan2, 'backward')
    const backwardRange = extractedRange(window.getSelection())
    const plainNodeAfterRemount = sourceTextNodes(sentenceSpan2)[0]!
    dispatchMouseUp(plainNodeAfterRemount)

    expect(backwardRange).toEqual(forwardRange)
    expect(querySelectionToolbar(container)).toBeTruthy()
  })

  it('collapsed click on edit source opens revision popover without selection toolbar', () => {
    const onSourceAnnotationActivate = vi.fn()
    const mounted = mountReader({ onSourceAnnotationActivate })
    const editGroup = mounted.querySelector('[data-source-edit-group="true"]')
    expect(editGroup).toBeTruthy()

    window.getSelection()?.removeAllRanges()

    act(() => {
      editGroup!.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
    })

    expect(onSourceAnnotationActivate).toHaveBeenCalledWith('ann_edit')
    expect(queryEditPopover()).toBeTruthy()
    expect(querySelectionToolbar(mounted)).toBeNull()
  })

  it('comment icon click keeps existing behavior without stale selection toolbar', () => {
    const mounted = mountReader({
      sourceAnnotations: new Map([
        ['ann_edit', editAnnotation],
        ['ann_comment', legacyCommentAnnotation],
      ]),
    })
    const sentenceSpan = getSentenceSpan(mounted)
    selectPlainToEdit(sentenceSpan)

    const commentIcon = mounted.querySelector('[data-source-comment-icon="true"]')
    expect(commentIcon).toBeTruthy()

    act(() => {
      commentIcon!.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
    })

    expect(querySelectionToolbar(mounted)).toBeNull()
  })

  it('replacement-only non-collapsed selection does not create toolbar', () => {
    const mounted = mountReader()
    const sentenceSpan = getSentenceSpan(mounted)
    const replacementNode = sentenceSpan.querySelector('[data-source-annotation-ui="true"]')
    expect(replacementNode).toBeTruthy()

    const range = document.createRange()
    range.selectNodeContents(replacementNode!)
    setBrowserSelection(range)

    dispatchMouseUp(replacementNode!)

    expect(extractSourceTextRangeFromSelection(window.getSelection()).supported).toBe(false)
    expect(querySelectionToolbar(mounted)).toBeNull()
  })

  it('invalid stale non-collapsed selection on replacement click does not create toolbar', () => {
    const mounted = mountReader()
    const sentenceSpan = getSentenceSpan(mounted)
    const replacementNode = sentenceSpan.querySelector('[data-source-annotation-ui="true"]')
    expect(replacementNode).toBeTruthy()

    const range = document.createRange()
    range.selectNodeContents(replacementNode!)
    setBrowserSelection(range)

    act(() => {
      replacementNode!.parentElement!.dispatchEvent(
        new MouseEvent('mouseup', { bubbles: true }),
      )
    })

    expect(querySelectionToolbar(mounted)).toBeNull()
    expect(queryEditPopover()).toBeNull()
  })
})
