import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

import { describe, expect, it } from 'vitest'

import { SentenceMarkedText } from '@/components/review/sentence-marked-text'
import {
  sourceHighlightActiveMarkClassName,
  sourceHighlightMarkClassName,
} from '@/lib/source-highlight-renderer'
import { sourceCommentActiveRangeMarkClassName } from '@/lib/source-comment-renderer'
import type { SourceAnnotation } from '@/types/source-annotation'

function highlight(
  annotationId: string,
  startOffset: number,
  endOffset: number,
): SourceAnnotation {
  return {
    annotationId,
    anchor: {
      slotId: 'source',
      docId: 'doc_test',
      blockId: 'C0002',
      sentenceId: 'C0002:S001',
    },
    kind: 'highlight',
    range: { startOffset, endOffset },
    createdAt: '2026-09-13T00:00:00Z',
    updatedAt: '2026-09-13T00:00:00Z',
  }
}

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

function renderSentence(props: {
  displayText: string
  highlights?: SourceAnnotation[]
  activeSourceAnnotationId?: string | null
  comment?: SourceAnnotation
}) {
  const highlights = new Map<string, SourceAnnotation[]>([
    ['C0002:S001', props.highlights ?? []],
  ])
  const comments = props.comment
    ? new Map<string, SourceAnnotation[]>([['C0002:S001', [props.comment]]])
    : undefined

  return renderToStaticMarkup(
    createElement(SentenceMarkedText, {
      docId: 'doc_test',
      displayText: props.displayText,
      mode: 'paragraph',
      sentences: [
        {
          sentenceId: 'C0002:S001',
          rawText: props.displayText,
          normalizedText: props.displayText,
        },
      ],
      highlightAnnotationsBySentenceId: highlights,
      commentAnnotationsBySentenceId: comments,
      activeSourceAnnotationId: props.activeSourceAnnotationId ?? null,
    }),
  )
}

