import { useCallback, useMemo } from 'react'

import { ScrollArea } from '@/components/ui/scroll-area'
import { DocumentRenderGroups } from '@/components/review/document-render-groups'
import { SourceDocumentInteraction } from '@/components/review/source-document-interaction'
import { documentReaderScrollAnchorClassName } from '@/lib/document-navigation'
import {
  centeredDocumentCanvasHorizontalClassName,
  fullDocumentSurfaceMaxWidthClassName,
} from '@/lib/document-surface-layout'
import {
  findFirstHeadingIndex,
  groupDocumentBlocks,
  openingSectionClassName,
  splitGroupsAtFirstHeading,
} from '@/lib/document-block-presentation'
import {
  buildCommentAnnotationsBySentenceId,
  buildEditAnnotationsBySentenceId,
  buildHighlightAnnotationsBySentenceId,
} from '@/lib/source-annotation-sentence-index'
import { resolveSourceSentenceAnchor } from '@/lib/source-sentence-anchor'
import type { FocusedSentence } from '@/lib/sentence-navigation-focus'
import type { SourceAnnotation, SourceSentenceAnchor, SourceTextRange } from '@/types/source-annotation'
import type { DocumentView } from '@/types/document-review'
import { cn } from '@/lib/utils'

type DocumentReaderProps = {
  document: DocumentView
  slotId: string
  focusedBlockId?: string | null
  focusedSentence?: FocusedSentence | null
  sourceAnnotations?: Map<string, SourceAnnotation>
  savingAnnotationId?: string | null
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
  activeSourceAnnotationId?: string | null
  onSourceAnnotationActivate?: (annotationId: string) => void
  onClearActiveSourceAnnotation?: () => void
  onClearFocusedSentence?: () => void
  onClearFocusedBlock?: () => void
  contentPlacement?: 'center' | 'expanded'
  /** Opt-in surface cap for canonical Full Document; shared defaults stay unchanged. */
  surfaceWidth?: 'default' | 'full-document'
  /** Gray canvas padding around the white document surface. */
  canvasLayout?: 'default' | 'workspace'
}

