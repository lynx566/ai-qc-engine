import { describe, expect, it } from 'vitest'

import {
  buildSourceSentenceAnnotationSegments,
  renderSegmentedSentenceTextContent,
  resolveEditSourcePartClassName,
  sourceCommentActiveRangeMarkClassName,
} from '@/lib/source-comment-renderer'
import {
  sourceEditReplacementClassName,
  sourceEditSourceMarkClassName,
} from '@/lib/source-edit-renderer'
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

function edit(
  annotationId: string,
  startOffset: number,
  endOffset: number,
  replacementText: string,
): SourceAnnotation {
  return {
    annotationId,
    anchor,
    kind: 'edit',
    range: { startOffset, endOffset },
    replacementText,
    createdAt: '2026-09-13T00:00:00Z',
    updatedAt: '2026-09-13T00:00:00Z',
  }
}

describe('comment and edit overlap rendering', () => {
  it('segments overlapping comment and edit ranges deterministically', () => {
    const rawText = '发生率为70.0%，需确认。'
    const segments = buildSourceSentenceAnnotationSegments(
      rawText,
      [],
      [comment('ann_comment', 3, 10)],
      [edit('ann_edit', 4, 9, '80.0%')],
    )

    expect(segments).toEqual([
      { kind: 'plain', text: '发生率' },
      {
        kind: 'annotated',
        text: '为',
        commentAnnotationId: 'ann_comment',
      },
      {
        kind: 'edit-inline',
        annotationId: 'ann_edit',
        sourceParts: [
          {
            text: '70.0%',
            commentAnnotationId: 'ann_comment',
          },
        ],
        replacementText: '80.0%',
      },
      {
        kind: 'annotated',
        text: '，',
        commentAnnotationId: 'ann_comment',
      },
      { kind: 'comment-icon', annotationId: 'ann_comment' },
      { kind: 'plain', text: '需确认。' },
    ])
  })

  it('keeps revision line-through without comment text decoration on overlap', () => {
    const className = resolveEditSourcePartClassName('ann_comment', null)
    expect(className).toBe(sourceEditSourceMarkClassName)
    expect(className).toContain('line-through')
    expect(className).not.toContain('underline')
    expect(className).not.toContain('decoration-blue-400')
    expect(className).not.toContain('bg-blue-100')
  })

  it('adds active comment background over edit without hiding line-through', () => {
    const className = resolveEditSourcePartClassName('ann_comment', 'ann_comment')
    expect(className).toContain('line-through')
    expect(className).not.toContain('underline')
    expect(className).not.toContain('decoration-blue-400')
    expect(className).toContain(sourceCommentActiveRangeMarkClassName)
  })

  it('keeps comment range unstyled when edit is active', () => {
    const className = resolveEditSourcePartClassName('ann_comment', 'ann_edit')
    expect(className).toBe(sourceEditSourceMarkClassName)
    expect(className).not.toContain('bg-blue-100')
    expect(className).not.toContain('decoration-blue-400')
  })

  it('renders replacement and comment icon exactly once', () => {
    const rawText = '发生率为70.0%，需确认。'
    const segments = buildSourceSentenceAnnotationSegments(
      rawText,
      [],
      [comment('ann_comment', 3, 10)],
      [edit('ann_edit', 4, 9, '80.0%')],
    )

    expect(segments.filter((segment) => segment.kind === 'edit-inline')).toHaveLength(1)
    expect(segments.filter((segment) => segment.kind === 'comment-icon')).toHaveLength(1)
    const editSegment = segments.find((segment) => segment.kind === 'edit-inline')
    expect(editSegment).toMatchObject({
      replacementText: '80.0%',
    })
  })

  it('embeds comment icon on edit-inline before replacement when ranges share edit end', () => {
    const rawText = 'ABCDEF'
    const segments = buildSourceSentenceAnnotationSegments(
      rawText,
      [],
      [comment('ann_comment', 1, 3)],
      [edit('ann_edit', 1, 3, 'XY')],
    )

    expect(segments.map((segment) => segment.kind)).toEqual([
      'plain',
      'edit-inline',
      'plain',
    ])
    expect(segments[1]).toMatchObject({
      kind: 'edit-inline',
      commentIconAnnotationIds: ['ann_comment'],
      replacementText: 'XY',
    })
  })

  it('keeps comment icon at true comment end when comment extends past edit end', () => {
    const rawText = '发生率为70.0%，需确认。'
    const segments = buildSourceSentenceAnnotationSegments(
      rawText,
      [],
      [comment('ann_comment', 3, 10)],
      [edit('ann_edit', 4, 9, '80.0%')],
    )

    const editSegment = segments.find((segment) => segment.kind === 'edit-inline')
    expect(editSegment).toMatchObject({
      replacementText: '80.0%',
    })
    expect(editSegment).not.toHaveProperty('commentIconAnnotationIds')
    expect(segments.filter((segment) => segment.kind === 'comment-icon')).toEqual([
      { kind: 'comment-icon', annotationId: 'ann_comment' },
    ])
  })

  it('keeps canonical source reconstruction unchanged with overlap', () => {
    const rawText = '发生率为70.0%，需确认。'
    const segments = buildSourceSentenceAnnotationSegments(
      rawText,
      [],
      [comment('ann_comment', 3, 10)],
      [edit('ann_edit', 4, 9, '80.0%')],
    )

    expect(renderSegmentedSentenceTextContent(segments)).toBe(rawText)
    expect(sourceEditReplacementClassName).toContain('underline')
  })
})