describe('SentenceMarkedText active annotation emphasis', () => {
  it('renders non-active marks as red text only', () => {
    const html = renderSentence({
      displayText: 'ABC',
      highlights: [highlight('ann_a', 0, 1), highlight('ann_b', 1, 2)],
    })

    expect(html).toContain(sourceHighlightMarkClassName)
    expect(html).not.toContain(sourceHighlightActiveMarkClassName)
    expect(html).not.toContain('bg-rose-100/60')
  })

  it('adds light rose background only to the active mark', () => {
    const html = renderSentence({
      displayText: 'ABC',
      highlights: [highlight('ann_a', 0, 1), highlight('ann_b', 1, 2)],
      activeSourceAnnotationId: 'ann_b',
    })

    const annASpan = html.indexOf('data-source-annotation-id="ann_a"')
    const annBSpan = html.indexOf('data-source-annotation-id="ann_b"')
    expect(annASpan).toBeGreaterThanOrEqual(0)
    expect(annBSpan).toBeGreaterThan(annASpan)
    expect(html.slice(annASpan, annBSpan)).not.toContain('bg-rose-100/60')
    expect(html.slice(annBSpan)).toContain('bg-rose-100/60')
    expect(html.slice(annBSpan)).toContain('text-rose-700')
  })

  it('moves active mark background when active id changes', () => {
    const htmlA = renderSentence({
      displayText: 'ABC',
      highlights: [highlight('ann_a', 0, 1), highlight('ann_b', 1, 2)],
      activeSourceAnnotationId: 'ann_a',
    })
    const htmlB = renderSentence({
      displayText: 'ABC',
      highlights: [highlight('ann_a', 0, 1), highlight('ann_b', 1, 2)],
      activeSourceAnnotationId: 'ann_b',
    })

    const annAInA = htmlA.indexOf('data-source-annotation-id="ann_a"')
    const annBInA = htmlA.indexOf('data-source-annotation-id="ann_b"')
    expect(htmlA.slice(annAInA, annBInA)).toContain('bg-rose-100/60')
    expect(htmlA.slice(annBInA)).not.toContain('bg-rose-100/60')

    const annAInB = htmlB.indexOf('data-source-annotation-id="ann_a"')
    const annBInB = htmlB.indexOf('data-source-annotation-id="ann_b"')
    expect(htmlB.slice(annAInB, annBInB)).not.toContain('bg-rose-100/60')
    expect(htmlB.slice(annBInB)).toContain('bg-rose-100/60')
  })

  it('does not add sentence-wide annotation emphasis', () => {
    const html = renderSentence({
      displayText: 'ABC。',
      highlights: [highlight('ann_a', 0, 1)],
      activeSourceAnnotationId: 'ann_a',
    })

    expect(html).not.toContain('bg-sky-100')
    const sentenceSpan = html.match(/data-sentence-id="C0002:S001"[^>]*class="([^"]*)"/)
    expect(sentenceSpan?.[1] ?? '').toBe('')
  })

  it('emphasizes only the active comment icon in a mixed sentence', () => {
    const rangeLevelComment: SourceAnnotation = {
      ...comment,
      range: { startOffset: 1, endOffset: 2 },
    }
    const htmlInactive = renderSentence({
      displayText: 'AB。',
      highlights: [highlight('ann_a', 0, 1)],
      comment: rangeLevelComment,
      activeSourceAnnotationId: 'ann_a',
    })
    const htmlActiveComment = renderSentence({
      displayText: 'AB。',
      highlights: [highlight('ann_a', 0, 1)],
      comment: rangeLevelComment,
      activeSourceAnnotationId: 'ann_comment',
    })

    expect(htmlInactive).toContain('bg-rose-100/60')
    const inactiveCommentRange = htmlInactive.match(
      /data-source-comment-range="true"[^>]*class="([^"]*)"/,
    )?.[1]
    expect(inactiveCommentRange ?? '').toBe('')
    expect(inactiveCommentRange ?? '').not.toContain('underline')
    expect(inactiveCommentRange ?? '').not.toContain('bg-blue-100')
    expect(htmlInactive.match(/data-source-comment-icon="true"[^>]*class="([^"]*)"/)?.[1]).not.toContain(
      'bg-blue-100',
    )

    const commentButton = htmlActiveComment.match(
      /data-source-comment-icon="true"[^>]*class="([^"]*)"/,
    )?.[1]
    expect(commentButton).toContain('bg-blue-100')
    const activeCommentRange = htmlActiveComment.match(
      /data-source-comment-range="true"[^>]*class="([^"]*)"/,
    )?.[1]
    expect(activeCommentRange).toContain(sourceCommentActiveRangeMarkClassName)
    expect(activeCommentRange).not.toContain('underline')
    expect(activeCommentRange).not.toContain('decoration-blue-400')
    expect(htmlActiveComment).not.toContain('bg-rose-100/60')
  })

  it('moves active comment range background when navigating A to B', () => {
    const rangeLevelCommentA: SourceAnnotation = {
      ...comment,
      annotationId: 'ann_a',
      range: { startOffset: 0, endOffset: 1 },
    }
    const rangeLevelCommentB: SourceAnnotation = {
      ...comment,
      annotationId: 'ann_b',
      range: { startOffset: 1, endOffset: 2 },
    }

    const renderWithActive = (activeId: string) =>
      renderToStaticMarkup(
        createElement(SentenceMarkedText, {
          docId: 'doc_test',
          displayText: 'AB',
          mode: 'paragraph',
          sentences: [
            {
              sentenceId: 'C0002:S001',
              rawText: 'AB',
              normalizedText: 'AB',
            },
          ],
          commentAnnotationsBySentenceId: new Map([
            ['C0002:S001', [rangeLevelCommentA, rangeLevelCommentB]],
          ]),
          activeSourceAnnotationId: activeId,
        }),
      )

    const htmlA = renderWithActive('ann_a')
    const htmlB = renderWithActive('ann_b')

    const rangeAInA = htmlA.match(
      /data-source-annotation-id="ann_a"[^>]*class="([^"]*)"/,
    )?.[1]
    const rangeBInA = htmlA.match(
      /data-source-annotation-id="ann_b"[^>]*class="([^"]*)"/,
    )?.[1]
    expect(rangeAInA).toContain('bg-blue-100')
    expect(rangeBInA).not.toContain('bg-blue-100')

    const rangeAInB = htmlB.match(
      /data-source-annotation-id="ann_a"[^>]*class="([^"]*)"/,
    )?.[1]
    const rangeBInB = htmlB.match(
      /data-source-annotation-id="ann_b"[^>]*class="([^"]*)"/,
    )?.[1]
    expect(rangeAInB).not.toContain('bg-blue-100')
    expect(rangeBInB).toContain('bg-blue-100')
  })
})
