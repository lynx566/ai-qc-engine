import type { ReactNode } from 'react'

import {
  SentenceMarkedText,
  type SentenceMarkedTextPresentation,
} from '@/components/review/sentence-marked-text'
import { applyPresentationToClassName } from '@/lib/block-presentation-styles'
import { selectSourceAnnotationsForBlock } from '@/lib/source-annotation-sentence-index'
import {
  headingClassName,
  listItemClassName,
  paragraphClassName,
  tableCaptionClassName,
  tableNoteClassName,
  tocEntryClassName,
  tocEntryLeaderClassName,
  tocEntryPageClassName,
  tocEntryRowClassName,
} from '@/lib/document-block-presentation'
import { parseTocEntryText } from '@/lib/toc-entry'
import type { FocusedSentence } from '@/lib/sentence-navigation-focus'
import type { SourceAnnotation } from '@/types/source-annotation'
import type { DocumentBlock, SentenceView } from '@/types/document-review'
import { cn } from '@/lib/utils'

export function DocumentTableBlock({
  table,
}: {
  table: NonNullable<DocumentBlock['table']>
}) {
  const [headerRow, ...bodyRows] = table.rows
  if (!headerRow) {
    return null
  }

  return (
    <div className="max-w-full overflow-x-auto">
      <table className="w-full min-w-[28rem] border-collapse text-left text-[14px] leading-relaxed">
        <thead>
          <tr className="border-b-2 border-border bg-muted/30">
            {headerRow.map((cell, index) => (
              <th
                key={`header-${index}`}
                className="px-3 py-2.5 align-top font-semibold text-foreground"
              >
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {bodyRows.map((row, rowIndex) => (
            <tr
              key={`row-${rowIndex}`}
              className="border-b border-border/70 last:border-b-0"
            >
              {row.map((cell, cellIndex) => (
                <td
                  key={`cell-${rowIndex}-${cellIndex}`}
                  className="px-3 py-2.5 align-top text-foreground/90 break-words"
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TocEntryContent({
  block,
  isSectionTitle,
}: {
  block: DocumentBlock
  isSectionTitle: boolean
}) {
  const parsed = parseTocEntryText(block.displayText ?? '')
  const { className, style } = applyPresentationToClassName(
    tocEntryClassName(isSectionTitle),
    block.presentation,
    { includeTocLevelIndent: !isSectionTitle },
  )

  if (isSectionTitle || !parsed.pageNumber) {
    return <p className={className} style={style}>{parsed.title}</p>
  }

  return (
    <p className={cn(className, tocEntryRowClassName())} style={style}>
      <span className="min-w-0 shrink">{parsed.title}</span>
      <span className={tocEntryLeaderClassName()} aria-hidden="true" />
      <span className={tocEntryPageClassName()}>{parsed.pageNumber}</span>
    </p>
  )
}

function PresentedText({
  as: Tag,
  block,
  semanticClassName,
  includeTocLevelIndent = false,
  children,
}: {
  as: 'p' | 'h1' | 'h2' | 'h3' | 'h4' | 'span'
  block: DocumentBlock
  semanticClassName: string
  includeTocLevelIndent?: boolean
  children: ReactNode
}) {
  const { className, style } = applyPresentationToClassName(
    semanticClassName,
    block.presentation,
    { includeTocLevelIndent },
  )
  return <Tag className={className} style={style}>{children}</Tag>
}

export type DocumentBlockContentProps = {
  docId: string
  block: DocumentBlock
  isOpeningContent: boolean
  tocEntryIndex?: number
  focusedSentence?: FocusedSentence | null
  highlightAnnotationsBySentenceId?: Map<string, SourceAnnotation[]>
  commentAnnotationsBySentenceId?: Map<string, SourceAnnotation[]>
  editAnnotationsBySentenceId?: Map<string, SourceAnnotation[]>
  activeSourceAnnotationId?: string | null
  onPersistedMarkClick?: (annotationId: string, element: HTMLElement) => void
  onCommentIconClick?: (annotationId: string, element: HTMLElement) => void
  onEditInlineClick?: (annotationId: string, element: HTMLElement) => void
  displayTextOverride?: string
  sentencesOverride?: readonly SentenceView[]
  enableRangeSelection?: boolean
  sentencePresentation?: (
    sentenceId: string,
  ) => SentenceMarkedTextPresentation | undefined
}

export function DocumentBlockContent({
  docId,
  block,
  isOpeningContent,
  tocEntryIndex,
  focusedSentence,
  highlightAnnotationsBySentenceId,
  commentAnnotationsBySentenceId,
  editAnnotationsBySentenceId,
  activeSourceAnnotationId,
  onPersistedMarkClick,
  onCommentIconClick,
  onEditInlineClick,
  displayTextOverride,
  sentencesOverride,
  enableRangeSelection = true,
  sentencePresentation,
}: DocumentBlockContentProps) {
  const displayText = displayTextOverride ?? block.displayText ?? ''
  const sentences = sentencesOverride ? [...sentencesOverride] : block.sentences
  const markedTextProps = {
    docId,
    focusedSentence,
    highlightAnnotationsBySentenceId: selectSourceAnnotationsForBlock(
      highlightAnnotationsBySentenceId,
      block.sourceBlockId,
    ),
    commentAnnotationsBySentenceId: selectSourceAnnotationsForBlock(
      commentAnnotationsBySentenceId,
      block.sourceBlockId,
    ),
    editAnnotationsBySentenceId: selectSourceAnnotationsForBlock(
      editAnnotationsBySentenceId,
      block.sourceBlockId,
    ),
    activeSourceAnnotationId,
    onPersistedMarkClick,
    onCommentIconClick,
    onEditInlineClick,
    enableRangeSelection,
    sentencePresentation,
  }

  if (block.kind === 'table' && block.table) {
    return <DocumentTableBlock table={block.table} />
  }

  if (block.kind === 'heading') {
    const level = block.headingLevel ?? 2
    const markedText = (
      <SentenceMarkedText
        {...markedTextProps}
        displayText={displayText}
        sentences={sentences}
        mode="whole-block"
      />
    )
    const tag = level === 1 ? 'h1' : level === 3 ? 'h3' : level >= 4 ? 'h4' : 'h2'
    return (
      <PresentedText as={tag} block={block} semanticClassName={headingClassName(level)}>
        {markedText}
      </PresentedText>
    )
  }

  if (block.kind === 'toc') {
    return <TocEntryContent block={block} isSectionTitle={tocEntryIndex === 0} />
  }

  if (block.kind === 'list_item') {
    return (
      <PresentedText as="span" block={block} semanticClassName={listItemClassName()}>
        <SentenceMarkedText {...markedTextProps} displayText={displayText} sentences={sentences} mode="whole-block" />
      </PresentedText>
    )
  }

  if (block.kind === 'table_caption' || block.kind === 'table_note') {
    return (
      <PresentedText
        as="p"
        block={block}
        semanticClassName={block.kind === 'table_caption' ? tableCaptionClassName() : tableNoteClassName()}
      >
        <SentenceMarkedText {...markedTextProps} displayText={displayText} sentences={sentences} mode="whole-block" />
      </PresentedText>
    )
  }

  return (
    <PresentedText as="p" block={block} semanticClassName={paragraphClassName(isOpeningContent)}>
      <SentenceMarkedText {...markedTextProps} displayText={displayText} sentences={sentences} mode="paragraph" />
    </PresentedText>
  )
}
