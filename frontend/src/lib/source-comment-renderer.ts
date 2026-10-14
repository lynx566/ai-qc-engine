import { codePointLength, sliceByCodePoint } from '@/lib/source-text-range'
import {
  isRenderableHighlightAnnotation,
  resolveSourceHighlightMarkClassName,
} from '@/lib/source-highlight-renderer'
import {
  isLegacySentenceCommentAnnotation,
  isRangeLevelCommentAnnotation,
} from '@/lib/source-comment'
import { isRenderableEditAnnotation } from '@/lib/source-edit'
import {
  resolveSourceEditSourceMarkClassName,
} from '@/lib/source-edit-renderer'
import { cn } from '@/lib/utils'
import type { SourceAnnotation } from '@/types/source-annotation'

export const sourceCommentActiveRangeMarkClassName =
  'rounded-[2px] bg-blue-100 box-decoration-clone'

export function resolveSourceCommentRangeMarkClassName(
  commentAnnotationId: string,
  activeSourceAnnotationId: string | null | undefined,
): string {
  return cn(
    activeSourceAnnotationId === commentAnnotationId &&
      sourceCommentActiveRangeMarkClassName,
  )
}

export function resolveEditSourcePartClassName(
  commentAnnotationId: string | undefined,
  activeSourceAnnotationId: string | null | undefined,
): string {
  return cn(
    resolveSourceEditSourceMarkClassName(),
    commentAnnotationId &&
      resolveSourceCommentRangeMarkClassName(
        commentAnnotationId,
        activeSourceAnnotationId,
      ),
  )
}

type IntervalAnnotation = {
  annotationId: string
  kind: 'highlight' | 'comment' | 'edit'
  startOffset: number
  endOffset: number
}

type MergedInterval = {
  startOffset: number
  endOffset: number
  highlightAnnotationId?: string
  commentAnnotationId?: string
  editAnnotationId?: string
}

export type EditInlineSourcePart = {
  text: string
  commentAnnotationId?: string
}

export type SourceSentenceAnnotationRenderSegment =
  | { kind: 'plain'; text: string }
  | {
      kind: 'annotated'
      text: string
      highlightAnnotationId?: string
      commentAnnotationId?: string
    }
  | {
      kind: 'edit-inline'
      annotationId: string
      sourceParts: EditInlineSourcePart[]
      commentIconAnnotationIds?: string[]
      replacementText: string
    }
  | { kind: 'comment-icon'; annotationId: string }

function collectIntervalAnnotations(
  highlights: readonly SourceAnnotation[],
  comments: readonly SourceAnnotation[],
  edits: readonly SourceAnnotation[],
): IntervalAnnotation[] {
  const items: IntervalAnnotation[] = []

  for (const highlight of highlights) {
    if (!isRenderableHighlightAnnotation(highlight) || !highlight.range) {
      continue
    }
    items.push({
      annotationId: highlight.annotationId,
      kind: 'highlight',
      startOffset: highlight.range.startOffset,
      endOffset: highlight.range.endOffset,
    })
  }

  for (const comment of comments) {
    if (!isRangeLevelCommentAnnotation(comment) || !comment.range) {
      continue
    }
    items.push({
      annotationId: comment.annotationId,
      kind: 'comment',
      startOffset: comment.range.startOffset,
      endOffset: comment.range.endOffset,
    })
  }

  for (const edit of edits) {
    if (!isRenderableEditAnnotation(edit) || !edit.range) {
      continue
    }
    items.push({
      annotationId: edit.annotationId,
      kind: 'edit',
      startOffset: edit.range.startOffset,
      endOffset: edit.range.endOffset,
    })
  }

  return items
}

function annotationCoversInterval(
  annotation: IntervalAnnotation,
  startOffset: number,
  endOffset: number,
): boolean {
  return (
    annotation.startOffset <= startOffset && annotation.endOffset >= endOffset
  )
}

function activeAnnotationId(
  annotations: readonly IntervalAnnotation[],
  kind: IntervalAnnotation['kind'],
  startOffset: number,
  endOffset: number,
): string | undefined {
  const match = annotations.find(
    (annotation) =>
      annotation.kind === kind &&
      annotationCoversInterval(annotation, startOffset, endOffset),
  )
  return match?.annotationId
}

