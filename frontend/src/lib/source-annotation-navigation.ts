import { isLegacySentenceCommentAnnotation, isRenderableCommentAnnotation } from '@/lib/source-comment'
import { isRenderableEditAnnotation } from '@/lib/source-edit'
import { isRenderableHighlightAnnotation } from '@/lib/source-highlight-renderer'
import type { SourceAnnotation } from '@/types/source-annotation'
import type { DocumentView } from '@/types/document-review'

type SentenceAnnotationBucket = {
  highlights: SourceAnnotation[]
  rangeComments: SourceAnnotation[]
  legacyComments: SourceAnnotation[]
  edits: SourceAnnotation[]
}

function sentenceBucketKey(blockId: string, sentenceId: string): string {
  return `${blockId}:${sentenceId}`
}

export function buildRevisionNavigationSequence(
  document: DocumentView,
  annotations: Iterable<SourceAnnotation>,
): SourceAnnotation[] {
  const buckets = new Map<string, SourceAnnotation[]>()

  for (const annotation of annotations) {
    if (annotation.anchor.docId !== document.docId) {
      continue
    }
    if (!isRenderableEditAnnotation(annotation)) {
      continue
    }
    const key = sentenceBucketKey(annotation.anchor.blockId, annotation.anchor.sentenceId)
    const bucket = buckets.get(key) ?? []
    bucket.push(annotation)
    buckets.set(key, bucket)
  }

  const sequence: SourceAnnotation[] = []
  const sortedBlocks = [...document.blocks].sort(
    (left, right) => left.docOrderIndex - right.docOrderIndex,
  )

  for (const block of sortedBlocks) {
    if (!block.sentences || block.sentences.length === 0) {
      continue
    }

    for (const sentence of block.sentences) {
      const edits = buckets.get(sentenceBucketKey(block.sourceBlockId, sentence.sentenceId))
      if (!edits || edits.length === 0) {
        continue
      }

      sequence.push(
        ...[...edits].sort(
          (left, right) =>
            (left.range?.startOffset ?? 0) - (right.range?.startOffset ?? 0),
        ),
      )
    }
  }

  return sequence
}

export function buildCommentNavigationSequence(
  document: DocumentView,
  annotations: Iterable<SourceAnnotation>,
): SourceAnnotation[] {
  const buckets = new Map<
    string,
    { rangeComments: SourceAnnotation[]; legacyComments: SourceAnnotation[] }
  >()

  for (const annotation of annotations) {
    if (annotation.anchor.docId !== document.docId) {
      continue
    }
    if (!isRenderableCommentAnnotation(annotation)) {
      continue
    }
    const key = sentenceBucketKey(annotation.anchor.blockId, annotation.anchor.sentenceId)
    const bucket = buckets.get(key) ?? {
      rangeComments: [],
      legacyComments: [],
    }

    if (isLegacySentenceCommentAnnotation(annotation)) {
      bucket.legacyComments.push(annotation)
    } else {
      bucket.rangeComments.push(annotation)
    }
    buckets.set(key, bucket)
  }

  const sequence: SourceAnnotation[] = []
  const sortedBlocks = [...document.blocks].sort(
    (left, right) => left.docOrderIndex - right.docOrderIndex,
  )

  for (const block of sortedBlocks) {
    if (!block.sentences || block.sentences.length === 0) {
      continue
    }

    for (const sentence of block.sentences) {
      const bucket = buckets.get(sentenceBucketKey(block.sourceBlockId, sentence.sentenceId))
      if (!bucket) {
        continue
      }

      const rangeComments = [...bucket.rangeComments].sort(
        (left, right) =>
          (left.range?.startOffset ?? 0) - (right.range?.startOffset ?? 0),
      )
      sequence.push(...rangeComments, ...bucket.legacyComments)
    }
  }

  return sequence
}

