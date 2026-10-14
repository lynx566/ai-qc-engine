import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

import { describe, expect, it } from 'vitest'

import { SentenceMarkedText } from '@/components/review/sentence-marked-text'
import {
  sourceCommentBadgeClassName,
} from '@/components/review/source-comment-marker'
import { sourceCommentActiveRangeMarkClassName } from '@/lib/source-comment-renderer'
import { sourceHighlightMarkClassName } from '@/lib/source-highlight-renderer'
import type { SourceAnnotation } from '@/types/source-annotation'

const anchor = {
  slotId: 'source',
  docId: 'doc_test',
  blockId: 'C0002',
  sentenceId: 'C0002:S001',
}

function rangeComment(
  annotationId: string,
  startOffset: number,
  endOffset: number,
  content = 'note',
): SourceAnnotation {
  return {
    annotationId,
    anchor,
    kind: 'comment',
    content,
    range: { startOffset, endOffset },
    createdAt: '2026-09-13T00:00:00Z',
    updatedAt: '2026-09-13T00:00:00Z',
  }
}

const legacyComment: SourceAnnotation = {
  annotationId: 'ann_legacy',
  anchor,
  kind: 'comment',
  content: 'legacy note',
  createdAt: '2026-09-13T00:00:00Z',
  updatedAt: '2026-09-13T00:00:00Z',
}

describe('SentenceMarkedText comment rendering', () => {
  it('does not render comment badge when sentence has no comment', () => {
    const html = renderToStaticMarkup(
      createElement(SentenceMarkedText, {
        docId: 'doc_test',
        displayText: '感染性肺炎2例',
        mode: 'paragraph',
        sentences: [
          { sentenceId: 'C0002:S001', rawText: '感染性肺炎2例', normalizedText: '感染性肺炎2例' },
        ],
      }),
    )

    expect(html).not.toContain('data-source-comment-icon')
  })

  it('renders range-level comment with icon after range and no text decoration', () => {
    const comments = new Map<string, SourceAnnotation[]>([
      ['C0002:S001', [rangeComment('ann_comment', 5, 9)]],
    ])
    const html = renderToStaticMarkup(
      createElement(SentenceMarkedText, {
        docId: 'doc_test',
        displayText: '本研究中ADR发生率为70.0%，需进一步确认。',
        mode: 'paragraph',
        sentences: [
          {
            sentenceId: 'C0002:S001',
            rawText: '本研究中ADR发生率为70.0%，需进一步确认。',
            normalizedText: '本研究中ADR发生率为70.0%，需进一步确认。',
          },
        ],
        commentAnnotationsBySentenceId: comments,
      }),
    )

    const commentRangeClass = html.match(
      /data-source-comment-range="true"[^>]*class="([^"]*)"/,
    )?.[1]
    expect(commentRangeClass ?? '').toBe('')
    expect(html).not.toContain('decoration-blue-400')
    expect(html).not.toContain(sourceCommentActiveRangeMarkClassName)
    expect(html).toContain(sourceCommentBadgeClassName)
    expect(html).toContain('data-source-comment-range="true"')
    expect(html).toContain('data-source-annotation-id="ann_comment"')
    const rangeSpanIndex = html.indexOf('data-source-comment-range="true"')
    const iconIndex = html.indexOf('data-source-comment-icon')
    const commaIndex = html.indexOf('，')
    expect(rangeSpanIndex).toBeGreaterThanOrEqual(0)
    expect(iconIndex).toBeGreaterThan(rangeSpanIndex)
    expect(iconIndex).toBeLessThan(commaIndex)
  })

  it('renders two range-level comments independently in one sentence', () => {
    const comments = new Map<string, SourceAnnotation[]>([
      [
        'C0002:S001',
        [rangeComment('ann_a', 2, 7), rangeComment('ann_b', 9, 12)],
      ],
    ])
    const html = renderToStaticMarkup(
      createElement(SentenceMarkedText, {
        docId: 'doc_test',
        displayText: 'AB70.0%CD24例EF',
        mode: 'paragraph',
        sentences: [
          { sentenceId: 'C0002:S001', rawText: 'AB70.0%CD24例EF', normalizedText: 'AB70.0%CD24例EF' },
        ],
        commentAnnotationsBySentenceId: comments,
      }),
    )

    expect(html.match(/data-source-comment-icon/g)?.length).toBe(2)
    expect(html).toContain('data-source-annotation-id="ann_a"')
    expect(html).toContain('data-source-annotation-id="ann_b"')
  })

  it('keeps legacy range-less comment at sentence end before terminal punctuation', () => {
    const comments = new Map<string, SourceAnnotation[]>([['C0002:S001', [legacyComment]]])
    const html = renderToStaticMarkup(
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
        commentAnnotationsBySentenceId: comments,
      }),
    )

    expect(html).not.toContain('data-source-comment-range="true"')
    expect(html).not.toContain(sourceCommentActiveRangeMarkClassName)
    expect(html.indexOf('data-source-comment-icon')).toBeLessThan(html.lastIndexOf('。'))
  })

  it('keeps highlight and range comment compatible', () => {
    const highlights = new Map<string, SourceAnnotation[]>([
      [
        'C0002:S001',
        [
          {
            annotationId: 'ann_hl',
            anchor,
            kind: 'highlight',
            range: { startOffset: 5, endOffset: 6 },
            createdAt: '2026-09-13T00:00:00Z',
            updatedAt: '2026-09-13T00:00:00Z',
          },
        ],
      ],
    ])
    const comments = new Map<string, SourceAnnotation[]>([
      ['C0002:S001', [rangeComment('ann_comment', 1, 3)]],
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
        commentAnnotationsBySentenceId: comments,
      }),
    )

    expect(html).toContain(sourceHighlightMarkClassName)
    expect(html).toContain('data-source-comment-icon="true"')
    expect(html).not.toContain('decoration-blue-400')
  })
})
