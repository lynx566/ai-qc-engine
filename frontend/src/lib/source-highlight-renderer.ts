import { codePointLength, sliceByCodePoint } from '@/lib/source-text-range'
import { cn } from '@/lib/utils'
import type { SourceAnnotation, SourceTextRange } from '@/types/source-annotation'

export const sourceHighlightMarkClassName =
  'text-rose-700 [text-decoration:none]'

export const sourceHighlightActiveMarkClassName =
  'rounded-[2px] bg-rose-100/60 box-decoration-clone'

export function resolveSourceHighlightMarkClassName(
  annotationId: string,
  activeSourceAnnotationId: string | null | undefined,
): string {
  return cn(
    sourceHighlightMarkClassName,
    activeSourceAnnotationId === annotationId && sourceHighlightActiveMarkClassName,
  )
}

export type SourceHighlightRenderSegment =
  | { kind: 'plain'; text: string }
  | { kind: 'mark'; text: string; annotationId: string }

export function isRenderableHighlightAnnotation(
  annotation: SourceAnnotation,
): boolean {
  return annotation.kind === 'highlight' && annotation.range !== undefined
}

export function highlightRangesOverlap(
  left: SourceTextRange,
  right: SourceTextRange,
): boolean {
  return left.startOffset < right.endOffset && right.startOffset < left.endOffset
}

export function buildSourceHighlightSegments(
  rawText: string,
  highlights: readonly SourceAnnotation[],
): SourceHighlightRenderSegment[] {
  const sorted = highlights
    .filter(isRenderableHighlightAnnotation)
    .sort((left, right) => left.range!.startOffset - right.range!.startOffset)

  const segments: SourceHighlightRenderSegment[] = []
  let cursor = 0

  for (const highlight of sorted) {
    const range = highlight.range!
    if (range.startOffset < cursor) {
      continue
    }
    if (range.startOffset > cursor) {
      segments.push({
        kind: 'plain',
        text: sliceByCodePoint(rawText, cursor, range.startOffset),
      })
    }
    segments.push({
      kind: 'mark',
      text: sliceByCodePoint(rawText, range.startOffset, range.endOffset),
      annotationId: highlight.annotationId,
    })
    cursor = range.endOffset
  }

  const textLength = codePointLength(rawText)
  if (cursor < textLength) {
    segments.push({
      kind: 'plain',
      text: sliceByCodePoint(rawText, cursor, textLength),
    })
  }

  return segments
}

export function renderSegmentedTextContent(
  segments: readonly SourceHighlightRenderSegment[],
): string {
  return segments.map((segment) => segment.text).join('')
}
