import { describe, expect, it } from 'vitest'

import {
  buildSourceSentenceAnnotationSegments,
  renderSegmentedSentenceTextContent,
} from '@/lib/source-comment-renderer'
import {
  sourceEditActiveGroupClassName,
  sourceEditReplacementClassName,
  sourceEditSourceMarkClassName,
} from '@/lib/source-edit-renderer'
import type { SourceAnnotation } from '@/types/source-annotation'

function editAnnotation(
  overrides: Partial<SourceAnnotation> = {},
): SourceAnnotation {
  return {
    annotationId: 'ann_edit',
    anchor: {
      slotId: 'source',
      docId: 'doc_test',
      blockId: 'C0002',
      sentenceId: 'C0002:S001',
    },
    createdAt: '2026-09-13T00:00:00Z',
    updatedAt: '2026-09-13T00:00:00Z',
    kind: 'edit',
    range: { startOffset: 1, endOffset: 3 },
    replacementText: 'XY',
    ...overrides,
  }
}

describe('edit sentence renderer', () => {
  it('renders strikethrough source and underlined replacement immediately after range', () => {
    const segments = buildSourceSentenceAnnotationSegments(
      'ABCDEF。',
      [],
      [],
      [editAnnotation()],
    )

    expect(segments).toEqual([
      { kind: 'plain', text: 'A' },
      {
        kind: 'edit-inline',
        annotationId: 'ann_edit',
        sourceParts: [{ text: 'BC' }],
        replacementText: 'XY',
      },
      { kind: 'plain', text: 'DEF。' },
    ])
  })

  it('keeps canonical reconstructed source text equal to rawText', () => {
    const rawText = 'ABCDEF。'
    const segments = buildSourceSentenceAnnotationSegments(
      rawText,
      [],
      [],
      [editAnnotation()],
    )

    expect(renderSegmentedSentenceTextContent(segments)).toBe(rawText)
  })

  it('uses rose line-through and underline classes', () => {
    expect(sourceEditSourceMarkClassName).toContain('line-through')
    expect(sourceEditSourceMarkClassName).toContain('text-rose-600')
    expect(sourceEditReplacementClassName).toContain('underline')
    expect(sourceEditReplacementClassName).toContain('text-rose-600')
    expect(sourceEditActiveGroupClassName).toContain('bg-rose-50')
  })
})
