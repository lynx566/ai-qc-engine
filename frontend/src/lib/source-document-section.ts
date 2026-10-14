import type { DocumentBlock, DocumentView } from '@/types/document-review'

export class SourceDocumentSectionError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'SourceDocumentSectionError'
  }
}

export type SourceDocumentSectionRange = {
  startBlockIndex: number
  endBlockIndexExclusive: number
  sectionHeadingSourceBlockId: string | null
}

export function resolveSourceHeadingLevel(block: DocumentBlock): number {
  return block.headingLevel ?? Math.max(1, block.headingPath.length)
}

export function findFirstHeadingBlockIndex(
  blocks: readonly DocumentBlock[],
): number | null {
  const index = blocks.findIndex((block) => block.kind === 'heading')
  return index >= 0 ? index : null
}

/** Source Evidence display range; canonical Full Document keeps all blocks. */
export function resolveSourceSectionForHeading(
  blocks: readonly DocumentBlock[],
  headingBlockIndex: number,
): SourceDocumentSectionRange {
  const heading = blocks[headingBlockIndex]
  if (!heading || heading.kind !== 'heading') {
    throw new SourceDocumentSectionError(
      `expected heading block at index ${headingBlockIndex}`,
    )
  }

  const startLevel = resolveSourceHeadingLevel(heading)
  let endBlockIndexExclusive = blocks.length
  for (let index = headingBlockIndex + 1; index < blocks.length; index += 1) {
    const candidate = blocks[index]
    if (candidate.kind === 'toc') {
      endBlockIndexExclusive = index
      break
    }
    if (candidate.kind !== 'heading') {
      continue
    }
    if (resolveSourceHeadingLevel(candidate) <= startLevel) {
      endBlockIndexExclusive = index
      break
    }
  }

  return {
    startBlockIndex: headingBlockIndex,
    endBlockIndexExclusive,
    sectionHeadingSourceBlockId: heading.sourceBlockId,
  }
}

function collectHeadingAncestryForBlock(
  blocks: readonly DocumentBlock[],
  blockIndex: number,
): number[] {
  const headingStack: Array<{ blockIndex: number; level: number }> = []
  for (let index = 0; index <= blockIndex; index += 1) {
    const block = blocks[index]
    if (block.kind !== 'heading') {
      continue
    }
    const level = resolveSourceHeadingLevel(block)
    while (headingStack.length > 0 && headingStack.at(-1)!.level >= level) {
      headingStack.pop()
    }
    headingStack.push({ blockIndex: index, level })
  }
  return headingStack.map((entry) => entry.blockIndex)
}

export function resolveContainingSourceSection(
  document: DocumentView,
  blockIndex: number,
): SourceDocumentSectionRange {
  return resolveContainingSourceSectionFromBlocks(document.blocks, blockIndex)
}

export function resolveContainingSourceSectionFromBlocks(
  blocks: readonly DocumentBlock[],
  blockIndex: number,
): SourceDocumentSectionRange {
  if (blockIndex < 0 || blockIndex >= blocks.length) {
    throw new SourceDocumentSectionError(`invalid block index ${blockIndex}`)
  }

  const block = blocks[blockIndex]!
  if (block.kind === 'heading') {
    return resolveSourceSectionForHeading(blocks, blockIndex)
  }

  const headingAncestry = collectHeadingAncestryForBlock(blocks, blockIndex)
  if (headingAncestry.length === 0) {
    return {
      startBlockIndex: 0,
      endBlockIndexExclusive: findFirstHeadingBlockIndex(blocks) ?? blocks.length,
      sectionHeadingSourceBlockId: null,
    }
  }

  return resolveSourceSectionForHeading(blocks, headingAncestry.at(-1)!)
}