export function buildSourceAnnotationNavigationSequence(
  document: DocumentView,
  annotations: Iterable<SourceAnnotation>,
): SourceAnnotation[] {
  const buckets = new Map<string, SentenceAnnotationBucket>()

  for (const annotation of annotations) {
    if (annotation.anchor.docId !== document.docId) {
      continue
    }
    const key = sentenceBucketKey(annotation.anchor.blockId, annotation.anchor.sentenceId)
    const bucket = buckets.get(key) ?? {
      highlights: [],
      rangeComments: [],
      legacyComments: [],
      edits: [],
    }

    if (isRenderableHighlightAnnotation(annotation)) {
      bucket.highlights.push(annotation)
      buckets.set(key, bucket)
      continue
    }

    if (isRenderableEditAnnotation(annotation)) {
      bucket.edits.push(annotation)
      buckets.set(key, bucket)
      continue
    }

    if (isRenderableCommentAnnotation(annotation)) {
      if (isLegacySentenceCommentAnnotation(annotation)) {
        bucket.legacyComments.push(annotation)
      } else {
        bucket.rangeComments.push(annotation)
      }
      buckets.set(key, bucket)
    }
  }

  const sequence: SourceAnnotation[] = []
  const sortedBlocks = [...document.blocks].sort(
    (left, right) => left.docOrderIndex - right.docOrderIndex,
  )

  for (const block of sortedBlocks) {
    if (!block.sentences || block.sentences.length === 0) {
      continue
    }

    for (const sentence of block.sentences) {
      const bucket = buckets.get(sentenceBucketKey(block.sourceBlockId, sentence.sentenceId))
      if (!bucket) {
        continue
      }

      const highlights = [...bucket.highlights].sort(
        (left, right) =>
          (left.range?.startOffset ?? 0) - (right.range?.startOffset ?? 0),
      )
      const rangeComments = [...bucket.rangeComments].sort(
        (left, right) =>
          (left.range?.startOffset ?? 0) - (right.range?.startOffset ?? 0),
      )
      const edits = [...bucket.edits].sort(
        (left, right) =>
          (left.range?.startOffset ?? 0) - (right.range?.startOffset ?? 0),
      )

      const merged = [...highlights, ...edits, ...rangeComments].sort(
        (left, right) =>
          (left.range?.startOffset ?? Number.MAX_SAFE_INTEGER) -
          (right.range?.startOffset ?? Number.MAX_SAFE_INTEGER),
      )
      sequence.push(...merged)
      sequence.push(...bucket.legacyComments)
    }
  }

  return sequence
}

export function resolveNextAnnotationIndex(
  sequence: readonly SourceAnnotation[],
  activeAnnotationId: string | null,
  direction: 'next' | 'previous',
): number {
  if (sequence.length === 0) {
    return -1
  }

  if (!activeAnnotationId) {
    return direction === 'next' ? 0 : sequence.length - 1
  }

  const currentIndex = sequence.findIndex(
    (annotation) => annotation.annotationId === activeAnnotationId,
  )
  if (currentIndex === -1) {
    return direction === 'next' ? 0 : sequence.length - 1
  }

  if (direction === 'next') {
    return (currentIndex + 1) % sequence.length
  }

  return (currentIndex - 1 + sequence.length) % sequence.length
}

export function resolveActiveAnnotationAfterDelete(
  sequence: readonly SourceAnnotation[],
  deletedAnnotationId: string,
): string | null {
  const deletedIndex = sequence.findIndex(
    (annotation) => annotation.annotationId === deletedAnnotationId,
  )
  if (deletedIndex === -1) {
    return sequence[0]?.annotationId ?? null
  }

  const remaining = sequence.filter(
    (annotation) => annotation.annotationId !== deletedAnnotationId,
  )
  if (remaining.length === 0) {
    return null
  }

  if (deletedIndex < remaining.length) {
    return remaining[deletedIndex]?.annotationId ?? null
  }

  return remaining[remaining.length - 1]?.annotationId ?? null
}

export function resolveComposedBlockId(
  document: DocumentView,
  sourceBlockId: string,
): string {
  const block = document.blocks.find((entry) => entry.sourceBlockId === sourceBlockId)
  return block?.blockId ?? `${document.docId}:${sourceBlockId}`
}
