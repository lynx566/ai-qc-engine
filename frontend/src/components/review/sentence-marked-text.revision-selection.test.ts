// @vitest-environment happy-dom

import { createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { act } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { SentenceMarkedText } from '@/components/review/sentence-marked-text'
import { extractSourceTextRangeFromSelection } from '@/lib/source-text-selection'
import type { SourceAnnotation } from '@/types/source-annotation'

const anchor = {
  slotId: 'source',
  docId: 'doc_test',
  blockId: 'C0002',
  sentenceId: 'C0002:S001',
}

const editAnnotation: SourceAnnotation = {
  annotationId: 'ann_edit',
  anchor,
  kind: 'edit',
  range: { startOffset: 6, endOffset: 11 },
  replacementText: '80.0%',
  createdAt: '2026-09-13T00:00:00Z',
  updatedAt: '2026-09-13T00:00:00Z',
}

function mountSentence(onEditInlineClick = vi.fn()) {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)

  act(() => {
    root.render(
      createElement(SentenceMarkedText, {
        docId: 'doc_test',
        displayText: 'ADR发生率为70.0%。',
        mode: 'paragraph',
        sentences: [
          {
            sentenceId: 'C0002:S001',
            rawText: 'ADR发生率为70.0%。',
            normalizedText: 'ADR发生率为70.0%。',
          },
        ],
        editAnnotationsBySentenceId: new Map([['C0002:S001', [editAnnotation]]]),
        onEditInlineClick,
      }),
    )
  })

  return { container, root, onEditInlineClick }
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

describe('revision source selection interaction', () => {
  it('allows drag-select on revised source without opening revision popover', () => {
    const onEditInlineClick = vi.fn()
    const { container } = mountSentence(onEditInlineClick)
    const sentenceSpan = container.querySelector('[data-sentence-id="C0002:S001"]')
    expect(sentenceSpan).toBeInstanceOf(HTMLElement)

    const editSourceNode = (sentenceSpan as HTMLElement).querySelector(
      '[data-source-edit-source="true"]',
    )
    expect(editSourceNode).toBeTruthy()
    const editSourceText = editSourceNode?.firstChild
    expect(editSourceText).toBeInstanceOf(Text)

    const range = document.createRange()
    range.setStart(editSourceText!, 0)
    range.setEnd(editSourceText!, (editSourceText as Text).data.length)
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)

    act(() => {
      editSourceNode!.parentElement!.dispatchEvent(
        new MouseEvent('mouseup', { bubbles: true }),
      )
    })

    expect(onEditInlineClick).not.toHaveBeenCalled()
    expect(extractSourceTextRangeFromSelection(selection)).toEqual({
      supported: true,
      range: { startOffset: 6, endOffset: 11 },
      sentenceId: 'C0002:S001',
    })
  })

  it('opens revision popover on plain click with collapsed selection', () => {
    const onEditInlineClick = vi.fn()
    const { container } = mountSentence(onEditInlineClick)
    const editGroup = container.querySelector('[data-source-edit-group="true"]')
    expect(editGroup).toBeTruthy()

    window.getSelection()?.removeAllRanges()

    act(() => {
      editGroup!.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
    })

    expect(onEditInlineClick).toHaveBeenCalledTimes(1)
    expect(onEditInlineClick.mock.calls[0]?.[0]).toBe('ann_edit')
  })

  it('excludes replacement text from source range extraction', () => {
    mountSentence()
    const sentenceSpan = document.querySelector('[data-sentence-id="C0002:S001"]')
    const replacementNode = (sentenceSpan as HTMLElement).querySelector(
      '[data-source-annotation-ui="true"]',
    )
    expect(replacementNode).toBeTruthy()

    const range = document.createRange()
    range.selectNodeContents(replacementNode!)
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)

    expect(extractSourceTextRangeFromSelection(selection)).toEqual({
      supported: false,
      reason: 'invalid-offset',
    })
  })

  it('supports selecting from plain source into revised source', () => {
    const { container } = mountSentence()
    const sentenceSpan = container.querySelector('[data-sentence-id="C0002:S001"]') as HTMLElement
    const nodes = sourceTextNodes(sentenceSpan)
    expect(nodes.length).toBeGreaterThan(1)

    const range = document.createRange()
    range.setStart(nodes[0]!, 0)
    range.setEnd(nodes[nodes.length - 1]!, nodes[nodes.length - 1]!.data.length)
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)

    const extracted = extractSourceTextRangeFromSelection(selection)
    expect(extracted.supported).toBe(true)
    if (extracted.supported) {
      expect(extracted.range.startOffset).toBe(0)
      expect(extracted.range.endOffset).toBeGreaterThan(6)
    }
  })
})
