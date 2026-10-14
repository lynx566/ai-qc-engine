import type { DocumentBlock } from '@/types/document-review'
import { cn } from '@/lib/utils'

export type DocumentRenderGroup =
  | { kind: 'single'; block: DocumentBlock }
  | { kind: 'list'; blocks: DocumentBlock[] }
  | { kind: 'toc'; blocks: DocumentBlock[] }

export function findFirstHeadingIndex(blocks: DocumentBlock[]): number {
  return blocks.findIndex((block) => block.kind === 'heading')
}

export function groupDocumentBlocks(blocks: DocumentBlock[]): DocumentRenderGroup[] {
  const groups: DocumentRenderGroup[] = []
  let index = 0

  while (index < blocks.length) {
    const block = blocks[index]!

    if (block.kind === 'list_item') {
      const listBlocks: DocumentBlock[] = [block]
      index += 1
      while (index < blocks.length && blocks[index]!.kind === 'list_item') {
        listBlocks.push(blocks[index]!)
        index += 1
      }
      groups.push({ kind: 'list', blocks: listBlocks })
      continue
    }

    if (block.kind === 'toc') {
      const tocBlocks: DocumentBlock[] = [block]
      index += 1
      while (index < blocks.length && blocks[index]!.kind === 'toc') {
        tocBlocks.push(blocks[index]!)
        index += 1
      }
      groups.push({ kind: 'toc', blocks: tocBlocks })
      continue
    }

    groups.push({ kind: 'single', block })
    index += 1
  }

  return groups
}

function lastBlockInGroup(group: DocumentRenderGroup): DocumentBlock {
  if (group.kind === 'single') {
    return group.block
  }
  return group.blocks[group.blocks.length - 1]!
}

export function isBeforeFirstHeading(
  block: DocumentBlock,
  blocks: DocumentBlock[],
  firstHeadingIndex: number,
): boolean {
  if (firstHeadingIndex < 0) {
    return false
  }
  const blockIndex = blocks.findIndex((candidate) => candidate.blockId === block.blockId)
  return blockIndex >= 0 && blockIndex < firstHeadingIndex
}

export function resolveGroupMarginTop(
  group: DocumentRenderGroup,
  groupIndex: number,
  groups: DocumentRenderGroup[],
  firstHeadingIndex: number,
  blocks: DocumentBlock[],
): string {
  if (groupIndex === 0) {
    return ''
  }

  const prevGroup = groups[groupIndex - 1]!
  const prevBlock = lastBlockInGroup(prevGroup)
  const currentBlock =
    group.kind === 'single' ? group.block : group.blocks[0]!

  if (group.kind === 'single' && currentBlock.kind === 'table') {
    if (prevBlock.kind === 'table_caption') {
      return 'mt-1'
    }
  }

  if (group.kind === 'single' && currentBlock.kind === 'table_note') {
    if (prevBlock.kind === 'table') {
      return 'mt-1.5'
    }
  }

  if (group.kind === 'single' && currentBlock.kind === 'table_caption') {
    return 'mt-6'
  }

  if (prevBlock.kind === 'table_note' || prevBlock.kind === 'table') {
    return 'mt-5'
  }

  if (group.kind === 'toc') {
    return 'mt-5'
  }

  if (group.kind === 'single' && currentBlock.kind === 'heading') {
    const level = currentBlock.headingLevel ?? 2
    if (level === 1) {
      return groupIndex === 0 || isBeforeFirstHeading(currentBlock, blocks, firstHeadingIndex)
        ? 'mt-0'
        : 'mt-10'
    }
    if (level === 2) {
      return 'mt-8'
    }
    if (level === 3) {
      return 'mt-6'
    }
    return 'mt-5'
  }

  if (
    group.kind === 'single' &&
    currentBlock.kind === 'paragraph' &&
    isBeforeFirstHeading(currentBlock, blocks, firstHeadingIndex)
  ) {
    return 'mt-3'
  }

  if (group.kind === 'list') {
    return 'mt-3'
  }

  if (group.kind === 'single') {
    return 'mt-3'
  }

  return 'mt-4'
}

