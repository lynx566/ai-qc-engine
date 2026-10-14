import { describe, expect, it } from 'vitest'

import type { DocumentBlock } from '@/types/document-review'
import {
  findFirstHeadingIndex,
  groupDocumentBlocks,
  isBeforeFirstHeading,
  resolveGroupMarginTop,
  splitGroupsAtFirstHeading,
} from '@/lib/document-block-presentation'

function makeBlock(
  overrides: Partial<DocumentBlock> & Pick<DocumentBlock, 'blockId' | 'kind'>,
): DocumentBlock {
  return {
    docOrderIndex: overrides.docOrderIndex ?? 0,
    headingPath: [],
    ...overrides,
  }
}

describe('groupDocumentBlocks', () => {
  it('groups consecutive list items and toc entries', () => {
    const blocks: DocumentBlock[] = [
      makeBlock({ blockId: 'a', kind: 'paragraph', docOrderIndex: 0 }),
      makeBlock({ blockId: 'b', kind: 'list_item', docOrderIndex: 1 }),
      makeBlock({ blockId: 'c', kind: 'list_item', docOrderIndex: 2 }),
      makeBlock({ blockId: 'd', kind: 'toc', docOrderIndex: 3 }),
      makeBlock({ blockId: 'e', kind: 'toc', docOrderIndex: 4 }),
      makeBlock({ blockId: 'f', kind: 'heading', docOrderIndex: 5, headingLevel: 1 }),
    ]

    const groups = groupDocumentBlocks(blocks)

    expect(groups).toEqual([
      { kind: 'single', block: blocks[0] },
      { kind: 'list', blocks: [blocks[1], blocks[2]] },
      { kind: 'toc', blocks: [blocks[3], blocks[4]] },
      { kind: 'single', block: blocks[5] },
    ])
  })
})

describe('findFirstHeadingIndex', () => {
  it('returns the first heading block index', () => {
    const blocks: DocumentBlock[] = [
      makeBlock({ blockId: 'a', kind: 'paragraph', docOrderIndex: 0 }),
      makeBlock({ blockId: 'b', kind: 'toc', docOrderIndex: 1 }),
      makeBlock({ blockId: 'c', kind: 'heading', docOrderIndex: 2, headingLevel: 1 }),
    ]

    expect(findFirstHeadingIndex(blocks)).toBe(2)
  })

  it('returns -1 when no heading exists', () => {
    const blocks: DocumentBlock[] = [
      makeBlock({ blockId: 'a', kind: 'paragraph', docOrderIndex: 0 }),
    ]

    expect(findFirstHeadingIndex(blocks)).toBe(-1)
  })
})

describe('isBeforeFirstHeading', () => {
  it('detects opening content before the first heading', () => {
    const blocks: DocumentBlock[] = [
      makeBlock({ blockId: 'a', kind: 'paragraph', docOrderIndex: 0 }),
      makeBlock({ blockId: 'b', kind: 'paragraph', docOrderIndex: 1 }),
      makeBlock({ blockId: 'c', kind: 'heading', docOrderIndex: 2, headingLevel: 1 }),
    ]

    expect(isBeforeFirstHeading(blocks[0]!, blocks, 2)).toBe(true)
    expect(isBeforeFirstHeading(blocks[2]!, blocks, 2)).toBe(false)
  })
})

describe('resolveGroupMarginTop', () => {
  it('keeps table caption, table, and note visually grouped', () => {
    const caption = makeBlock({ blockId: 'cap', kind: 'table_caption', docOrderIndex: 0 })
    const table = makeBlock({
      blockId: 'tbl',
      kind: 'table',
      docOrderIndex: 1,
      table: { rows: [['A'], ['1']] },
    })
    const note = makeBlock({ blockId: 'note', kind: 'table_note', docOrderIndex: 2 })

    const groups = groupDocumentBlocks([caption, table, note])

    expect(
      resolveGroupMarginTop(groups[1]!, 1, groups, 3, [caption, table, note]),
    ).toBe('mt-1')
    expect(
      resolveGroupMarginTop(groups[2]!, 2, groups, 3, [caption, table, note]),
    ).toBe('mt-1.5')
  })

  it('splits groups into opening and body sections at the first heading', () => {
    const paragraph = makeBlock({ blockId: 'p', kind: 'paragraph', docOrderIndex: 0 })
    const toc = makeBlock({ blockId: 't', kind: 'toc', docOrderIndex: 1 })
    const heading = makeBlock({
      blockId: 'h',
      kind: 'heading',
      docOrderIndex: 2,
      headingLevel: 1,
    })

    const groups = groupDocumentBlocks([paragraph, toc, heading])

    expect(splitGroupsAtFirstHeading(groups, [paragraph, toc, heading], 2)).toEqual({
      openingGroups: groups.slice(0, 2),
      bodyGroups: groups.slice(2),
    })
  })

  it('adds larger top spacing before heading level 1 after body content', () => {
    const paragraph = makeBlock({ blockId: 'p', kind: 'paragraph', docOrderIndex: 0 })
    const heading = makeBlock({
      blockId: 'h',
      kind: 'heading',
      docOrderIndex: 1,
      headingLevel: 1,
    })

    const groups = groupDocumentBlocks([paragraph, heading])

    expect(
      resolveGroupMarginTop(groups[1]!, 1, groups, 1, [paragraph, heading]),
    ).toBe('mt-10')
  })
})
