import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type MouseEvent,
  type ReactNode,
  type RefObject,
} from 'react'
import { createPortal } from 'react-dom'

import { SourceCommentPopover } from '@/components/review/source-comment-popover'
import { SourceEditPopover } from '@/components/review/source-edit-popover'
import { SourceMarkAction } from '@/components/review/source-mark-action'
import { SourceSelectionToolbar } from '@/components/review/source-selection-toolbar'
import { findSourceCommentForAnchorAndRange } from '@/lib/source-comment'
import { findSourceEditForAnchorAndRange } from '@/lib/source-edit'
import { shouldClearDocumentNavigationFocusOnDocumentMouseUp } from '@/lib/focused-sentence-lifecycle'
import {
  isSourceAnnotationInteractionElement,
  resolveMouseEventInteractionElement,
  shouldClearActiveSourceAnnotationOnDocumentMouseUp,
} from '@/lib/source-annotation-interaction'
import {
  extractSourceTextRangeFromSelection,
  type SourceTextSelectionIdentity,
} from '@/lib/source-text-selection'
import type { SourceAnnotation, SourceSentenceAnchor, SourceTextRange } from '@/types/source-annotation'
import { cn } from '@/lib/utils'

type SelectionActionState =
  | {
      mode: 'selection'
      anchor: SourceSentenceAnchor
      range: SourceTextRange
      top: number
      left: number
    }
  | {
      mode: 'delete-highlight'
      annotationId: string
      top: number
      left: number
    }
  | null

type CommentPopoverState =
  | {
      mode: 'create'
      anchor: SourceSentenceAnchor
      range: SourceTextRange
      top: number
      left: number
    }
  | {
      mode: 'edit'
      annotation: SourceAnnotation
      top: number
      left: number
    }
  | null

type EditPopoverState =
  | {
      mode: 'create'
      anchor: SourceSentenceAnchor
      range: SourceTextRange
      top: number
      left: number
    }
  | {
      mode: 'edit'
      annotation: SourceAnnotation
      top: number
      left: number
    }
  | null

export type SourceDocumentInteractionHandlers = {
  onPersistedMarkClick: (annotationId: string, element: HTMLElement) => void
  onCommentIconClick: (annotationId: string, element: HTMLElement) => void
  onEditInlineClick: (annotationId: string, element: HTMLElement) => void
}

export type SourceDocumentInteractionProps = {
  children: (handlers: SourceDocumentInteractionHandlers) => ReactNode
  className?: string
  interactionRootRef?: RefObject<HTMLElement | null>
  selectionBoundarySelector?: string
  sourceAnnotations: Map<string, SourceAnnotation>
  savingAnnotationId?: string | null
  resolveSentenceAnchor: (identity: SourceTextSelectionIdentity) => SourceSentenceAnchor | null
  activeSourceAnnotationId?: string | null
  onSourceAnnotationActivate?: (annotationId: string) => void
  onClearActiveSourceAnnotation?: () => void
  onClearFocusedSentence?: () => void
  onClearFocusedBlock?: () => void
  onCreateHighlight?: (input: {
    anchor: SourceSentenceAnchor
    range: SourceTextRange
  }) => Promise<void>
  onDeleteHighlight?: (annotationId: string) => Promise<void>
  onCreateComment?: (input: {
    anchor: SourceSentenceAnchor
    range: SourceTextRange
    content: string
  }) => Promise<void>
  onUpdateComment?: (input: {
    annotationId: string
    content: string
  }) => Promise<void>
  onDeleteComment?: (annotationId: string) => Promise<void>
  onCreateEdit?: (input: {
    anchor: SourceSentenceAnchor
    range: SourceTextRange
    replacementText: string
  }) => Promise<void>
  onUpdateEdit?: (input: {
    annotationId: string
    replacementText: string
  }) => Promise<void>
  onDeleteEdit?: (annotationId: string) => Promise<void>
}

