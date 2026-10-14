import { useMemo } from 'react'

import { DocumentRenderGroups } from '@/components/review/document-render-groups'
import type { SourceDocumentInteractionHandlers } from '@/components/review/source-document-interaction'
import {
  findFirstHeadingIndex,
  groupDocumentBlocks,
} from '@/lib/document-block-presentation'
import {
  sourceBlockIdentityAttributes,
  sourceBlockRenderId,
  sourceSentenceRenderId,
} from '@/lib/source-evidence-viewport'
import {
  buildCommentAnnotationsBySentenceId,
  buildEditAnnotationsBySentenceId,
  buildHighlightAnnotationsBySentenceId,
} from '@/lib/source-annotation-sentence-index'
import type { SourceAnnotation } from '@/types/source-annotation'
import type { DocumentView } from '@/types/document-review'

export type SourceSectionReaderProps = {
  document: DocumentView
  slotId: string
  viewportKey: string
  sectionStartBlockIndex: number
  sectionEndBlockIndexExclusive: number
  primaryEvidenceSentenceId: string
  /** When set, drops the leading section heading block already shown in viewport chrome. */
  omitLeadingSectionHeadingSourceBlockId?: string | null
  compactViewportPresentation?: boolean
  sourceAnnotations?: Map<string, SourceAnnotation>
  activeSourceAnnotationId?: string | null
  interactionHandlers?: SourceDocumentInteractionHandlers
}

const emptySourceAnnotations = new Map<string, SourceAnnotation>()

export function SourceSectionReader({
  document,
  slotId,
  viewportKey,
  sectionStartBlockIndex,
  sectionEndBlockIndexExclusive,
  primaryEvidenceSentenceId,
  omitLeadingSectionHeadingSourceBlockId = null,
  compactViewportPresentation = false,
  sourceAnnotations,
  activeSourceAnnotationId = null,
  interactionHandlers,
}: SourceSectionReaderProps) {
  const annotations = sourceAnnotations ?? emptySourceAnnotations
  const highlightAnnotationsBySentenceId = useMemo(
    () => buildHighlightAnnotationsBySentenceId(annotations.values(), slotId, document.docId),
    [annotations, document.docId, slotId],
  )
  const commentAnnotationsBySentenceId = useMemo(
    () => buildCommentAnnotationsBySentenceId(
      annotations.values(),
      slotId,
      document.docId,
    ),
    [annotations, document.docId, slotId],
  )
  const editAnnotationsBySentenceId = useMemo(
    () => buildEditAnnotationsBySentenceId(
      annotations.values(),
      slotId,
      document.docId,
    ),
    [annotations, document.docId, slotId],
  )

  const sectionBlocks = useMemo(() => {
    const blocks = document.blocks.slice(
      sectionStartBlockIndex,
      sectionEndBlockIndexExclusive,
    )
    if (
      !omitLeadingSectionHeadingSourceBlockId ||
      blocks.length <= 1 ||
      blocks[0]?.sourceBlockId !== omitLeadingSectionHeadingSourceBlockId
    ) {
      return blocks
    }
    return blocks.slice(1)
  }, [
    document.blocks,
    omitLeadingSectionHeadingSourceBlockId,
    sectionEndBlockIndexExclusive,
    sectionStartBlockIndex,
  ])
  const groups = groupDocumentBlocks(sectionBlocks)
  const firstHeadingIndex = findFirstHeadingIndex(sectionBlocks)
  const documentFirstHeadingIndex = findFirstHeadingIndex(document.blocks)

  return (
    <article
      data-source-section-reader="true"
      className={compactViewportPresentation
        ? 'document-surface box-border w-full min-w-0 max-w-full bg-transparent px-3 py-2'
        : 'document-surface box-border w-full min-w-0 max-w-full bg-white px-5 py-6'}
    >
      <div
        data-source-canonical-body="true"
        className={compactViewportPresentation
          ? 'document-body text-sm text-foreground'
          : 'document-body text-foreground'}
      >
        <DocumentRenderGroups
          docId={document.docId}
          groups={groups}
          allGroups={groups}
          blocks={sectionBlocks}
          firstHeadingIndex={firstHeadingIndex}
          keyPrefix={viewportKey}
          blockIdentity={(block) => ({
            id: sourceBlockRenderId(viewportKey, block.sourceBlockId),
            ...sourceBlockIdentityAttributes({
              slotId,
              documentId: document.docId,
              sourceBlockId: block.sourceBlockId,
            }),
          })}
          isOpeningContent={(block) => {
            const sourceIndex = document.blocks.indexOf(block)
            return documentFirstHeadingIndex >= 0 && sourceIndex < documentFirstHeadingIndex
          }}
          highlightAnnotationsBySentenceId={highlightAnnotationsBySentenceId}
          commentAnnotationsBySentenceId={commentAnnotationsBySentenceId}
          editAnnotationsBySentenceId={editAnnotationsBySentenceId}
          activeSourceAnnotationId={activeSourceAnnotationId}
          onPersistedMarkClick={interactionHandlers?.onPersistedMarkClick}
          onCommentIconClick={interactionHandlers?.onCommentIconClick}
          onEditInlineClick={interactionHandlers?.onEditInlineClick}
          sentencePresentation={(sentenceId) => ({
            id: sourceSentenceRenderId(viewportKey, document.docId, sentenceId),
            slotId,
            docId: document.docId,
            isFindingTarget: sentenceId === primaryEvidenceSentenceId,
            isFocusedFindingTarget: sentenceId === primaryEvidenceSentenceId,
          })}
        />
      </div>
    </article>
  )
}
