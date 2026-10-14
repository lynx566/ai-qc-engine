import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

import { describe, expect, it } from 'vitest'

import { SentenceMarkedText } from '@/components/review/sentence-marked-text'
import { sourceHighlightMarkClassName } from '@/lib/source-highlight-renderer'
import type { SourceAnnotation } from '@/types/source-annotation'

describe('SentenceMarkedText highlight rendering', () => {
  it('renders persisted highlight mark inside sentence span', () => {
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
            range: { startOffset: 0, endOffset: 5 },
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
        highlightAnnotationsBySentenceId: highlights,
      }),
    )

    expect(html).toContain('data-source-annotation-id="ann_1"')
    expect(html).toContain('data-source-persisted-mark="true"')
    expect(html).toContain(sourceHighlightMarkClassName)
    expect(html).toContain('感染性肺炎')
    expect(html).not.toContain('标红')
  })

  it('does not render annotations without highlight kind', () => {
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
        highlightAnnotationsBySentenceId: highlights,
      }),
    )

    expect(html).not.toContain('data-source-annotation-id')
  })
})