function appendCommentIconsForEndOffset(
  segments: SourceSentenceAnnotationRenderSegment[],
  rangeComments: readonly SourceAnnotation[],
  endOffset: number,
  emittedCommentIconIds: Set<string>,
): void {
  for (const comment of rangeComments) {
    if (comment.range?.endOffset !== endOffset) {
      continue
    }
    if (emittedCommentIconIds.has(comment.annotationId)) {
      continue
    }
    segments.push({
      kind: 'comment-icon',
      annotationId: comment.annotationId,
    })
    emittedCommentIconIds.add(comment.annotationId)
  }
}

function collectCommentIconsOverlappingEdit(
  rangeComments: readonly SourceAnnotation[],
  editRange: SourceAnnotation['range'],
  emittedCommentIconIds: Set<string>,
): string[] {
  if (!editRange) {
    return []
  }

  const pending = rangeComments
    .filter((comment) => {
      if (!comment.range || emittedCommentIconIds.has(comment.annotationId)) {
        return false
      }
      const commentStart = comment.range.startOffset
      const commentEnd = comment.range.endOffset
      if (commentStart >= editRange.endOffset || commentEnd <= editRange.startOffset) {
        return false
      }
      return commentEnd <= editRange.endOffset
    })
    .sort(
      (left, right) =>
        (left.range?.endOffset ?? 0) - (right.range?.endOffset ?? 0),
    )

  const annotationIds: string[] = []
  for (const comment of pending) {
    annotationIds.push(comment.annotationId)
    emittedCommentIconIds.add(comment.annotationId)
  }
  return annotationIds
}

function appendPlainOrAnnotatedSegment(
  segments: SourceSentenceAnnotationRenderSegment[],
  interval: MergedInterval,
  rawText: string,
  rangeComments: readonly SourceAnnotation[],
  emittedCommentIconIds: Set<string>,
): void {
  const text = sliceByCodePoint(rawText, interval.startOffset, interval.endOffset)
  if (!text) {
    return
  }

  if (interval.highlightAnnotationId || interval.commentAnnotationId) {
    segments.push({
      kind: 'annotated',
      text,
      highlightAnnotationId: interval.highlightAnnotationId,
      commentAnnotationId: interval.commentAnnotationId,
    })
  } else {
    segments.push({ kind: 'plain', text })
  }

  appendCommentIconsForEndOffset(
    segments,
    rangeComments,
    interval.endOffset,
    emittedCommentIconIds,
  )
}

type EditRunPart = {
  startOffset: number
  endOffset: number
  commentAnnotationId?: string
}

function flushEditRun(
  segments: SourceSentenceAnnotationRenderSegment[],
  editAnnotationId: string,
  parts: readonly EditRunPart[],
  rawText: string,
  edits: readonly SourceAnnotation[],
  rangeComments: readonly SourceAnnotation[],
  emittedCommentIconIds: Set<string>,
): void {
  const edit = edits.find((entry) => entry.annotationId === editAnnotationId)
  if (!edit?.range || parts.length === 0) {
    return
  }

  const sourceParts: EditInlineSourcePart[] = parts.map((part) => ({
    text: sliceByCodePoint(rawText, part.startOffset, part.endOffset),
    commentAnnotationId: part.commentAnnotationId,
  }))

  if (!sourceParts.some((part) => part.text)) {
    return
  }

  const commentIconAnnotationIds = collectCommentIconsOverlappingEdit(
    rangeComments,
    edit.range,
    emittedCommentIconIds,
  )

  segments.push({
    kind: 'edit-inline',
    annotationId: editAnnotationId,
    sourceParts,
    ...(commentIconAnnotationIds.length > 0
      ? { commentIconAnnotationIds }
      : {}),
    replacementText: edit.replacementText ?? '',
  })
}

