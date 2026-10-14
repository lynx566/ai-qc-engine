import type {
  SourceAnnotation,
  SourceSentenceAnchor,
  SourceTextRange,
} from '@/types/source-annotation'

import {
  sourceSentenceAnchorsEqual,
  sourceTextRangesEqual,
} from '@/lib/source-comment'

export function isRenderableEditAnnotation(
  annotation: SourceAnnotation,
): boolean {
  return (
    annotation.kind === 'edit' &&
    typeof annotation.replacementText === 'string' &&
    annotation.replacementText.length > 0 &&
    annotation.range !== undefined
  )
}

export function findSourceEditForAnchorAndRange(
  annotations: Map<string, SourceAnnotation> | Iterable<SourceAnnotation>,
  anchor: SourceSentenceAnchor,
  range: SourceTextRange,
): SourceAnnotation | null {
  for (const annotation of annotations instanceof Map
    ? annotations.values()
    : annotations) {
    if (!isRenderableEditAnnotation(annotation) || !annotation.range) {
      continue
    }
    if (
      sourceSentenceAnchorsEqual(annotation.anchor, anchor) &&
      sourceTextRangesEqual(annotation.range, range)
    ) {
      return annotation
    }
  }
  return null
}

export function editRangesOverlap(
  left: SourceTextRange,
  right: SourceTextRange,
): boolean {
  return left.startOffset < right.endOffset && right.startOffset < left.endOffset
}

export function isValidEditDraft(replacementText: string): boolean {
  return replacementText.trim().length > 0
}
