import { DocumentBlockContent } from '@/components/review/document-block-content'
import { blockDomId } from '@/lib/document-anchors'
import { blockNavigationFocusClassName } from '@/lib/block-navigation-focus'
import {
  isBeforeFirstHeading,
  resolveGroupMarginBottom,
  resolveGroupMarginTop,
  tocSectionClassName,
  type DocumentRenderGroup,
} from '@/lib/document-block-presentation'
import type { FocusedSentence } from '@/lib/sentence-navigation-focus'
import type { SourceAnnotation } from '@/types/source-annotation'
import type { DocumentBlock } from '@/types/document-review'
import { cn } from '@/lib/utils'
import type { SentenceMarkedTextPresentation } from '@/components/review/sentence-marked-text'

export type DocumentBlockRenderIdentity = {
  id: string
  'data-block-id': string
  'data-slot-id'?: string
  'data-doc-id'?: string
}

type SharedPresentationProps = {
  focusedBlockId?: string | null
  focusedSentence?: FocusedSentence | null
  highlightAnnotationsBySentenceId?: Map<string, SourceAnnotation[]>
  commentAnnotationsBySentenceId?: Map<string, SourceAnnotation[]>
  editAnnotationsBySentenceId?: Map<string, SourceAnnotation[]>
  activeSourceAnnotationId?: string | null
  onPersistedMarkClick?: (annotationId: string, element: HTMLElement) => void
  onCommentIconClick?: (annotationId: string, element: HTMLElement) => void
  onEditInlineClick?: (annotationId: string, element: HTMLElement) => void
  sentencePresentation?: (sentenceId: string) => SentenceMarkedTextPresentation | undefined
}

export type DocumentRenderGroupsProps = SharedPresentationProps & {
  docId: string
  groups: DocumentRenderGroup[]
  allGroups: DocumentRenderGroup[]
  blocks: DocumentBlock[]
  firstHeadingIndex: number
  keyPrefix: string
  blockIdentity?: (block: DocumentBlock) => DocumentBlockRenderIdentity
  isOpeningContent?: (block: DocumentBlock) => boolean
}

function canonicalBlockIdentity(block: DocumentBlock): DocumentBlockRenderIdentity {
  return {
    id: blockDomId(block.blockId),
    'data-block-id': block.blockId,
  }
}

function ReaderBlock({
  docId,
  block,
  isOpeningContent,
  isFocused,
  blockIdentity,
  ...presentation
}: SharedPresentationProps & {
  docId: string
  block: DocumentBlock
  isOpeningContent: boolean
  isFocused: boolean
  blockIdentity: (block: DocumentBlock) => DocumentBlockRenderIdentity
}) {
  return (
    <section
      {...blockIdentity(block)}
      tabIndex={-1}
      className={blockNavigationFocusClassName(isFocused)}
    >
      <DocumentBlockContent
        docId={docId}
        block={block}
        isOpeningContent={isOpeningContent}
        {...presentation}
      />
    </section>
  )
}

function DocumentRenderGroupView({
  docId,
  group,
  groupIndex,
  groups,
  blocks,
  firstHeadingIndex,
  blockIdentity,
  isOpeningContent,
  focusedBlockId,
  ...presentation
}: Omit<DocumentRenderGroupsProps, 'keyPrefix' | 'allGroups'> & {
  group: DocumentRenderGroup
  groupIndex: number
}) {
  const marginTop = resolveGroupMarginTop(group, groupIndex, groups, firstHeadingIndex, blocks)
  const marginBottom = resolveGroupMarginBottom(group)
  const resolveIdentity = blockIdentity ?? canonicalBlockIdentity

  if (group.kind === 'list') {
    return (
      <ul className={cn('list-disc space-y-1.5 pl-6 marker:text-foreground/70', marginTop, marginBottom)}>
        {group.blocks.map((block) => (
          <li
            key={block.blockId}
            {...resolveIdentity(block)}
            tabIndex={-1}
            className={blockNavigationFocusClassName(focusedBlockId === block.blockId)}
          >
            <DocumentBlockContent
              docId={docId}
              block={block}
              isOpeningContent={false}
              focusedSentence={presentation.focusedSentence}
              highlightAnnotationsBySentenceId={presentation.highlightAnnotationsBySentenceId}
              commentAnnotationsBySentenceId={presentation.commentAnnotationsBySentenceId}
              activeSourceAnnotationId={presentation.activeSourceAnnotationId}
              onPersistedMarkClick={presentation.onPersistedMarkClick}
              onCommentIconClick={presentation.onCommentIconClick}
              sentencePresentation={presentation.sentencePresentation}
            />
          </li>
        ))}
      </ul>
    )
  }

  if (group.kind === 'toc') {
    return (
      <nav aria-label="Table of contents" className={cn(tocSectionClassName(), marginTop, marginBottom)}>
        {group.blocks.map((block, entryIndex) => (
          <section
            key={block.blockId}
            {...resolveIdentity(block)}
            tabIndex={-1}
            className={blockNavigationFocusClassName(focusedBlockId === block.blockId)}
          >
            <DocumentBlockContent
              docId={docId}
              block={block}
              isOpeningContent={false}
              tocEntryIndex={entryIndex}
              focusedSentence={presentation.focusedSentence}
              highlightAnnotationsBySentenceId={presentation.highlightAnnotationsBySentenceId}
              commentAnnotationsBySentenceId={presentation.commentAnnotationsBySentenceId}
              activeSourceAnnotationId={presentation.activeSourceAnnotationId}
              onPersistedMarkClick={presentation.onPersistedMarkClick}
              onCommentIconClick={presentation.onCommentIconClick}
              sentencePresentation={presentation.sentencePresentation}
            />
          </section>
        ))}
      </nav>
    )
  }

  const block = group.block
  const opening = isOpeningContent
    ? isOpeningContent(block)
    : isBeforeFirstHeading(block, blocks, firstHeadingIndex)

  return (
    <div className={cn(marginTop, marginBottom)}>
      <ReaderBlock
        docId={docId}
        block={block}
        isOpeningContent={opening}
        isFocused={focusedBlockId === block.blockId}
        blockIdentity={resolveIdentity}
        {...presentation}
      />
    </div>
  )
}

export function DocumentRenderGroups({
  groups,
  allGroups,
  keyPrefix,
  ...props
}: DocumentRenderGroupsProps) {
  return groups.map((group) => (
    <DocumentRenderGroupView
      key={group.kind === 'single'
        ? `${keyPrefix}-${group.block.blockId}`
        : `${keyPrefix}-${group.kind}-${group.blocks[0]!.blockId}`}
      {...props}
      groups={allGroups}
      group={group}
      groupIndex={allGroups.indexOf(group)}
    />
  ))
}
