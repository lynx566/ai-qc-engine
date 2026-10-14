import { describe, expect, it } from 'vitest'

import {
  buildCommentNavigationSequence,
  buildRevisionNavigationSequence,
  buildSourceAnnotationNavigationSequence,
  resolveActiveAnnotationAfterDelete,
  resolveNextAnnotationIndex,
} from '@/lib/source-annotation-navigation'
import type { SourceAnnotation } from '@/types/source-annotation'
import type { DocumentView } from '@/types/document-review'

const document: DocumentView = {
  docId: 'doc_test',
  fileName: 'test.docx',
  displayName: 'test',
  blocks: [
    {
      blockId: 'doc_test:C0002',
      sourceBlockId: 'C0002',
      kind: 'paragraph',
      docOrderIndex: 2,
      headingPath: [],
      displayText: '第一句。第二句。',
      sentences: [
        { sentenceId: 'C0002:S001', rawText: '第一句。', normalizedText: '第一句。' },
        { sentenceId: 'C0002:S002', rawText: '第二句。', normalizedText: '第二句。' },
      ],
    },
    {
      blockId: 'doc_test:C0003',
      sourceBlockId: 'C0003',
      kind: 'paragraph',
      docOrderIndex: 1,
      headingPath: [],
      displayText: '更早一句。',
      sentences: [
        { sentenceId: 'C0003:S001', rawText: '更早一句。', normalizedText: '更早一句。' },
      ],
    },
  ],
}

const anchor = {
  slotId: 'source',
  docId: 'doc_test',
  blockId: 'C0002',
  sentenceId: 'C0002:S001',
}

function annotation(
  annotationId: string,
  kind: 'highlight' | 'comment' | 'edit',
  overrides: Partial<SourceAnnotation> = {},
): SourceAnnotation {
  return {
    annotationId,
    anchor,
    kind,
    createdAt: '2026-09-13T00:00:00Z',
    updatedAt: '2026-09-13T00:00:00Z',
    ...(kind === 'highlight'
      ? { range: { startOffset: 0, endOffset: 1 } }
      : kind === 'edit'
        ? { range: { startOffset: 0, endOffset: 1 }, replacementText: '80.0%' }
        : { content: 'note', range: { startOffset: 0, endOffset: 1 } }),
    ...overrides,
  }
}

describe('buildRevisionNavigationSequence', () => {
  it('includes only edits in document order', () => {
    const sequence = buildRevisionNavigationSequence(document, [
      annotation('ann_edit_b', 'edit', {
        anchor: { ...anchor, blockId: 'C0002', sentenceId: 'C0002:S002' },
      }),
      annotation('ann_edit_a', 'edit', {
        anchor: { ...anchor, blockId: 'C0003', sentenceId: 'C0003:S001' },
      }),
      annotation('ann_comment', 'comment'),
      annotation('ann_h1', 'highlight'),
    ])

    expect(sequence.map((entry) => entry.annotationId)).toEqual(['ann_edit_a', 'ann_edit_b'])
  })
})

describe('buildCommentNavigationSequence', () => {
  it('includes only comments in document order', () => {
    const sequence = buildCommentNavigationSequence(document, [
      annotation('ann_comment_b', 'comment', {
        anchor: { ...anchor, blockId: 'C0002', sentenceId: 'C0002:S002' },
      }),
      annotation('ann_comment_a', 'comment', {
        anchor: { ...anchor, blockId: 'C0003', sentenceId: 'C0003:S001' },
      }),
      annotation('ann_edit', 'edit'),
      annotation('ann_h1', 'highlight'),
    ])

    expect(sequence.map((entry) => entry.annotationId)).toEqual([
      'ann_comment_a',
      'ann_comment_b',
    ])
  })

  it('places legacy range-less comments after range comments in same sentence', () => {
    const sequence = buildCommentNavigationSequence(document, [
      {
        ...annotation('ann_legacy', 'comment'),
        range: undefined,
      },
      annotation('ann_range', 'comment', { range: { startOffset: 2, endOffset: 3 } }),
    ])

    expect(sequence.map((entry) => entry.annotationId)).toEqual([
      'ann_range',
      'ann_legacy',
    ])
  })
})

