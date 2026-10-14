import { describe, expect, it } from 'vitest'

import {
  buildSourceHighlightSegments,
  highlightRangesOverlap,
  isRenderableHighlightAnnotation,
  renderSegmentedTextContent,
  resolveSourceHighlightMarkClassName,
  sourceHighlightActiveMarkClassName,
  sourceHighlightMarkClassName,
} from '@/lib/source-highlight-renderer'
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
    createdAt: '2026-09-13T00:00:00Z',
    updatedAt: '2026-09-13T00:00:00Z',
    kind: 'highlight',
    range: { startOffset, endOffset },
  }
}

describe('buildSourceHighlightSegments', () => {
  it('renders a single highlight substring', () => {
    const segments = buildSourceHighlightSegments('感染性肺炎2例', [highlight('ann_1', 0, 5)])
    expect(renderSegmentedTextContent(segments)).toBe('感染性肺炎2例')
    expect(segments).toEqual([
      { kind: 'mark', text: '感染性肺炎', annotationId: 'ann_1' },
      { kind: 'plain', text: '2例' },
    ])
  })

  it('renders two adjacent highlights', () => {
    const segments = buildSourceHighlightSegments('ABCDE', [
      highlight('ann_1', 0, 1),
      highlight('ann_2', 1, 3),
    ])
    expect(renderSegmentedTextContent(segments)).toBe('ABCDE')
  })

  it('renders emoji ranges by code point', () => {
    const segments = buildSourceHighlightSegments('A😀B', [highlight('ann_1', 1, 2)])
    expect(segments).toEqual([
      { kind: 'plain', text: 'A' },
      { kind: 'mark', text: '😀', annotationId: 'ann_1' },
      { kind: 'plain', text: 'B' },
    ])
  })

  it('ignores annotations without highlight kind', () => {
    const segments = buildSourceHighlightSegments('ABC', [
      {
        ...highlight('ann_1', 0, 1),
        kind: undefined,
      },
    ])
    expect(segments).toEqual([{ kind: 'plain', text: 'ABC' }])
  })
})

describe('highlightRangesOverlap', () => {
  it('detects overlap but allows adjacent ranges', () => {
    expect(
      highlightRangesOverlap({ startOffset: 1, endOffset: 5 }, { startOffset: 3, endOffset: 8 }),
    ).toBe(true)
    expect(
      highlightRangesOverlap({ startOffset: 1, endOffset: 4 }, { startOffset: 4, endOffset: 8 }),
    ).toBe(false)
  })
})

describe('sourceHighlightMarkClassName', () => {
  it('uses rose text color without background or underline', () => {
    expect(sourceHighlightMarkClassName).toContain('text-rose-700')
    expect(sourceHighlightMarkClassName).not.toContain('bg-rose')
    expect(sourceHighlightMarkClassName).not.toContain('underline')
    expect(sourceHighlightMarkClassName).not.toContain('border')
  })
})

describe('resolveSourceHighlightMarkClassName', () => {
  it('adds light rose background only for the active annotation', () => {
    expect(resolveSourceHighlightMarkClassName('ann_a', null)).toBe(sourceHighlightMarkClassName)
    expect(resolveSourceHighlightMarkClassName('ann_a', 'ann_b')).toBe(sourceHighlightMarkClassName)
    expect(resolveSourceHighlightMarkClassName('ann_a', 'ann_a')).toContain(
      sourceHighlightActiveMarkClassName,
    )
    expect(resolveSourceHighlightMarkClassName('ann_a', 'ann_a')).toContain('text-rose-700')
    expect(resolveSourceHighlightMarkClassName('ann_a', 'ann_a')).toContain('bg-rose-100/60')
  })
})

describe('isRenderableHighlightAnnotation', () => {
  it('requires highlight kind and range', () => {
    expect(isRenderableHighlightAnnotation(highlight('ann_1', 0, 1))).toBe(true)
    expect(isRenderableHighlightAnnotation({ ...highlight('ann_1', 0, 1), kind: undefined })).toBe(
      false,
    )
  })
})
