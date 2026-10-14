import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

import { describe, expect, it } from 'vitest'

import { SentenceMarkedText } from '@/components/review/sentence-marked-text'
import { sourceHighlightMarkClassName } from '@/lib/source-highlight-renderer'
import { sentenceNavigationFocusClassName } from '@/lib/sentence-navigation-focus'
import type { SourceAnnotation } from '@/types/source-annotation'

describe('SentenceMarkedText focus styling', () => {
  it('applies focus class only to the focused sentence span', () => {
    const html = renderToStaticMarkup(
      createElement(SentenceMarkedText, {
        docId: 'doc_test',
        displayText: '第一句。 第二句。',
        mode: 'paragraph',
        sentences: [
          { sentenceId: 'C0002:S001', rawText: '第一句。', normalizedText: '第一句。' },
          { sentenceId: 'C0002:S002', rawText: '第二句。', normalizedText: '第二句。' },
        ],
        focusedSentence: {
          docId: 'doc_test',
          sentenceId: 'C0002:S002',
        },
      }),
    )

    expect(html).toContain(`data-sentence-id="C0002:S001"`)
    expect(html).toContain(`data-sentence-id="C0002:S002"`)
    expect(html).toContain(sentenceNavigationFocusClassName)
    const firstSpan = html.indexOf('data-sentence-id="C0002:S001"')
    const secondSpan = html.indexOf('data-sentence-id="C0002:S002"')
    expect(html.slice(firstSpan, secondSpan)).not.toContain('#E3EEF7')
    expect(html.slice(secondSpan)).toContain('#E3EEF7')
  })

  it('does not apply focus class when docId does not match', () => {
    const html = renderToStaticMarkup(
      createElement(SentenceMarkedText, {
        docId: 'doc_test',
        displayText: '单句。',
        mode: 'whole-block',
        sentences: [
          { sentenceId: 'C0002:S001', rawText: '单句。', normalizedText: '单句。' },
        ],
        focusedSentence: {
          docId: 'doc_other',
          sentenceId: 'C0002:S001',
        },
      }),
    )

    expect(html).not.toContain('#E3EEF7')
  })

  it('applies focus to whole-block heading span', () => {
    const html = renderToStaticMarkup(
      createElement(SentenceMarkedText, {
        docId: 'doc_test',
        displayText: '1. 执行概要',
        mode: 'whole-block',
        sentences: [
          { sentenceId: 'C0010:S001', rawText: '执行概要', normalizedText: '1. 执行概要' },
        ],
        focusedSentence: {
          docId: 'doc_test',
          sentenceId: 'C0010:S001',
        },
      }),
    )

    expect(html).toContain('#E3EEF7')
    expect(html).toContain('1. 执行概要')
  })

  it('renders navigation focus together with persisted source highlight', () => {
    const highlights = new Map<string, SourceAnnotation[]>([
      [
        'C0002:S001',
        [
          {
            annotationId: 'ann_1',
            anchor: {
              slotId: 'source',
              docId: 'doc_test',
              blockId: 'C0002',
              sentenceId: 'C0002:S001',
            },
            kind: 'highlight',
            range: { startOffset: 0, endOffset: 4 },
            createdAt: '2026-09-13T00:00:00Z',
            updatedAt: '2026-09-13T00:00:00Z',
          },
        ],
      ],
    ])

    const html = renderToStaticMarkup(
      createElement(SentenceMarkedText, {
        docId: 'doc_test',
        displayText: '感染性肺炎2例',
        mode: 'paragraph',
        sentences: [
          { sentenceId: 'C0002:S001', rawText: '感染性肺炎2例', normalizedText: '感染性肺炎2例' },
        ],
        focusedSentence: {
          docId: 'doc_test',
          sentenceId: 'C0002:S001',
        },
        highlightAnnotationsBySentenceId: highlights,
      }),
    )

    expect(html).toContain(sentenceNavigationFocusClassName)
    expect(html).toContain(sourceHighlightMarkClassName)
    expect(html).toContain('data-source-annotation-id="ann_1"')
  })
})