export function DocumentReader({
  document,
  slotId,
  focusedBlockId = null,
  focusedSentence = null,
  sourceAnnotations = new Map(),
  savingAnnotationId = null,
  onCreateHighlight: _onCreateHighlight,
  onDeleteHighlight,
  onCreateComment,
  onUpdateComment,
  onDeleteComment,
  onCreateEdit,
  onUpdateEdit,
  onDeleteEdit,
  activeSourceAnnotationId = null,
  onSourceAnnotationActivate,
  onClearActiveSourceAnnotation,
  onClearFocusedSentence,
  onClearFocusedBlock,
  contentPlacement = 'center',
  surfaceWidth = 'default',
  canvasLayout = 'default',
}: DocumentReaderProps) {
  const highlightAnnotationsBySentenceId = useMemo(
    () =>
      buildHighlightAnnotationsBySentenceId(
        sourceAnnotations.values(),
        slotId,
        document.docId,
      ),
    [document.docId, slotId, sourceAnnotations],
  )

  const commentAnnotationsBySentenceId = useMemo(
    () =>
      buildCommentAnnotationsBySentenceId(
        sourceAnnotations.values(),
        slotId,
        document.docId,
      ),
    [document.docId, slotId, sourceAnnotations],
  )

  const editAnnotationsBySentenceId = useMemo(
    () =>
      buildEditAnnotationsBySentenceId(
        sourceAnnotations.values(),
        slotId,
        document.docId,
      ),
    [document.docId, slotId, sourceAnnotations],
  )

  const resolveSentenceAnchor = useCallback(
    (identity: { sentenceId: string }) =>
      resolveSourceSentenceAnchor(slotId, document, identity.sentenceId),
    [document, slotId],
  )

  const firstHeadingIndex = findFirstHeadingIndex(document.blocks)
  const groups = groupDocumentBlocks(document.blocks)
  const { openingGroups, bodyGroups } = splitGroupsAtFirstHeading(
    groups,
    document.blocks,
    firstHeadingIndex,
  )

  return (
    <ScrollArea
      className="h-full min-h-0 w-full min-w-0 flex-1"
      viewportClassName={cn(
        documentReaderScrollAnchorClassName,
        '[&>div]:!block [&>div]:!w-full [&>div]:!min-w-0',
      )}
    >
      <div
        data-document-canvas="true"
        data-document-canvas-layout={canvasLayout}
        className={cn(
          'box-border flex w-full min-w-0 max-w-full',
          canvasLayout === 'workspace'
            ? 'pt-2 pb-6 min-[840px]:sm:pt-2 min-[840px]:sm:pb-8'
            : 'py-6 min-[840px]:sm:py-10',
          contentPlacement === 'expanded'
            ? 'justify-center px-3 min-[840px]:px-4 min-[840px]:sm:px-6'
            : centeredDocumentCanvasHorizontalClassName,
        )}
      >
        <SourceDocumentInteraction
          className="w-full min-w-0 max-w-full"
          sourceAnnotations={sourceAnnotations}
          savingAnnotationId={savingAnnotationId}
          resolveSentenceAnchor={resolveSentenceAnchor}
          activeSourceAnnotationId={activeSourceAnnotationId}
          onSourceAnnotationActivate={onSourceAnnotationActivate}
          onClearActiveSourceAnnotation={onClearActiveSourceAnnotation}
          onClearFocusedSentence={onClearFocusedSentence}
          onClearFocusedBlock={onClearFocusedBlock}
          onCreateHighlight={_onCreateHighlight}
          onDeleteHighlight={onDeleteHighlight}
          onCreateComment={onCreateComment}
          onUpdateComment={onUpdateComment}
          onDeleteComment={onDeleteComment}
          onCreateEdit={onCreateEdit}
          onUpdateEdit={onUpdateEdit}
          onDeleteEdit={onDeleteEdit}
        >
          {(handlers) => (
            <article
              className={cn(
                'document-surface box-border w-full min-w-0 max-w-full rounded-sm bg-white px-6 py-12 shadow-md ring-1 ring-black/5',
                contentPlacement === 'expanded'
                  ? 'mx-auto min-[840px]:max-w-[56rem] min-[840px]:px-10 min-[840px]:sm:px-12 min-[840px]:sm:py-14'
                  : 'mx-auto min-[840px]:px-10 min-[840px]:sm:px-14 min-[840px]:sm:py-16',
                contentPlacement === 'center' && (
                  surfaceWidth === 'full-document'
                    ? fullDocumentSurfaceMaxWidthClassName
                    : 'min-[840px]:max-w-[48rem]'
                ),
              )}
            >
              <div className="document-body text-foreground">
                {openingGroups.length > 0 ? (
                  <div className={openingSectionClassName()}>
                    <DocumentRenderGroups
                      docId={document.docId}
                      groups={openingGroups}
                      allGroups={groups}
                      blocks={document.blocks}
                      firstHeadingIndex={firstHeadingIndex}
                      focusedBlockId={focusedBlockId}
                      focusedSentence={focusedSentence}
                      highlightAnnotationsBySentenceId={highlightAnnotationsBySentenceId}
                      commentAnnotationsBySentenceId={commentAnnotationsBySentenceId}
                      editAnnotationsBySentenceId={editAnnotationsBySentenceId}
                      activeSourceAnnotationId={activeSourceAnnotationId}
                      onPersistedMarkClick={handlers.onPersistedMarkClick}
                      onCommentIconClick={handlers.onCommentIconClick}
                      onEditInlineClick={handlers.onEditInlineClick}
                      keyPrefix="opening"
                    />
                  </div>
                ) : null}

                <DocumentRenderGroups
                  docId={document.docId}
                  groups={bodyGroups}
                  allGroups={groups}
                  blocks={document.blocks}
                  firstHeadingIndex={firstHeadingIndex}
                  focusedBlockId={focusedBlockId}
                  focusedSentence={focusedSentence}
                  highlightAnnotationsBySentenceId={highlightAnnotationsBySentenceId}
                  commentAnnotationsBySentenceId={commentAnnotationsBySentenceId}
                  editAnnotationsBySentenceId={editAnnotationsBySentenceId}
                  activeSourceAnnotationId={activeSourceAnnotationId}
                  onPersistedMarkClick={handlers.onPersistedMarkClick}
                  onCommentIconClick={handlers.onCommentIconClick}
                  onEditInlineClick={handlers.onEditInlineClick}
                  keyPrefix="body"
                />
              </div>
            </article>
          )}
        </SourceDocumentInteraction>
      </div>
    </ScrollArea>
  )
}
