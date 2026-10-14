import {
  commentRangesOverlap,
  findSourceCommentForAnchor,
  findSourceCommentForAnchorAndRange,
  isLegacySentenceCommentAnnotation,
  isRangeLevelCommentAnnotation,
} from '@/lib/source-comment'
import type { SourceAnnotation, SourceSentenceAnchor } from '@/types/source-annotation'
import { describe, expect, it } from 'vitest'

const anchor: SourceSentenceAnchor = {
  slotId: 'source',
  docId: 'doc_test',
  blockId: 'C0002',
  sentenceId: 'C0002:S001',
}

const legacyComment: SourceAnnotation = {
  annotationId: 'ann_legacy',
  anchor,
  kind: 'comment',
  content: 'legacy',
  createdAt: '2026-09-13T00:00:00Z',
  updatedAt: '2026-09-13T00:00:00Z',
}

const rangeComment: SourceAnnotation = {
  annotationId: 'ann_range',
  anchor,
  kind: 'comment',
  content: 'range note',
  range: { startOffset: 1, endOffset: 4 },
  createdAt: '2026-09-13T00:00:00Z',
  updatedAt: '2026-09-13T00:00:00Z',
}

describe('source comment helpers', () => {
  it('detects legacy and range-level comments', () => {
    expect(isLegacySentenceCommentAnnotation(legacyComment)).toBe(true)
    expect(isRangeLevelCommentAnnotation(rangeComment)).toBe(true)
    expect(isRangeLevelCommentAnnotation(legacyComment)).toBe(false)
  })

  it('finds legacy comment by anchor only', () => {
    const found = findSourceCommentForAnchor(
      new Map([
        [legacyComment.annotationId, legacyComment],
        [rangeComment.annotationId, rangeComment],
      ]),
      anchor,
    )
    expect(found?.annotationId).toBe('ann_legacy')
  })

  it('finds range-level comment by anchor and exact range', () => {
    const found = findSourceCommentForAnchorAndRange(
      new Map([[rangeComment.annotationId, rangeComment]]),
      anchor,
      { startOffset: 1, endOffset: 4 },
    )
    expect(found?.annotationId).toBe('ann_range')
  })

  it('detects overlapping comment ranges', () => {
    expect(
      commentRangesOverlap({ startOffset: 1, endOffset: 5 }, { startOffset: 3, endOffset: 8 }),
    ).toBe(true)
    expect(
      commentRangesOverlap({ startOffset: 1, endOffset: 4 }, { startOffset: 4, endOffset: 8 }),
    ).toBe(false)
  })
})