export function SourceDocumentInteraction({
  children,
  className,
  interactionRootRef: externalRootRef,
  selectionBoundarySelector,
  sourceAnnotations,
  savingAnnotationId = null,
  resolveSentenceAnchor,
  activeSourceAnnotationId: _activeSourceAnnotationId = null,
  onSourceAnnotationActivate,
  onClearActiveSourceAnnotation,
  onClearFocusedSentence,
  onClearFocusedBlock,
  onCreateHighlight: _onCreateHighlight,
  onDeleteHighlight,
  onCreateComment,
  onUpdateComment,
  onDeleteComment,
  onCreateEdit,
  onUpdateEdit,
  onDeleteEdit,
}: SourceDocumentInteractionProps) {
  const localRootRef = useRef<HTMLDivElement>(null)
  const [selectionAction, setSelectionAction] = useState<SelectionActionState>(null)
  const [commentPopover, setCommentPopover] = useState<CommentPopoverState>(null)
  const [editPopover, setEditPopover] = useState<EditPopoverState>(null)

  const setRootRef = useCallback(
    (element: HTMLDivElement | null) => {
      localRootRef.current = element
      if (externalRootRef) {
        externalRootRef.current = element
      }
    },
    [externalRootRef],
  )

  const dismissSelectionAction = useCallback(() => {
    setSelectionAction(null)
  }, [])

  const dismissCommentPopover = useCallback(() => {
    setCommentPopover(null)
  }, [])

  const dismissEditPopover = useCallback(() => {
    setEditPopover(null)
  }, [])

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target
      if (!(target instanceof HTMLElement)) {
        dismissSelectionAction()
        dismissCommentPopover()
        dismissEditPopover()
        return
      }
      if (target.closest('[data-source-mark-action="true"]')) {
        return
      }
      // Export commits the live draft; outside-click dismissal must not discard it.
      if (target.closest('[data-qc-report-export="true"]')) {
        return
      }
      if (target.closest('[data-source-comment-popover="true"]')) {
        return
      }
      if (target.closest('[data-source-edit-popover="true"]')) {
        return
      }
      if (target.closest('[data-source-comment-icon="true"]')) {
        return
      }
      if (target.closest('[data-source-edit-group="true"]')) {
        return
      }
      dismissSelectionAction()
      dismissCommentPopover()
      dismissEditPopover()
    }
    window.document.addEventListener('pointerdown', handlePointerDown)
    return () => {
      window.document.removeEventListener('pointerdown', handlePointerDown)
    }
  }, [dismissCommentPopover, dismissEditPopover, dismissSelectionAction])


  const openCommentPopoverAtElement = useCallback(
    (annotation: SourceAnnotation, element: HTMLElement) => {
      const rect = element.getBoundingClientRect()
      setCommentPopover({
        mode: 'edit',
        annotation,
        top: rect.bottom + 8,
        left: rect.left,
      })
      dismissSelectionAction()
    },
    [dismissSelectionAction],
  )

  const openCommentPopoverForAnchor = useCallback(
    (
      anchor: SourceSentenceAnchor,
      range: SourceTextRange,
      top: number,
      left: number,
    ) => {
      const existing = findSourceCommentForAnchorAndRange(
        sourceAnnotations,
        anchor,
        range,
      )
      if (existing) {
        setCommentPopover({
          mode: 'edit',
          annotation: existing,
          top,
          left,
        })
        return
      }
      setCommentPopover({
        mode: 'create',
        anchor,
        range,
        top,
        left,
      })
    },
    [sourceAnnotations],
  )

  const openEditPopoverForAnchor = useCallback(
    (
      anchor: SourceSentenceAnchor,
      range: SourceTextRange,
      top: number,
      left: number,
    ) => {
      const existing = findSourceEditForAnchorAndRange(sourceAnnotations, anchor, range)
      if (existing) {
        setEditPopover({
          mode: 'edit',
          annotation: existing,
          top,
          left,
        })
        return
      }
      setEditPopover({
        mode: 'create',
        anchor,
        range,
        top,
        left,
      })
    },
    [sourceAnnotations],
  )

  const openEditPopoverAtElement = useCallback(
    (annotation: SourceAnnotation, element: HTMLElement) => {
      const rect = element.getBoundingClientRect()
      setEditPopover({
        mode: 'edit',
        annotation,
        top: rect.bottom + 8,
        left: rect.left,
      })
      dismissSelectionAction()
    },
    [dismissSelectionAction],
  )

  const clearDocumentNavigationFocusIfNeeded = useCallback(
    (hasValidSourceSelection: boolean, clickedPersistedHighlight: boolean) => {
      if (!onClearFocusedSentence && !onClearFocusedBlock) {
        return
      }
      if (
        shouldClearDocumentNavigationFocusOnDocumentMouseUp({
          clickedPersistedHighlight,
          hasValidSourceSelection,
        })
      ) {
        onClearFocusedSentence?.()
        onClearFocusedBlock?.()
      }
    },
    [onClearFocusedBlock, onClearFocusedSentence],
  )

  const handleDocumentMouseUp = useCallback(
    (event: MouseEvent<HTMLElement>) => {
      const root = localRootRef.current
      const selection = window.getSelection()
      const extracted = extractSourceTextRangeFromSelection(selection, {
        containmentRoot: root,
        selectionBoundarySelector,
      })

      if (extracted.supported) {
        const interactionElement = resolveMouseEventInteractionElement(event.target)
        if (
          interactionElement &&
          shouldClearActiveSourceAnnotationOnDocumentMouseUp(interactionElement)
        ) {
          onClearActiveSourceAnnotation?.()
        }

        clearDocumentNavigationFocusIfNeeded(true, false)

        const anchor = resolveSentenceAnchor({
          sentenceId: extracted.sentenceId,
          slotId: extracted.slotId,
          docId: extracted.docId,
        })
        if (!anchor) {
          return
        }

        const domRange = selection?.rangeCount ? selection.getRangeAt(0) : null
        const rect = domRange?.getBoundingClientRect()
        if (!rect) {
          return
        }

        setSelectionAction({
          mode: 'selection',
          anchor,
          range: extracted.range,
          top: rect.bottom + 8,
          left: rect.left,
        })
        dismissCommentPopover()
        dismissEditPopover()
        return
      }

      const interactionElement = resolveMouseEventInteractionElement(event.target)
      if (!interactionElement) {
        return
      }
      if (isSourceAnnotationInteractionElement(interactionElement)) {
        return
      }

      if (shouldClearActiveSourceAnnotationOnDocumentMouseUp(interactionElement)) {
        onClearActiveSourceAnnotation?.()
      }

      clearDocumentNavigationFocusIfNeeded(false, false)
    },
    [
      clearDocumentNavigationFocusIfNeeded,
      dismissCommentPopover,
      dismissEditPopover,
      onClearActiveSourceAnnotation,
      resolveSentenceAnchor,
      selectionBoundarySelector,
    ],
  )

  const handleCommentIconClick = useCallback(
    (annotationId: string, element: HTMLElement) => {
      const annotation = sourceAnnotations.get(annotationId)
      if (!annotation) {
        return
      }
      onClearFocusedSentence?.()
      onClearFocusedBlock?.()
      onSourceAnnotationActivate?.(annotationId)
      openCommentPopoverAtElement(annotation, element)
    },
    [
      onClearFocusedBlock,
      onClearFocusedSentence,
      onSourceAnnotationActivate,
      openCommentPopoverAtElement,
      sourceAnnotations,
    ],
  )

  const handlePersistedMarkClick = useCallback(
    (annotationId: string, element: HTMLElement) => {
      const rect = element.getBoundingClientRect()
      onClearFocusedSentence?.()
      onClearFocusedBlock?.()
      onSourceAnnotationActivate?.(annotationId)
      setSelectionAction({
        mode: 'delete-highlight',
        annotationId,
        top: rect.bottom + 8,
        left: rect.left,
      })
      dismissCommentPopover()
    },
    [
      dismissCommentPopover,
      onClearFocusedBlock,
      onClearFocusedSentence,
      onSourceAnnotationActivate,
    ],
  )

  const handleEditInlineClick = useCallback(
    (annotationId: string, element: HTMLElement) => {
      const annotation = sourceAnnotations.get(annotationId)
      if (!annotation) {
        return
      }
      onClearFocusedSentence?.()
      onClearFocusedBlock?.()
      onSourceAnnotationActivate?.(annotationId)
      openEditPopoverAtElement(annotation, element)
      dismissCommentPopover()
    },
    [
      dismissCommentPopover,
      onClearFocusedBlock,
      onClearFocusedSentence,
      onSourceAnnotationActivate,
      openEditPopoverAtElement,
      sourceAnnotations,
    ],
  )

  const handleOpenEditFromSelection = useCallback(() => {
    if (!selectionAction || selectionAction.mode !== 'selection') {
      return
    }
    openEditPopoverForAnchor(
      selectionAction.anchor,
      selectionAction.range,
      selectionAction.top,
      selectionAction.left,
    )
    dismissSelectionAction()
    window.getSelection()?.removeAllRanges()
  }, [dismissSelectionAction, openEditPopoverForAnchor, selectionAction])

  const handleDeleteHighlight = useCallback(async () => {
    if (!selectionAction || selectionAction.mode !== 'delete-highlight' || !onDeleteHighlight) {
      return
    }
    await onDeleteHighlight(selectionAction.annotationId)
    dismissSelectionAction()
  }, [dismissSelectionAction, onDeleteHighlight, selectionAction])

  const handleOpenCommentFromSelection = useCallback(() => {
    if (!selectionAction || selectionAction.mode !== 'selection') {
      return
    }
    openCommentPopoverForAnchor(
      selectionAction.anchor,
      selectionAction.range,
      selectionAction.top,
      selectionAction.left,
    )
    dismissSelectionAction()
    window.getSelection()?.removeAllRanges()
  }, [dismissSelectionAction, openCommentPopoverForAnchor, selectionAction])

  const handleSaveEdit = useCallback(
    async (replacementText: string) => {
      if (!editPopover) {
        return
      }
      if (editPopover.mode === 'create') {
        if (!onCreateEdit) {
          return
        }
        await onCreateEdit({
          anchor: editPopover.anchor,
          range: editPopover.range,
          replacementText,
        })
      } else if (onUpdateEdit) {
        await onUpdateEdit({
          annotationId: editPopover.annotation.annotationId,
          replacementText,
        })
      }
      dismissEditPopover()
    },
    [dismissEditPopover, editPopover, onCreateEdit, onUpdateEdit],
  )

  const handleDeleteEdit = useCallback(async () => {
    if (!editPopover || editPopover.mode !== 'edit' || !onDeleteEdit) {
      return
    }
    await onDeleteEdit(editPopover.annotation.annotationId)
    dismissEditPopover()
  }, [dismissEditPopover, editPopover, onDeleteEdit])

  const handleSaveComment = useCallback(
    async (content: string) => {
      if (!commentPopover) {
        return
      }
      if (commentPopover.mode === 'create') {
        if (!onCreateComment) {
          return
        }
        await onCreateComment({
          anchor: commentPopover.anchor,
          range: commentPopover.range,
          content,
        })
      } else if (onUpdateComment) {
        await onUpdateComment({
          annotationId: commentPopover.annotation.annotationId,
          content,
        })
      }
      dismissCommentPopover()
    },
    [commentPopover, dismissCommentPopover, onCreateComment, onUpdateComment],
  )

  const handleDeleteComment = useCallback(async () => {
    if (!commentPopover || commentPopover.mode !== 'edit' || !onDeleteComment) {
      return
    }
    await onDeleteComment(commentPopover.annotation.annotationId)
    dismissCommentPopover()
  }, [commentPopover, dismissCommentPopover, onDeleteComment])

  return (
    <div
      ref={setRootRef}
      data-source-document-interaction="true"
      className={cn('relative', className)}
      onMouseUp={handleDocumentMouseUp}
    >
      {children({
        onPersistedMarkClick: handlePersistedMarkClick,
        onCommentIconClick: handleCommentIconClick,
        onEditInlineClick: handleEditInlineClick,
      })}
      {selectionAction?.mode === 'selection' ? (
        <SourceSelectionToolbar
          top={selectionAction.top}
          left={selectionAction.left}
          editSaving={savingAnnotationId === 'create:edit'}
          commentSaving={savingAnnotationId === 'create:comment'}
          onEdit={handleOpenEditFromSelection}
          onComment={handleOpenCommentFromSelection}
        />
      ) : null}
      {selectionAction?.mode === 'delete-highlight' ? (
        <SourceMarkAction
          label="删除标注"
          top={selectionAction.top}
          left={selectionAction.left}
          disabled={savingAnnotationId === selectionAction.annotationId}
          onClick={() => {
            void handleDeleteHighlight()
          }}
        />
      ) : null}
      {commentPopover
        ? createPortal(
            <SourceCommentPopover
              key={
                commentPopover.mode === 'edit'
                  ? commentPopover.annotation.annotationId
                  : `create:${commentPopover.anchor.sentenceId}`
              }
              mode={commentPopover.mode}
              top={commentPopover.top}
              left={commentPopover.left}
              initialContent={
                commentPopover.mode === 'edit'
                  ? commentPopover.annotation.content ?? ''
                  : ''
              }
              saving={
                savingAnnotationId === 'create:comment' ||
                (commentPopover.mode === 'edit' &&
                  savingAnnotationId === commentPopover.annotation.annotationId)
              }
              deleting={
                commentPopover.mode === 'edit' &&
                savingAnnotationId === `delete:${commentPopover.annotation.annotationId}`
              }
              onCancel={dismissCommentPopover}
              onSave={handleSaveComment}
              onDelete={
                commentPopover.mode === 'edit'
                  ? () => {
                      void handleDeleteComment()
                    }
                  : undefined
              }
            />,
            window.document.body,
          )
        : null}
      {editPopover
        ? createPortal(
            <SourceEditPopover
              key={
                editPopover.mode === 'edit'
                  ? editPopover.annotation.annotationId
                  : `create:${editPopover.anchor.sentenceId}`
              }
              mode={editPopover.mode}
              top={editPopover.top}
              left={editPopover.left}
              initialReplacementText={
                editPopover.mode === 'edit'
                  ? editPopover.annotation.replacementText ?? ''
                  : ''
              }
              saving={
                savingAnnotationId === 'create:edit' ||
                (editPopover.mode === 'edit' &&
                  savingAnnotationId === editPopover.annotation.annotationId)
              }
              deleting={
                editPopover.mode === 'edit' &&
                savingAnnotationId === `delete:${editPopover.annotation.annotationId}`
              }
              onCancel={dismissEditPopover}
              onSave={handleSaveEdit}
              onDelete={
                editPopover.mode === 'edit'
                  ? () => {
                      void handleDeleteEdit()
                    }
                  : undefined
              }
            />,
            window.document.body,
          )
        : null}
    </div>
  )
}