export function resolveGroupMarginBottom(group: DocumentRenderGroup): string {
  if (group.kind === 'single') {
    const block = group.block
    if (block.kind === 'heading') {
      const level = block.headingLevel ?? 2
      if (level === 1) {
        return 'mb-3'
      }
      if (level === 2) {
        return 'mb-2.5'
      }
      return 'mb-2'
    }
    if (block.kind === 'table_caption') {
      return 'mb-0'
    }
    if (block.kind === 'table') {
      return 'mb-0'
    }
    if (block.kind === 'table_note') {
      return 'mb-1'
    }
    if (block.kind === 'toc') {
      return 'mb-0'
    }
  }

  if (group.kind === 'toc') {
    return 'mb-2'
  }

  if (group.kind === 'list') {
    return 'mb-1'
  }

  return 'mb-0'
}

export function splitGroupsAtFirstHeading(
  groups: DocumentRenderGroup[],
  blocks: DocumentBlock[],
  firstHeadingIndex: number,
): { openingGroups: DocumentRenderGroup[]; bodyGroups: DocumentRenderGroup[] } {
  if (firstHeadingIndex < 0) {
    return { openingGroups: [], bodyGroups: groups }
  }

  const firstHeadingBlockId = blocks[firstHeadingIndex]!.blockId
  const splitIndex = groups.findIndex(
    (group) => group.kind === 'single' && group.block.blockId === firstHeadingBlockId,
  )

  if (splitIndex < 0) {
    return { openingGroups: groups, bodyGroups: [] }
  }

  return {
    openingGroups: groups.slice(0, splitIndex),
    bodyGroups: groups.slice(splitIndex),
  }
}

export function headingClassName(level: number | undefined): string {
  const resolvedLevel = level ?? 2

  return cn(
    'text-foreground tracking-tight',
    resolvedLevel === 1 &&
      'border-b border-border/70 pb-2 text-[1.375rem] font-bold leading-tight',
    resolvedLevel === 2 && 'text-[1.25rem] font-semibold leading-snug',
    resolvedLevel === 3 && 'text-[1.125rem] font-semibold leading-snug',
    resolvedLevel >= 4 && 'text-base font-medium leading-snug',
  )
}

export function paragraphClassName(isOpeningContent: boolean): string {
  return cn(
    'text-base leading-7 text-foreground whitespace-pre-wrap',
    isOpeningContent && 'leading-8',
  )
}

export function openingSectionClassName(): string {
  return 'opening-content mb-10 space-y-1 border-b border-border/70 pb-10'
}

export function tocSectionClassName(): string {
  return 'space-y-0.5'
}

export function tocEntryClassName(isFirstInGroup: boolean): string {
  return cn(
    'text-[14px] leading-relaxed text-foreground',
    isFirstInGroup && 'mb-4 text-center text-base font-semibold tracking-wide',
  )
}

export function tocEntryRowClassName(): string {
  return 'flex min-w-0 items-baseline gap-1'
}

export function tocEntryLeaderClassName(): string {
  return 'mx-1 min-w-[1rem] flex-1 border-b border-dotted border-foreground/30'
}

export function tocEntryPageClassName(): string {
  return 'shrink-0 tabular-nums text-foreground/80'
}

export function listItemClassName(): string {
  return 'text-base leading-7 text-foreground pl-1'
}

export function tableCaptionClassName(): string {
  return 'text-[15px] font-semibold leading-snug text-foreground'
}

export function tableNoteClassName(): string {
  return 'text-[13px] leading-relaxed text-muted-foreground italic'
}

export function filterOverlayClassName(isSelected: boolean): string {
  return cn(
    'scroll-mt-8 rounded-sm transition-colors',
    isSelected && 'border-l-2 border-primary/50 bg-primary/[0.04] pl-3 -ml-3',
  )
}
