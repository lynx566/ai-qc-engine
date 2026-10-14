import type { SourceTextRange } from '@/types/source-annotation'

export type SourceTextRangeSlice = {
  prefix: string
  middle: string
  suffix: string
}

function toCodePoints(text: string): string[] {
  return Array.from(text)
}

export function codePointLength(text: string): number {
  return toCodePoints(text).length
}

export function sliceByCodePoint(text: string, start: number, end: number): string {
  return toCodePoints(text).slice(start, end).join('')
}

export function sliceSourceTextByRange(
  text: string,
  range: SourceTextRange,
): SourceTextRangeSlice {
  const points = toCodePoints(text)
  const prefix = points.slice(0, range.startOffset).join('')
  const middle = points.slice(range.startOffset, range.endOffset).join('')
  const suffix = points.slice(range.endOffset).join('')
  return { prefix, middle, suffix }
}

export function utf16OffsetToCodePointOffset(text: string, utf16Offset: number): number {
  if (utf16Offset < 0 || utf16Offset > text.length) {
    throw new RangeError('utf16Offset is out of bounds')
  }
  return toCodePoints(text.slice(0, utf16Offset)).length
}

export function codePointOffsetToUtf16Offset(text: string, codePointOffset: number): number {
  const length = codePointLength(text)
  if (codePointOffset < 0 || codePointOffset > length) {
    throw new RangeError('codePointOffset is out of bounds')
  }
  return toCodePoints(text).slice(0, codePointOffset).join('').length
}

export function normalizeSourceTextRange(
  startOffset: number,
  endOffset: number,
): SourceTextRange {
  const start = Math.min(startOffset, endOffset)
  const end = Math.max(startOffset, endOffset)
  if (start === end) {
    throw new RangeError('source text range must be non-empty')
  }
  return { startOffset: start, endOffset: end }
}
