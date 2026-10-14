import type { KeyboardEvent, MouseEvent } from 'react'

import { sentenceDomId } from '@/lib/document-anchors'
import {
  isRenderableHighlightAnnotation,
} from '@/lib/source-highlight-renderer'
import {
  buildSourceSentenceAnnotationSegments,
  listLegacySentenceComments,
  renderSegmentedSentenceTextContent,
  resolveAnnotatedSegmentClassName,
  resolveEditSourcePartClassName,
} from '@/lib/source-comment-renderer'
import { isRenderableCommentAnnotation } from '@/lib/source-comment'
import { isRenderableEditAnnotation } from '@/lib/source-edit'
import {
  resolveSourceEditGroupClassName,
  resolveSourceEditReplacementClassName,
} from '@/lib/source-edit-renderer'
import {
  clipCommentsToSourceBody,
  clipEditsToSourceBody,
  clipHighlightsToSourceBody,
  splitSentenceTerminalPunctuation,
} from '@/lib/source-sentence-presentation'
import { segmentSentenceText } from '@/lib/sentence-segmentation'
import { SENTENCE_RANGE_ENABLED_ATTRIBUTE } from '@/lib/source-text-selection'
import { shouldActivateFindingTarget } from '@/lib/source-annotation-interaction'
import {
  findingTargetSentenceClassName,
  focusedFindingTargetSentenceClassName,
  isSentenceNavigationFocused,
  sentenceNavigationFocusClassName,
  type FocusedSentence,
} from '@/lib/sentence-navigation-focus'
import { SourceCommentMarker } from '@/components/review/source-comment-marker'
import type { SourceAnnotation } from '@/types/source-annotation'
import type { SentenceView } from '@/types/document-review'
import { cn } from '@/lib/utils'

export type SentenceMarkedTextPresentation = {
  id?: string
  slotId?: string
  docId?: string
  isFindingTarget?: boolean
  isFocusedFindingTarget?: boolean
  onActivate?: () => void
}

type SentenceMarkedTextProps = {
  docId: string
  displayText: string
  sentences?: SentenceView[]
  mode: 'paragraph' | 'whole-block'
  focusedSentence?: FocusedSentence | null
  highlightAnnotationsBySentenceId?: Map<string, SourceAnnotation[]>
  commentAnnotationsBySentenceId?: Map<string, SourceAnnotation[]>
  editAnnotationsBySentenceId?: Map<string, SourceAnnotation[]>
  activeSourceAnnotationId?: string | null
  onPersistedMarkClick?: (annotationId: string, element: HTMLElement) => void
  onCommentIconClick?: (annotationId: string, element: HTMLElement) => void
  onEditInlineClick?: (annotationId: string, element: HTMLElement) => void
  enableRangeSelection?: boolean
  sentencePresentation?: (
    sentenceId: string,
  ) => SentenceMarkedTextPresentation | undefined
}

function sentenceSpanProps(
  docId: string,
  sentenceId: string,
  focusedSentence: FocusedSentence | null | undefined,
  rangeEnabled = false,
  presentation?: SentenceMarkedTextPresentation,
) {
  const isFocused = isSentenceNavigationFocused(focusedSentence, docId, sentenceId)
  const isActivatable = Boolean(presentation?.onActivate)
  return {
    id: presentation?.id ?? sentenceDomId(docId, sentenceId),
    'data-sentence-id': sentenceId,
    'data-slot-id': presentation?.slotId,
    'data-doc-id': presentation?.docId,
    'data-finding-target': presentation?.isFindingTarget ? 'true' : undefined,
    'data-focused-finding-target': presentation?.isFocusedFindingTarget
      ? 'true'
      : undefined,
    ...(rangeEnabled ? { [SENTENCE_RANGE_ENABLED_ATTRIBUTE]: 'true' } : {}),
    role: isActivatable ? 'button' : undefined,
    tabIndex: isActivatable ? 0 : undefined,
    onClick: isActivatable
      ? (event: MouseEvent<HTMLSpanElement>) => {
          if (!shouldActivateFindingTarget(event)) {
            return
          }
          presentation?.onActivate?.()
        }
      : undefined,
    onKeyDown: isActivatable
      ? (event: KeyboardEvent<HTMLSpanElement>) => {
          if (event.key !== 'Enter' && event.key !== ' ') {
            return
          }
          if (!shouldActivateFindingTarget(event)) {
            return
          }
          event.preventDefault()
          presentation?.onActivate?.()
        }
      : undefined,
    className: cn(
      isFocused && sentenceNavigationFocusClassName,
      presentation?.isFindingTarget && findingTargetSentenceClassName,
      presentation?.isFocusedFindingTarget && focusedFindingTargetSentenceClassName,
    ),
  }
}

