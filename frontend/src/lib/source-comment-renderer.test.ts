import { describe, expect, it } from 'vitest'

import {
  buildSourceSentenceAnnotationSegments,
  renderSegmentedSentenceTextContent,
  resolveSourceCommentRangeMarkClassName,
  sourceCommentActiveRangeMarkClassName,
} from '@/lib/source-comment-renderer'
import { sentenceNavigationFocusClassName } from '@/lib/sentence-navigation-focus'
import type { SourceAnnotation } from '@/types/source-annotation'

const anchor = {
  slotId: 'source',
  docId: 'doc_test',
  blockId: 'C0002',
  sentenceId: 'C0002:S001',
}

function comment(
  annotationId: string,
  startOffset: number,
  endOffset: number,
): SourceAnnotation {
  return {
    annotationId,
    anchor,
    kind: 'comment',
    content: 'note',
    range: { startOffset, endOffset },
    createdAt: '2026-09-13T00:00:00Z',
    updatedAt: '2026-09-13T00:00:00Z',
  }
}

describe('buildSourceSentenceAnnotationSegments', () => {
  it('reconstructs raw text with range comment icon segments excluded', () => {
    const segments = buildSourceSentenceAnnotationSegments(
      'ABCDEF。',
      [],
      [comment('ann_a', 1, 3)],
    )

    expect(renderSegmentedSentenceTextContent(segments)).toBe('ABCDEF。')
    expect(segments.some((segment) => segment.kind === 'comment-icon')).toBe(true)
  })

  it('places comment icon after exact range end before following text', () => {
    const segments = buildSourceSentenceAnnotationSegments(
      'ABCDEF。',
      [],
      [comment('ann_a', 1, 3)],
    )

    const kinds = segments.map((segment) => segment.kind)
    expect(kinds).toEqual(['plain', 'annotated', 'comment-icon', 'plain'])
  })

  it('supports two non-overlapping comments in one sentence', () => {
    const segments = buildSourceSentenceAnnotationSegments(
      'AB70.0%CD24例EF',
      [],
      [comment('ann_a', 2, 7), comment('ann_b', 9, 12)],
    )

    expect(segments.filter((segment) => segment.kind === 'comment-icon')).toHaveLength(2)
    expect(renderSegmentedSentenceTextContent(segments)).toBe('AB70.0%CD24例EF')
  })
})

describe('comment range color hierarchy', () => {
  it('applies no comment-specific text style for non-active comment range', () => {
    const className = resolveSourceCommentRangeMarkClassName('ann_a', null)
    expect(className).toBe('')
    expect(className).not.toContain('bg-blue-100')
    expect(className).not.toContain('underline')
    expect(className).not.toContain('decoration-blue-400')
  })

  it('adds light-blue background only when comment is active', () => {
    const activeClassName = resolveSourceCommentRangeMarkClassName('ann_a', 'ann_a')
    expect(activeClassName).toContain(sourceCommentActiveRangeMarkClassName)
    expect(activeClassName).toContain('bg-blue-100')
    expect(activeClassName).not.toContain('underline')
    expect(activeClassName).not.toContain('decoration-blue-400')
  })

  it('moves active background when navigating A to B', () => {
    const classAWhenActive = resolveSourceCommentRangeMarkClassName('ann_a', 'ann_a')
    const classAWhenInactive = resolveSourceCommentRangeMarkClassName('ann_a', 'ann_b')
    const classBWhenActive = resolveSourceCommentRangeMarkClassName('ann_b', 'ann_b')

    expect(classAWhenActive).toContain('bg-blue-100')
    expect(classAWhenInactive).toBe('')
    expect(classBWhenActive).toContain('bg-blue-100')
  })

  it('keeps Evidence source focus class unchanged and distinct from comment range', () => {
    expect(sentenceNavigationFocusClassName).toContain('#E3EEF7')
    expect(sourceCommentActiveRangeMarkClassName).toContain('bg-blue-100')
    expect(sourceCommentActiveRangeMarkClassName).not.toContain('bg-sky-100')
    expect(sourceCommentActiveRangeMarkClassName).not.toContain('underline')
  })
})
