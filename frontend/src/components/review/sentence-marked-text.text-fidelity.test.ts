// @vitest-environment happy-dom

import { createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { act } from 'react'
import { describe, expect, it } from 'vitest'

import { SentenceMarkedText } from '@/components/review/sentence-marked-text'
import { collectSentenceSourceText } from '@/lib/source-sentence-presentation'
import {
  extractSourceTextRangeFromSelection,
  SENTENCE_RANGE_ENABLED_ATTRIBUTE,
} from '@/lib/source-text-selection'
import type { SourceAnnotation } from '@/types/source-annotation'

const comment: SourceAnnotation = {
  annotationId: 'ann_comment',
  anchor: {
    slotId: 'source',
    docId: 'doc_test',
    blockId: 'C0002',
    sentenceId: 'C0002:S001',
  },
  kind: 'comment',
  content: 'note',
  createdAt: '2026-09-13T00:00:00Z',
  updatedAt: '2026-09-13T00:00:00Z',
}

function mountSentenceMarkedText() {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)

  act(() => {
    root.render(
      createElement(SentenceMarkedText, {
        docId: 'doc_test',
        displayText: '接受至少一次VT8802治疗。',
        mode: 'paragraph',
        sentences: [
          {
            sentenceId: 'C0002:S001',
            rawText: '接受至少一次VT8802治疗。',
            normalizedText: '接受至少一次VT8802治疗。',
          },
        ],
        commentAnnotationsBySentenceId: new Map([
          [
            'C0002:S001',
            [
              {
                ...comment,
                range: { startOffset: 5, endOffset: 9 },
              },
            ],
          ],
        ]),
        highlightAnnotationsBySentenceId: new Map([
          [
            'C0002:S001',
            [
              {
                annotationId: 'ann_hl',
                anchor: comment.anchor,
                kind: 'highlight',
                range: { startOffset: 0, endOffset: 2 },
                createdAt: '2026-09-13T00:00:00Z',
                updatedAt: '2026-09-13T00:00:00Z',
              },
            ],
          ],
        ]),
      }),
    )
  })

  const sentenceSpan = container.querySelector('[data-sentence-id="C0002:S001"]')
  return { container, root, sentenceSpan }
}

describe('SentenceMarkedText text fidelity with comment badge', () => {
  it('reconstructs sentence raw text from source text nodes only', () => {
    const { sentenceSpan } = mountSentenceMarkedText()
    expect(sentenceSpan).toBeInstanceOf(HTMLElement)
    expect(collectSentenceSourceText(sentenceSpan as HTMLElement)).toBe(
      '接受至少一次VT8802治疗。',
    )
  })

  it('keeps selection offsets valid with badge inside sentence span', () => {
    const { sentenceSpan } = mountSentenceMarkedText()
    expect(sentenceSpan?.getAttribute(SENTENCE_RANGE_ENABLED_ATTRIBUTE)).toBe('true')

    const textNodes: Text[] = []
    const walker = document.createTreeWalker(sentenceSpan as HTMLElement, NodeFilter.SHOW_TEXT)
    let current = walker.nextNode()
    while (current) {
      if (current.nodeType === Node.TEXT_NODE) {
        textNodes.push(current as Text)
      }
      current = walker.nextNode()
    }

    const firstTextNode = textNodes[0]
    expect(firstTextNode).toBeTruthy()

    const range = document.createRange()
    range.setStart(firstTextNode!, 0)
    range.setEnd(firstTextNode!, 2)
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)

    const extracted = extractSourceTextRangeFromSelection(selection)
    expect(extracted).toEqual({
      supported: true,
      range: { startOffset: 0, endOffset: 2 },
      sentenceId: 'C0002:S001',
    })
  })
})