function renderSentenceInnerText(
  rawText: string,
  highlights: SourceAnnotation[],
  comments: SourceAnnotation[],
  edits: SourceAnnotation[],
  activeSourceAnnotationId: string | null | undefined,
  onPersistedMarkClick?: (annotationId: string, element: HTMLElement) => void,
  onCommentIconClick?: (annotationId: string, element: HTMLElement) => void,
  onEditInlineClick?: (annotationId: string, element: HTMLElement) => void,
) {
  const renderableHighlights = highlights.filter(isRenderableHighlightAnnotation)
  const renderableComments = comments.filter(isRenderableCommentAnnotation)
  const renderableEdits = edits.filter(isRenderableEditAnnotation)
  const segments = buildSourceSentenceAnnotationSegments(
    rawText,
    renderableHighlights,
    renderableComments,
    renderableEdits,
  )

  if (
    segments.length === 1 &&
    segments[0]?.kind === 'plain' &&
    listLegacySentenceComments(renderableComments).length === 0
  ) {
    return rawText
  }

  return segments.map((segment, index) => {
    if (segment.kind === 'plain') {
      return segment.text
    }

    if (segment.kind === 'comment-icon') {
      return (
        <SourceCommentMarker
          key={`${segment.annotationId}-icon-${index}`}
          annotationId={segment.annotationId}
          isActive={activeSourceAnnotationId === segment.annotationId}
          onClick={onCommentIconClick}
        />
      )
    }

    if (segment.kind === 'edit-inline') {
      return (
        <span
          key={`${segment.annotationId}-edit-${index}`}
          data-source-annotation-id={segment.annotationId}
          data-source-edit-group="true"
          className={resolveSourceEditGroupClassName(
            segment.annotationId,
            activeSourceAnnotationId,
          )}
          onClick={(event) => {
            event.stopPropagation()
          }}
          onMouseUp={(event) => {
            const selection = window.getSelection()
            if (selection && !selection.isCollapsed) {
              return
            }
            event.stopPropagation()
            onEditInlineClick?.(segment.annotationId, event.currentTarget)
          }}
        >
          {segment.sourceParts.map((part, partIndex) => (
            <span
              key={`${segment.annotationId}-source-${partIndex}`}
              data-source-edit-source="true"
              data-source-comment-range={
                part.commentAnnotationId ? 'true' : undefined
              }
              className={resolveEditSourcePartClassName(
                part.commentAnnotationId,
                activeSourceAnnotationId,
              )}
            >
              {part.text}
            </span>
          ))}
          {segment.commentIconAnnotationIds?.map((commentIconAnnotationId) => (
            <SourceCommentMarker
              key={`${segment.annotationId}-icon-${commentIconAnnotationId}`}
              annotationId={commentIconAnnotationId}
              isActive={activeSourceAnnotationId === commentIconAnnotationId}
              onClick={onCommentIconClick}
            />
          ))}
          <span
            data-source-annotation-ui="true"
            className={resolveSourceEditReplacementClassName()}
          >
            {segment.replacementText}
          </span>
        </span>
      )
    }

    const persistedAnnotationId =
      segment.commentAnnotationId ?? segment.highlightAnnotationId
    return (
      <span
        key={`${persistedAnnotationId ?? 'annotated'}-${index}`}
        data-source-persisted-mark={segment.highlightAnnotationId ? 'true' : undefined}
        data-source-comment-range={segment.commentAnnotationId ? 'true' : undefined}
        data-source-annotation-id={persistedAnnotationId}
        className={resolveAnnotatedSegmentClassName(segment, activeSourceAnnotationId)}
        onClick={(event) => {
          if (!segment.highlightAnnotationId) {
            return
          }
          event.stopPropagation()
        }}
        onMouseUp={(event) => {
          if (!segment.highlightAnnotationId) {
            return
          }
          event.stopPropagation()
          onPersistedMarkClick?.(segment.highlightAnnotationId, event.currentTarget)
        }}
      >
        {segment.text}
      </span>
    )
  })
}

function renderLegacySentenceComments(
  comments: SourceAnnotation[],
  activeSourceAnnotationId: string | null | undefined,
  onCommentIconClick?: (annotationId: string, element: HTMLElement) => void,
) {
  return listLegacySentenceComments(comments).map((comment) => (
    <SourceCommentMarker
      key={`${comment.annotationId}-legacy`}
      annotationId={comment.annotationId}
      isActive={activeSourceAnnotationId === comment.annotationId}
      onClick={onCommentIconClick}
    />
  ))
}

