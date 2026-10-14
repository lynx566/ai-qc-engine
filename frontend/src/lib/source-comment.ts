import type {
  SourceAnnotation,
  SourceSentenceAnchor,
  SourceTextRange,
} from '@/types/source-annotation'

export function sourceSentenceAnchorsEqual(
  left: SourceSentenceAnchor,
  right: SourceSentenceAnchor,
): boolean {
  return (
    left.slotId === right.slotId &&
    left.docId === right.docId &&
    left.blockId === right.blockId &&
    left.sentenceId === right.sentenceId
  )
}

export function sourceTextRangesEqual(
  left: SourceTextRange,
  right: SourceTextRange,
): boolean {
  return (
    left.startOffset === right.startOffset && left.endOffset === right.endOffset
  )
}

export function isRenderableCommentAnnotation(
  annotation: SourceAnnotation,
): boolean {
  return annotation.kind === 'comment' && typeof annotation.content === 'string'
}

export function isRangeLevelCommentAnnotation(
  annotation: SourceAnnotation,
): boolean {
  return isRenderableCommentAnnotation(annotation) && annotation.range !== undefined
}

export function isLegacySentenceCommentAnnotation(
  annotation: SourceAnnotation,
): boolean {
  return isRenderableCommentAnnotation(annotation) && annotation.range === undefined
}

export function findSourceCommentForAnchor(
  annotations: Map<string, SourceAnnotation> | Iterable<SourceAnnotation>,
  anchor: SourceSentenceAnchor,
): SourceAnnotation | null {
  for (const annotation of annotations instanceof Map
    ? annotations.values()
    : annotations) {
    if (!isLegacySentenceCommentAnnotation(annotation)) {
      continue
    }
    if (sourceSentenceAnchorsEqual(annotation.anchor, anchor)) {
      return annotation
    }
  }
  return null
}

export function findSourceCommentForAnchorAndRange(
  annotations: Map<string, SourceAnnotation> | Iterable<SourceAnnotation>,
  anchor: SourceSentenceAnchor,
  range: SourceTextRange,
): SourceAnnotation | null {
  for (const annotation of annotations instanceof Map
    ? annotations.values()
    : annotations) {
    if (!isRangeLevelCommentAnnotation(annotation) || !annotation.range) {
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

export function commentRangesOverlap(
  left: SourceTextRange,
  right: SourceTextRange,
): boolean {
  return left.startOffset < right.endOffset && right.startOffset < left.endOffset
}

export function isValidCommentDraft(content: string): boolean {
  return content.trim().length > 0
}
