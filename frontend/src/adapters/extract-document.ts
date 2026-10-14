import type {
  ExtractBlockDto,
  ExtractBlockPresentationDto,
  ExtractBundleDto,
} from '@/adapters/extract-bundle.dto'
import type {
  BlockPresentation,
  BlockPresentationAlignment,
  DocumentBlock,
  DocumentBlockKind,
  DocumentView,
  SentenceView,
  TableView,
} from '@/types/document-review'

export class ExtractDocumentAdapterError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ExtractDocumentAdapterError'
  }
}

const BODY_COLLECTIONS = [
  'front_matter_blocks',
  'content_blocks',
  'table_blocks',
] as const

const DISPLAY_BLOCK_KINDS = new Set<DocumentBlockKind>([
  'heading',
  'paragraph',
  'list_item',
  'toc',
  'table_caption',
  'table_note',
  'table',
])

const PRESENTATION_ALIGNMENTS = new Set<BlockPresentationAlignment>([
  'left',
  'center',
  'right',
  'justify',
])

export function composeDocumentBlockId(docId: string, extractBlockId: string) {
  return `${docId}:${extractBlockId}`
}

export function collectBodyBlocks(bundle: ExtractBundleDto): ExtractBlockDto[] {
  const blocks: ExtractBlockDto[] = []

  for (const collection of BODY_COLLECTIONS) {
    const collectionBlocks = bundle[collection] ?? []
    blocks.push(...collectionBlocks)
  }

  return blocks
}

export function assertCanonicalDocOrderIndexes(blocks: ExtractBlockDto[]) {
  const seen = new Set<number>()

  for (const block of blocks) {
    const index = block.doc_order_index

    if (index === null || index === undefined) {
      throw new ExtractDocumentAdapterError(
        `Block ${block.block_id} is missing doc_order_index in body collections.`,
      )
    }

    if (seen.has(index)) {
      throw new ExtractDocumentAdapterError(
        `Duplicate doc_order_index ${index} in body collections.`,
      )
    }

    seen.add(index)
  }
}

export function sortBodyBlocksByDocOrderIndex(
  blocks: ExtractBlockDto[],
): ExtractBlockDto[] {
  return [...blocks].sort((left, right) => {
    const leftIndex = left.doc_order_index
    const rightIndex = right.doc_order_index

    if (leftIndex === null || leftIndex === undefined) {
      throw new ExtractDocumentAdapterError(
        `Block ${left.block_id} is missing doc_order_index.`,
      )
    }

    if (rightIndex === null || rightIndex === undefined) {
      throw new ExtractDocumentAdapterError(
        `Block ${right.block_id} is missing doc_order_index.`,
      )
    }

    return leftIndex - rightIndex
  })
}

export function resolveHeadingDisplayText(block: ExtractBlockDto): string {
  if (block.kind !== 'heading') {
    throw new ExtractDocumentAdapterError(
      `resolveHeadingDisplayText called for non-heading block ${block.block_id}.`,
    )
  }

  const headingPath = block.heading_path ?? []
  const recoveredFromPath =
    headingPath.length > 0 &&
    headingPath[headingPath.length - 1] !== block.raw_text

  if (recoveredFromPath) {
    return headingPath[headingPath.length - 1]!
  }

  return block.raw_text
}

function mapSentences(block: ExtractBlockDto): SentenceView[] | undefined {
  if (!block.sentences || block.sentences.length === 0) {
    return undefined
  }

  return block.sentences.map((sentence) => ({
    sentenceId: sentence.sentence_id,
    rawText: sentence.raw_text,
    normalizedText: sentence.normalized_text,
  }))
}

function mapTable(block: ExtractBlockDto): TableView {
  const rawRows = block.meta?.raw_rows

  if (!rawRows || rawRows.length === 0) {
    throw new ExtractDocumentAdapterError(
      `Table block ${block.block_id} is missing meta.raw_rows.`,
    )
  }

  return { rows: rawRows.map((row) => [...row]) }
}

function toDocumentBlockKind(kind: string, blockId: string): DocumentBlockKind {
  if (!DISPLAY_BLOCK_KINDS.has(kind as DocumentBlockKind)) {
    throw new ExtractDocumentAdapterError(
      `Unsupported display block kind "${kind}" for block ${blockId}.`,
    )
  }

  return kind as DocumentBlockKind
}

function readFiniteNumber(value: unknown): number | undefined {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return undefined
  }
  return value
}

function readBoolean(value: unknown): boolean | undefined {
  if (typeof value === 'boolean') {
    return value
  }
  return undefined
}