function renderSentenceWithComment(
  sentenceId: string,
  docId: string,
  text: string,
  highlights: SourceAnnotation[],
  comments: SourceAnnotation[],
  edits: SourceAnnotation[],
  focusedSentence: FocusedSentence | null | undefined,
  activeSourceAnnotationId: string | null | undefined,
  rangeEnabled = false,
  presentation?: SentenceMarkedTextPresentation,
  onPersistedMarkClick?: (annotationId: string, element: HTMLElement) => void,
  onCommentIconClick?: (annotationId: string, element: HTMLElement) => void,
  onEditInlineClick?: (annotationId: string, element: HTMLElement) => void,
) {
  const { sourceBody, terminalPunctuation } = splitSentenceTerminalPunctuation(text)
  const bodyHighlights = clipHighlightsToSourceBody(highlights, sourceBody)
  const bodyComments = clipCommentsToSourceBody(
    comments.filter(isRenderableCommentAnnotation),
    sourceBody,
  )
  const bodyEdits = clipEditsToSourceBody(
    edits.filter(isRenderableEditAnnotation),
    sourceBody,
  )

  return (
    <span className="inline">
      <span
        {...sentenceSpanProps(
          docId,
          sentenceId,
          focusedSentence,
          rangeEnabled,
          presentation,
        )}
      >
        {renderSentenceInnerText(
          sourceBody,
          bodyHighlights,
          bodyComments,
          bodyEdits,
          activeSourceAnnotationId,
          onPersistedMarkClick,
          onCommentIconClick,
          onEditInlineClick,
        )}
        {renderLegacySentenceComments(
          comments,
          activeSourceAnnotationId,
          onCommentIconClick,
        )}
        {terminalPunctuation}
      </span>
    </span>
  )
}

export function SentenceMarkedText({
  docId,
  displayText,
  sentences,
  mode,
  focusedSentence = null,
  highlightAnnotationsBySentenceId,
  commentAnnotationsBySentenceId,
  editAnnotationsBySentenceId,
  activeSourceAnnotationId = null,
  onPersistedMarkClick,
  onCommentIconClick,
  onEditInlineClick,
  enableRangeSelection = true,
  sentencePresentation,
}: SentenceMarkedTextProps) {
  if (!sentences || sentences.length === 0) {
    return displayText
  }

  const highlightsFor = (sentenceId: string) =>
    highlightAnnotationsBySentenceId?.get(sentenceId) ?? []

  const commentsFor = (sentenceId: string) =>
    commentAnnotationsBySentenceId?.get(sentenceId) ?? []

  const editsFor = (sentenceId: string) =>
    editAnnotationsBySentenceId?.get(sentenceId) ?? []

  if (mode === 'whole-block') {
    if (sentences.length !== 1) {
      return displayText
    }

    const sentence = sentences[0]!
    const highlights = highlightsFor(sentence.sentenceId)
    const comments = commentsFor(sentence.sentenceId)
    const edits = editsFor(sentence.sentenceId)
    const visibleText =
      highlights.some(isRenderableHighlightAnnotation) ||
      comments.some(isRenderableCommentAnnotation) ||
      edits.some(isRenderableEditAnnotation)
        ? sentence.rawText
        : displayText
    return renderSentenceWithComment(
      sentence.sentenceId,
      docId,
      visibleText,
      highlights,
      comments,
      edits,
      focusedSentence,
      activeSourceAnnotationId,
      false,
      sentencePresentation?.(sentence.sentenceId),
      onPersistedMarkClick,
      onCommentIconClick,
      onEditInlineClick,
    )
  }

  const segmentation = segmentSentenceText(displayText, sentences)
  if (!segmentation.available) {
    return displayText
  }

  return (
    <>
      {segmentation.segments.map((segment) => {
        if (segment.kind === 'gap') {
          return segment.text
        }

        return (
          <span key={segment.sentenceId}>
            {renderSentenceWithComment(
              segment.sentenceId,
              docId,
              segment.text,
              highlightsFor(segment.sentenceId),
              commentsFor(segment.sentenceId),
              editsFor(segment.sentenceId),
              focusedSentence,
              activeSourceAnnotationId,
              enableRangeSelection,
              sentencePresentation?.(segment.sentenceId),
              onPersistedMarkClick,
              onCommentIconClick,
              onEditInlineClick,
            )}
          </span>
        )
      })}
    </>
  )
}

export { renderSegmentedSentenceTextContent as reconstructSentenceSourceText }