export function buildSourceSentenceAnnotationSegments(
  rawText: string,
  highlights: readonly SourceAnnotation[],
  comments: readonly SourceAnnotation[],
  edits: readonly SourceAnnotation[] = [],
): SourceSentenceAnnotationRenderSegment[] {
  const intervalAnnotations = collectIntervalAnnotations(highlights, comments, edits)
  if (intervalAnnotations.length === 0) {
    return rawText ? [{ kind: 'plain', text: rawText }] : []
  }

  const breakpoints = new Set<number>([0, codePointLength(rawText)])
  for (const annotation of intervalAnnotations) {
    breakpoints.add(annotation.startOffset)
    breakpoints.add(annotation.endOffset)
  }

  const sortedBreakpoints = [...breakpoints].sort((left, right) => left - right)
  const merged: MergedInterval[] = []

  for (let index = 0; index < sortedBreakpoints.length - 1; index += 1) {
    const startOffset = sortedBreakpoints[index]!
    const endOffset = sortedBreakpoints[index + 1]!
    if (endOffset <= startOffset) {
      continue
    }

    const highlightAnnotationId = activeAnnotationId(
      intervalAnnotations,
      'highlight',
      startOffset,
      endOffset,
    )
    const commentAnnotationId = activeAnnotationId(
      intervalAnnotations,
      'comment',
      startOffset,
      endOffset,
    )
    const editAnnotationId = activeAnnotationId(
      intervalAnnotations,
      'edit',
      startOffset,
      endOffset,
    )

    const previous = merged[merged.length - 1]
    if (
      previous &&
      previous.endOffset === startOffset &&
      previous.highlightAnnotationId === highlightAnnotationId &&
      previous.commentAnnotationId === commentAnnotationId &&
      previous.editAnnotationId === editAnnotationId
    ) {
      previous.endOffset = endOffset
      continue
    }

    merged.push({
      startOffset,
      endOffset,
      highlightAnnotationId,
      commentAnnotationId,
      editAnnotationId,
    })
  }

  const segments: SourceSentenceAnnotationRenderSegment[] = []
  const rangeComments = comments.filter(isRangeLevelCommentAnnotation)
  const emittedCommentIconIds = new Set<string>()

  let editRunId: string | undefined
  let editRunParts: EditRunPart[] = []

  const flushCurrentEditRun = () => {
    if (!editRunId) {
      return
    }
    flushEditRun(
      segments,
      editRunId,
      editRunParts,
      rawText,
      edits,
      rangeComments,
      emittedCommentIconIds,
    )
    editRunId = undefined
    editRunParts = []
  }

  for (const interval of merged) {
    if (interval.editAnnotationId) {
      if (editRunId && editRunId !== interval.editAnnotationId) {
        flushCurrentEditRun()
      }
      editRunId = interval.editAnnotationId
      editRunParts.push({
        startOffset: interval.startOffset,
        endOffset: interval.endOffset,
        commentAnnotationId: interval.commentAnnotationId,
      })
      continue
    }

    flushCurrentEditRun()
    appendPlainOrAnnotatedSegment(
      segments,
      interval,
      rawText,
      rangeComments,
      emittedCommentIconIds,
    )
  }

  flushCurrentEditRun()

  return segments
}

export function renderSegmentedSentenceTextContent(
  segments: readonly SourceSentenceAnnotationRenderSegment[],
): string {
  return segments
    .map((segment) => {
      if (segment.kind === 'plain' || segment.kind === 'annotated') {
        return segment.text
      }
      if (segment.kind === 'edit-inline') {
        return segment.sourceParts.map((part) => part.text).join('')
      }
      return ''
    })
    .join('')
}

export function resolveAnnotatedSegmentClassName(
  segment: Extract<SourceSentenceAnnotationRenderSegment, { kind: 'annotated' }>,
  activeSourceAnnotationId: string | null | undefined,
): string {
  return cn(
    segment.highlightAnnotationId &&
      resolveSourceHighlightMarkClassName(
        segment.highlightAnnotationId,
        activeSourceAnnotationId,
      ),
    segment.commentAnnotationId &&
      resolveSourceCommentRangeMarkClassName(
        segment.commentAnnotationId,
        activeSourceAnnotationId,
      ),
  )
}

export function listLegacySentenceComments(
  comments: readonly SourceAnnotation[],
): SourceAnnotation[] {
  return comments.filter(isLegacySentenceCommentAnnotation)
}
