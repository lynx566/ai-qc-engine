import { isRenderableHighlightAnnotation } from '@/lib/source-highlight-renderer'
import type { SourceAnnotation } from '@/types/source-annotation'

function indexMatchingAnnotations(
  sourceAnnotations: Iterable<SourceAnnotation>,
  matches: (annotation: SourceAnnotation) => boolean,
): Map<string, SourceAnnotation[]> {
  const grouped = new Map<string, SourceAnnotation[]>()
  for (const annotation of sourceAnnotations) {
    if (!matches(annotation)) {
      continue
    }
    const existing = grouped.get(annotation.anchor.sentenceId) ?? []
    existing.push(annotation)
    grouped.set(annotation.anchor.sentenceId, existing)
  }
  return grouped
}

export function selectSourceAnnotationsForBlock(
  annotationsBySentenceId: Map<string, SourceAnnotation[]> | undefined,
  sourceBlockId: string,
): Map<string, SourceAnnotation[]> | undefined {
  if (!annotationsBySentenceId) {
    return undefined
  }

  const selected = new Map<string, SourceAnnotation[]>()
  for (const [sentenceId, annotations] of annotationsBySentenceId) {
    const matching = annotations.filter(
      (annotation) => annotation.anchor.blockId === sourceBlockId,
    )
    if (matching.length > 0) {
      selected.set(sentenceId, matching)
    }
  }
  return selected
}

export function buildHighlightAnnotationsBySentenceId(
  sourceAnnotations: Iterable<SourceAnnotation>,
  slotId: string,
  docId: string,
): Map<string, SourceAnnotation[]> {
  return indexMatchingAnnotations(sourceAnnotations, (annotation) => {
    if (!isRenderableHighlightAnnotation(annotation)) {
      return false
    }
    return (
      annotation.anchor.slotId === slotId && annotation.anchor.docId === docId
    )
  })
}

export function buildCommentAnnotationsBySentenceId(
  sourceAnnotations: Iterable<SourceAnnotation>,
  slotId: string,
  docId: string,
): Map<string, SourceAnnotation[]> {
  return indexMatchingAnnotations(sourceAnnotations, (annotation) => {
    return (
      annotation.kind === 'comment' &&
      annotation.anchor.slotId === slotId &&
      annotation.anchor.docId === docId
    )
  })
}

export function buildEditAnnotationsBySentenceId(
  sourceAnnotations: Iterable<SourceAnnotation>,
  slotId: string,
  docId: string,
): Map<string, SourceAnnotation[]> {
  return indexMatchingAnnotations(sourceAnnotations, (annotation) => {
    return (
      annotation.kind === 'edit' &&
      annotation.anchor.slotId === slotId &&
      annotation.anchor.docId === docId
    )
  })
}
