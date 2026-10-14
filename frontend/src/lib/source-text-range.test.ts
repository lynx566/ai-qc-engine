import { describe, expect, it } from 'vitest'

import {
  codePointLength,
  codePointOffsetToUtf16Offset,
  normalizeSourceTextRange,
  sliceByCodePoint,
  sliceSourceTextByRange,
  utf16OffsetToCodePointOffset,
} from '@/lib/source-text-range'

describe('source text range code-point helpers', () => {
  it('measures ASCII and Chinese by code point', () => {
    expect(codePointLength('ABC')).toBe(3)
    expect(codePointLength('感染性肺炎')).toBe(5)
  })

  it('slices emoji without splitting surrogate pair', () => {
    const text = 'A😀B'
    expect(sliceByCodePoint(text, 1, 2)).toBe('😀')
    expect(sliceSourceTextByRange(text, { startOffset: 1, endOffset: 2 }).middle).toBe('😀')
  })

  it('converts UTF-16 offsets to code-point offsets', () => {
    const text = 'A😀B'
    expect(utf16OffsetToCodePointOffset(text, 0)).toBe(0)
    expect(utf16OffsetToCodePointOffset(text, 1)).toBe(1)
    expect(utf16OffsetToCodePointOffset(text, 3)).toBe(2)
    expect(utf16OffsetToCodePointOffset(text, 4)).toBe(3)
  })

  it('converts code-point offsets to UTF-16 offsets', () => {
    const text = 'A😀B'
    expect(codePointOffsetToUtf16Offset(text, 0)).toBe(0)
    expect(codePointOffsetToUtf16Offset(text, 1)).toBe(1)
    expect(codePointOffsetToUtf16Offset(text, 2)).toBe(3)
    expect(codePointOffsetToUtf16Offset(text, 3)).toBe(4)
  })

  it('round-trips code point through UTF-16', () => {
    const text = '中文😀END'
    for (let codePointOffset = 0; codePointOffset <= codePointLength(text); codePointOffset += 1) {
      const utf16Offset = codePointOffsetToUtf16Offset(text, codePointOffset)
      expect(utf16OffsetToCodePointOffset(text, utf16Offset)).toBe(codePointOffset)
    }
  })

  it('normalizes reversed code-point offsets', () => {
    expect(normalizeSourceTextRange(4, 1)).toEqual({
      startOffset: 1,
      endOffset: 4,
    })
  })

  it('keeps Chinese offsets intuitive', () => {
    const text = '感染性肺炎2例'
    expect(sliceByCodePoint(text, 0, 5)).toBe('感染性肺炎')
    expect(sliceByCodePoint(text, 5, 6)).toBe('2')
  })
})