describe('resolveNextAnnotationIndex for split sequences', () => {
  const revisions = [
    annotation('rev_1', 'edit'),
    annotation('rev_2', 'edit', { range: { startOffset: 1, endOffset: 2 } }),
    annotation('rev_3', 'edit', { range: { startOffset: 2, endOffset: 3 } }),
  ]
  const comments = [
    annotation('com_1', 'comment'),
    annotation('com_2', 'comment', { range: { startOffset: 1, endOffset: 2 } }),
    annotation('com_3', 'comment', { range: { startOffset: 2, endOffset: 3 } }),
  ]

  it('revision next only traverses edits', () => {
    expect(resolveNextAnnotationIndex(revisions, 'rev_2', 'next')).toBe(2)
    expect(resolveNextAnnotationIndex(revisions, 'rev_3', 'next')).toBe(0)
  })

  it('revision previous only traverses edits', () => {
    expect(resolveNextAnnotationIndex(revisions, 'rev_2', 'previous')).toBe(0)
    expect(resolveNextAnnotationIndex(revisions, 'rev_1', 'previous')).toBe(2)
  })

  it('comment next only traverses comments', () => {
    expect(resolveNextAnnotationIndex(comments, 'com_2', 'next')).toBe(2)
    expect(resolveNextAnnotationIndex(comments, 'com_3', 'next')).toBe(0)
  })

  it('starts at first or last in each group when active belongs to another kind', () => {
    expect(resolveNextAnnotationIndex(revisions, 'com_2', 'next')).toBe(0)
    expect(resolveNextAnnotationIndex(revisions, 'com_2', 'previous')).toBe(2)
    expect(resolveNextAnnotationIndex(comments, 'rev_1', 'next')).toBe(0)
    expect(resolveNextAnnotationIndex(comments, 'rev_1', 'previous')).toBe(2)
  })
})

describe('buildSourceAnnotationNavigationSequence', () => {
  it('orders annotations by document order, not creation order', () => {
    const sequence = buildSourceAnnotationNavigationSequence(document, [
      annotation('ann_b', 'highlight', {
        anchor: { ...anchor, blockId: 'C0002', sentenceId: 'C0002:S002' },
      }),
      annotation('ann_a', 'highlight', {
        anchor: { ...anchor, blockId: 'C0003', sentenceId: 'C0003:S001' },
      }),
    ])

    expect(sequence.map((entry) => entry.annotationId)).toEqual(['ann_a', 'ann_b'])
  })

  it('orders highlights, edits, and range comments by start offset in same sentence', () => {
    const sequence = buildSourceAnnotationNavigationSequence(document, [
      annotation('ann_comment', 'comment', { range: { startOffset: 2, endOffset: 3 } }),
      annotation('ann_edit', 'edit', { range: { startOffset: 1, endOffset: 2 } }),
      annotation('ann_h2', 'highlight', { range: { startOffset: 2, endOffset: 3 } }),
      annotation('ann_h1', 'highlight', { range: { startOffset: 0, endOffset: 1 } }),
    ])

    expect(sequence.map((entry) => entry.annotationId)).toEqual([
      'ann_h1',
      'ann_edit',
      'ann_h2',
      'ann_comment',
    ])
  })

  it('places legacy range-less comments after range-level annotations', () => {
    const sequence = buildSourceAnnotationNavigationSequence(document, [
      {
        ...annotation('ann_legacy', 'comment'),
        range: undefined,
      },
      annotation('ann_range', 'comment', { range: { startOffset: 2, endOffset: 3 } }),
    ])

    expect(sequence.map((entry) => entry.annotationId)).toEqual([
      'ann_range',
      'ann_legacy',
    ])
  })
})

describe('resolveNextAnnotationIndex', () => {
  const sequence = [
    annotation('ann_1', 'highlight'),
    annotation('ann_2', 'comment'),
    annotation('ann_3', 'highlight', { range: { startOffset: 1, endOffset: 2 } }),
  ]

  it('starts at first or last when no active annotation', () => {
    expect(resolveNextAnnotationIndex(sequence, null, 'next')).toBe(0)
    expect(resolveNextAnnotationIndex(sequence, null, 'previous')).toBe(2)
  })

  it('wraps around at boundaries', () => {
    expect(resolveNextAnnotationIndex(sequence, 'ann_3', 'next')).toBe(0)
    expect(resolveNextAnnotationIndex(sequence, 'ann_1', 'previous')).toBe(2)
  })
})

describe('resolveActiveAnnotationAfterDelete', () => {
  const sequence = [
    annotation('ann_1', 'highlight'),
    annotation('ann_2', 'comment'),
    annotation('ann_3', 'highlight'),
  ]

  it('prefers next neighbor after delete', () => {
    expect(resolveActiveAnnotationAfterDelete(sequence, 'ann_2')).toBe('ann_3')
  })

  it('falls back to previous when deleting last', () => {
    expect(resolveActiveAnnotationAfterDelete(sequence, 'ann_3')).toBe('ann_2')
  })
})
