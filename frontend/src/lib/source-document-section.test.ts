import { describe, expect, it } from 'vitest'

import { resolveContainingSourceSection } from '@/lib/source-document-section'
import type { DocumentBlock, DocumentView } from '@/types/document-review'

function block(
  sourceBlockId: string,
  kind: DocumentBlock['kind'],
  docOrderIndex: number,
  headingLevel?: DocumentBlock['headingLevel'],
): DocumentBlock {
  return {
    blockId: `doc-a:${sourceBlockId}`,
    sourceBlockId,
    kind,
    docOrderIndex,
    headingLevel,
    headingPath: [],
    displayText: sourceBlockId,
    sentences: [{
      sentenceId: `${sourceBlockId}:S001`,
      rawText: sourceBlockId,
      normalizedText: sourceBlockId,
    }],
  }
}

function document(blocks: DocumentBlock[]): DocumentView {
  return {
    docId: 'doc-a',
    fileName: 'doc-a.docx',
    displayName: 'Document A',
    blocks,
  }
}

describe('resolveContainingSourceSection', () => {
  const source = document([
    block('OPENING', 'paragraph', 0),
    block('H1', 'heading', 1, 1),
    block('P1', 'paragraph', 2),
    block('H2', 'heading', 3, 2),
    block('P2', 'paragraph', 4),
    block('H3', 'heading', 5, 3),
    block('P3', 'paragraph', 6),
    block('H2B', 'heading', 7, 2),
    block('P4', 'paragraph', 8),
    block('H1B', 'heading', 9, 1),
  ])

  it('uses the nearest innermost heading for paragraph evidence', () => {
    expect(resolveContainingSourceSection(source, 6)).toEqual({
      sectionHeadingSourceBlockId: 'H3',
      startBlockIndex: 5,
      endBlockIndexExclusive: 7,
    })
  })

  it.each([0, 2])('stops the 执行概要 context before TOC for evidence at index %i', (evidenceIndex) => {
    const sourceWithToc = document([
      { ...block('H', 'heading', 0, 1), displayText: '执行概要' },
      block('C1', 'paragraph', 1),
      block('C2', 'paragraph', 2),
      block('M1', 'toc', 3),
      block('M2', 'toc', 4),
      { ...block('NEXT', 'heading', 5, 1), displayText: '前言' },
    ])

    const range = resolveContainingSourceSection(sourceWithToc, evidenceIndex)
    expect(range).toEqual({
      sectionHeadingSourceBlockId: 'H',
      startBlockIndex: 0,
      endBlockIndexExclusive: 3,
    })
    expect(sourceWithToc.blocks.slice(range.startBlockIndex, range.endBlockIndexExclusive)
      .map((entry) => entry.sourceBlockId)).toEqual(['H', 'C1', 'C2'])
  })

  it('includes descendant subsections until a peer or ancestor heading', () => {
    expect(resolveContainingSourceSection(source, 3)).toEqual({
      sectionHeadingSourceBlockId: 'H2',
      startBlockIndex: 3,
      endBlockIndexExclusive: 7,
    })
  })

  it('uses a heading evidence block as its own section start', () => {
    expect(resolveContainingSourceSection(source, 1)).toEqual({
      sectionHeadingSourceBlockId: 'H1',
      startBlockIndex: 1,
      endBlockIndexExclusive: 9,
    })
  })

  it('maps content before the first heading to the opening section', () => {
    expect(resolveContainingSourceSection(source, 0)).toEqual({
      sectionHeadingSourceBlockId: null,
      startBlockIndex: 0,
      endBlockIndexExclusive: 1,
    })
  })

  it('maps a no-heading document to the whole document', () => {
    const sourceWithoutHeadings = document([
      block('P1', 'paragraph', 0),
      block('P2', 'paragraph', 1),
    ])

    expect(resolveContainingSourceSection(sourceWithoutHeadings, 1)).toEqual({
      sectionHeadingSourceBlockId: null,
      startBlockIndex: 0,
      endBlockIndexExclusive: 2,
    })
  })
})