function readPositiveInteger(value: unknown): number | undefined {
  if (typeof value !== 'number' || !Number.isInteger(value) || value < 1) {
    return undefined
  }
  return value
}

function mapPresentation(
  raw: ExtractBlockPresentationDto | undefined,
): BlockPresentation | undefined {
  if (!raw || typeof raw !== 'object') {
    return undefined
  }

  const presentation: BlockPresentation = {}

  if (
    typeof raw.alignment === 'string' &&
    PRESENTATION_ALIGNMENTS.has(raw.alignment as BlockPresentationAlignment)
  ) {
    presentation.alignment = raw.alignment
  }

  const fontSizePt = readFiniteNumber(raw.font_size_pt)
  if (fontSizePt !== undefined) {
    presentation.font_size_pt = fontSizePt
  }

  const bold = readBoolean(raw.bold)
  if (bold !== undefined) {
    presentation.bold = bold
  }

  const italic = readBoolean(raw.italic)
  if (italic !== undefined) {
    presentation.italic = italic
  }

  const indentFirstLinePt = readFiniteNumber(raw.indent_first_line_pt)
  if (indentFirstLinePt !== undefined) {
    presentation.indent_first_line_pt = indentFirstLinePt
  }

  const indentLeftPt = readFiniteNumber(raw.indent_left_pt)
  if (indentLeftPt !== undefined) {
    presentation.indent_left_pt = indentLeftPt
  }

  const lineSpacingMultiple = readFiniteNumber(raw.line_spacing_multiple)
  if (lineSpacingMultiple !== undefined) {
    presentation.line_spacing_multiple = lineSpacingMultiple
  }

  const spaceBeforePt = readFiniteNumber(raw.space_before_pt)
  if (spaceBeforePt !== undefined) {
    presentation.space_before_pt = spaceBeforePt
  }

  const spaceAfterPt = readFiniteNumber(raw.space_after_pt)
  if (spaceAfterPt !== undefined) {
    presentation.space_after_pt = spaceAfterPt
  }

  const tocLevel = readPositiveInteger(raw.toc_level)
  if (tocLevel !== undefined) {
    presentation.toc_level = tocLevel
  }

  return Object.keys(presentation).length > 0 ? presentation : undefined
}

function resolveHeadingLevel(
  block: ExtractBlockDto,
): 1 | 2 | 3 | 4 | 5 | 6 | 7 | undefined {
  const level = block.meta?.heading_level

  if (level === undefined) {
    return undefined
  }

  if (!Number.isInteger(level) || level < 1 || level > 7) {
    throw new ExtractDocumentAdapterError(
      `Block ${block.block_id} has invalid heading_level ${String(level)}.`,
    )
  }

  return level as 1 | 2 | 3 | 4 | 5 | 6 | 7
}

export function mapExtractBlockToDocumentBlock(
  docId: string,
  block: ExtractBlockDto,
): DocumentBlock {
  const kind = toDocumentBlockKind(block.kind, block.block_id)
  const docOrderIndex = block.doc_order_index

  if (docOrderIndex === null || docOrderIndex === undefined) {
    throw new ExtractDocumentAdapterError(
      `Block ${block.block_id} is missing doc_order_index.`,
    )
  }

  const mapped: DocumentBlock = {
    blockId: composeDocumentBlockId(docId, block.block_id),
    sourceBlockId: block.block_id,
    kind,
    docOrderIndex,
    headingPath: [...(block.heading_path ?? [])],
    sentences: mapSentences(block),
    presentation: mapPresentation(block.meta?.presentation),
  }

  if (kind === 'heading') {
    mapped.displayText = resolveHeadingDisplayText(block)
    mapped.headingLevel = resolveHeadingLevel(block)
    return mapped
  }

  if (kind === 'table') {
    mapped.table = mapTable(block)
    return mapped
  }

  mapped.displayText = block.raw_text
  return mapped
}

export { mapPresentation }

export function adaptExtractBundleToDocumentView(
  bundle: ExtractBundleDto,
): DocumentView {
  if (!bundle.doc_id) {
    throw new ExtractDocumentAdapterError('Extract bundle is missing doc_id.')
  }

  const bodyBlocks = collectBodyBlocks(bundle)
  assertCanonicalDocOrderIndexes(bodyBlocks)

  const sortedBlocks = sortBodyBlocksByDocOrderIndex(bodyBlocks)

  return {
    docId: bundle.doc_id,
    fileName: bundle.file_name,
    displayName: bundle.display_name,
    blocks: sortedBlocks.map((block) =>
      mapExtractBlockToDocumentBlock(bundle.doc_id, block),
    ),
  }
}
