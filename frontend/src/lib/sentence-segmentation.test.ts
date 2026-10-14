import { describe, expect, it } from 'vitest'

import {
  renderSegmentedTextContent,
  segmentSentenceText,
} from '@/lib/sentence-segmentation'

function sentences(...items: Array<{ id: string; text: string }>) {
  return items.map((item) => ({
    sentenceId: item.id,
    rawText: item.text,
  }))
}

describe('segmentSentenceText', () => {
  it('segments contiguous Chinese sentences without gaps', () => {
    const displayText = '第一句。第二句。'
    const result = segmentSentenceText(
      displayText,
      sentences(
        { id: 'C0001:S001', text: '第一句。' },
        { id: 'C0001:S002', text: '第二句。' },
      ),
    )

    expect(result.available).toBe(true)
    if (!result.available) {
      return
    }
    expect(renderSegmentedTextContent(result.segments)).toBe(displayText)
  })

  it('preserves newline gaps between sentences', () => {
    const displayText = '上行内容\n下行内容。'
    const result = segmentSentenceText(
      displayText,
      sentences(
        { id: 'C0001:S001', text: '上行内容' },
        { id: 'C0001:S002', text: '下行内容。' },
      ),
    )

    expect(result.available).toBe(true)
    if (!result.available) {
      return
    }
    expect(renderSegmentedTextContent(result.segments)).toBe(displayText)
    expect(result.segments.some((segment) => segment.kind === 'gap' && segment.text === '\n')).toBe(
      true,
    )
  })

  it('preserves repeated newlines between sentences', () => {
    const displayText = 'A\n\nB'
    const result = segmentSentenceText(
      displayText,
      sentences({ id: 'C0001:S001', text: 'A' }, { id: 'C0001:S002', text: 'B' }),
    )

    expect(result.available).toBe(true)
    if (!result.available) {
      return
    }
    expect(renderSegmentedTextContent(result.segments)).toBe(displayText)
    expect(result.segments.some((segment) => segment.kind === 'gap' && segment.text === '\n\n')).toBe(
      true,
    )
  })

  it('preserves whitespace gaps between sentences', () => {
    const displayText = '第一句。 第二句。'
    const result = segmentSentenceText(
      displayText,
      sentences(
        { id: 'C0001:S001', text: '第一句。' },
        { id: 'C0001:S002', text: '第二句。' },
      ),
    )

    expect(result.available).toBe(true)
    if (!result.available) {
      return
    }
    expect(renderSegmentedTextContent(result.segments)).toBe(displayText)
    expect(result.segments.some((segment) => segment.kind === 'gap' && segment.text === ' ')).toBe(
      true,
    )
  })

  it('maps duplicate sentence content to distinct sentence ids', () => {
    const displayText = 'A。A。'
    const result = segmentSentenceText(
      displayText,
      sentences({ id: 'C0001:S001', text: 'A。' }, { id: 'C0001:S002', text: 'A。' }),
    )

    expect(result.available).toBe(true)
    if (!result.available) {
      return
    }
    const sentenceIds = result.segments
      .filter((segment) => segment.kind === 'sentence')
      .map((segment) => segment.sentenceId)
    expect(sentenceIds).toEqual(['C0001:S001', 'C0001:S002'])
    expect(renderSegmentedTextContent(result.segments)).toBe(displayText)
  })

  it('preserves leading and trailing gaps', () => {
    const displayText = '  A。  '
    const result = segmentSentenceText(
      displayText,
      sentences({ id: 'C0001:S001', text: 'A。' }),
    )

    expect(result.available).toBe(true)
    if (!result.available) {
      return
    }
    expect(renderSegmentedTextContent(result.segments)).toBe(displayText)
  })

  it('returns unavailable when a sentence cannot be exact-located', () => {
    const result = segmentSentenceText(
      '第一句。第二句。',
      sentences(
        { id: 'C0001:S001', text: '第一句。' },
        { id: 'C0001:S002', text: 'missing' },
      ),
    )

    expect(result.available).toBe(false)
  })
})
