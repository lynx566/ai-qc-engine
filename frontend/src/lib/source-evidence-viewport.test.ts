// @vitest-environment happy-dom

import { beforeEach, describe, expect, it } from 'vitest'

import {
  deriveSourceEvidenceViewportDescriptors,
  findSourceBlockWithinRoot,
  findSourceSentenceWithinRoot,
  sourceBlockRenderId,
  sourceBlockIdentityAttributes,
  sourceSentenceRenderId,
  sourceSentenceIdentityAttributes,
} from '@/lib/source-evidence-viewport'
import type { InternalResultEvidenceRef } from '@/types/document-consistency-qc'
import type { DocumentBlock, DocumentView } from '@/types/document-review'

function heading(sourceBlockId: string, index: number): DocumentBlock {
  return {
    blockId: `doc-a:${sourceBlockId}`,
    sourceBlockId,
    kind: 'heading',
    docOrderIndex: index,
    headingLevel: 1,
    headingPath: [sourceBlockId],
    displayText: sourceBlockId,
    sentences: [{
      sentenceId: `${sourceBlockId}:S001`,
      rawText: sourceBlockId,
      normalizedText: sourceBlockId,
    }],
  }
}

function paragraph(sourceBlockId: string, index: number, sentenceCount = 1): DocumentBlock {
  const sentences = Array.from({ length: sentenceCount }, (_, sentenceIndex) => ({
    sentenceId: `${sourceBlockId}:S${sentenceIndex + 1}`,
    rawText: `${sourceBlockId} sentence ${sentenceIndex + 1}`,
    normalizedText: `${sourceBlockId} sentence ${sentenceIndex + 1}`,
  }))
  return {
    blockId: `doc-a:${sourceBlockId}`,
    sourceBlockId,
    kind: 'paragraph',
    docOrderIndex: index,
    headingPath: ['Section'],
    displayText: sentences.map((sentence) => sentence.rawText).join(' '),
    sentences,
  }
}

const sourceDocument: DocumentView = {
  docId: 'doc-a',
  fileName: 'doc-a.docx',
  displayName: 'Document A',
  blocks: [
    heading('H1', 0),
    paragraph('P1', 1, 4),
    paragraph('P2', 2, 4),
    heading('H2', 3),
  ],
}

function evidence(
  blockId: string,
  sentenceId: string,
  sentenceAlias: string,
): InternalResultEvidenceRef {
  return {
    slotId: 'source',
    docId: 'doc-a',
    blockId,
    sentenceId,
    sentenceAlias,
  }
}

describe('deriveSourceEvidenceViewportDescriptors', () => {
  it('orders raw model aliases by canonical block and sentence position without mutating refs', () => {
    const aliases = ['T0014', 'T0017', 'T0026', 'T0069', 'T0080', 'T0086']
    const document: DocumentView = {
      ...sourceDocument,
      blocks: [
        heading('H1', 0),
        paragraph('P1', 1, 3),
        heading('H2', 2),
        paragraph('P2', 3, 3),
      ],
    }
    const canonicalRefs = aliases.map((alias, index) => evidence(
      index < 3 ? 'P1' : 'P2',
      `${index < 3 ? 'P1' : 'P2'}:S${index % 3 + 1}`,
      alias,
    ))
    const refs = [0, 5, 1, 2, 3, 4].map((index) => canonicalRefs[index]!)
    const inputOrder = [...refs]
    const project = (evidenceLocations: readonly InternalResultEvidenceRef[]) =>
      deriveSourceEvidenceViewportDescriptors({
        findingId: 'finding-a', slotId: 'source', document, evidenceLocations,
      })

    const descriptors = project(refs)
    expect(descriptors.map((item) => item.evidenceSentenceId)).toEqual(
      canonicalRefs.map((ref) => ref.sentenceId),
    )
    expect(descriptors).toEqual(project(canonicalRefs))
    expect(descriptors).toHaveLength(refs.length)
    expect(new Set(descriptors.map((item) => item.viewportKey)).size).toBe(refs.length)
    expect(descriptors.map((item) => item.sectionHeadingSourceBlockId)).toEqual([
      'H1', 'H1', 'H1', 'H2', 'H2', 'H2',
    ])
    expect(refs).toEqual(inputOrder)
  })

  it('uses numeric canonical source position rather than alias or sentence-id order', () => {
    const document = { ...sourceDocument, blocks: [heading('H1', 0), paragraph('P1', 2, 12)] }
    const refs = [
      evidence('P1', 'P1:S10', 'T0001'),
      evidence('P1', 'P1:S2', 'T0099'),
    ]
    const descriptors = deriveSourceEvidenceViewportDescriptors({
      findingId: 'finding-a', slotId: 'source', document, evidenceLocations: refs,
    })
    expect(descriptors.map((item) => item.evidenceSentenceId)).toEqual(['P1:S2', 'P1:S10'])
  })

  it('sorts duplicate anchors stably while keeping every occurrence and its viewport key', () => {
    const duplicate = evidence('P1', 'P1:S1', 'T0001')
    const project = (evidenceLocations: InternalResultEvidenceRef[]) =>
      deriveSourceEvidenceViewportDescriptors({
        findingId: 'finding-a', slotId: 'source', document: sourceDocument, evidenceLocations,
      })
    const canonical = project([duplicate, { ...duplicate }, evidence('P2', 'P2:S1', 'T0002')])
    const reordered = project([evidence('P2', 'P2:S1', 'T0002'), duplicate, { ...duplicate }])
    expect(reordered).toEqual(canonical)
    expect(reordered).toHaveLength(3)
    expect(new Set(reordered.map((item) => item.viewportKey)).size).toBe(3)
  })

  it.each([
    { slotId: 'other-slot' },
    { docId: 'other-document' },
  ])('rejects evidence outside the current document/slot: %s', (identity) => {
    expect(() => deriveSourceEvidenceViewportDescriptors({
      findingId: 'finding-a', slotId: 'source', document: sourceDocument,
      evidenceLocations: [{ ...evidence('P1', 'P1:S1', 'T0001'), ...identity }],
    })).toThrow('does not belong to loaded document')
  })

  it('creates exactly one descriptor for each of eight evidence occurrences', () => {
    const evidenceLocations = [
      evidence('P1', 'P1:S1', 'T1'),
      evidence('P1', 'P1:S2', 'T2'),
      evidence('P1', 'P1:S3', 'T3'),
      evidence('P1', 'P1:S4', 'T4'),
      evidence('P2', 'P2:S1', 'T5'),
      evidence('P2', 'P2:S2', 'T6'),
      evidence('P2', 'P2:S3', 'T7'),
      evidence('P2', 'P2:S4', 'T8'),
    ]

    const descriptors = deriveSourceEvidenceViewportDescriptors({
      findingId: 'finding-a',
      slotId: 'source',
      document: sourceDocument,
      evidenceLocations,
    })

    expect(descriptors).toHaveLength(8)
    expect(descriptors.map((descriptor) => descriptor.evidenceSentenceId)).toEqual([
      'P1:S1', 'P1:S2', 'P1:S3', 'P1:S4',
      'P2:S1', 'P2:S2', 'P2:S3', 'P2:S4',
    ])
  })

  it('keeps same-section evidence as separate viewport instances', () => {
    const descriptors = deriveSourceEvidenceViewportDescriptors({
      findingId: 'finding-a',
      slotId: 'source',
      document: sourceDocument,
      evidenceLocations: [
        evidence('P1', 'P1:S1', 'T1'),
        evidence('P2', 'P2:S2', 'T2'),
      ],
    })

    expect(descriptors).toHaveLength(2)
    expect(descriptors[0]).toMatchObject({
      sourceBlockId: 'P1',
      sourceBlockIndex: 1,
      evidenceSentenceId: 'P1:S1',
      evidenceSentenceIndex: 0,
      sectionHeadingSourceBlockId: 'H1',
      sectionStartBlockIndex: 0,
      sectionEndBlockIndexExclusive: 3,
    })
    expect(descriptors[1]).toMatchObject({
      sourceBlockId: 'P2',
      sourceBlockIndex: 2,
      evidenceSentenceId: 'P2:S2',
      evidenceSentenceIndex: 1,
      sectionHeadingSourceBlockId: 'H1',
      sectionStartBlockIndex: 0,
      sectionEndBlockIndexExclusive: 3,
    })
    expect(descriptors[0]!.viewportKey).not.toBe(descriptors[1]!.viewportKey)
  })

  it('assigns stable unique viewport keys to exact duplicate source occurrences', () => {
    const duplicate = evidence('P1', 'P1:S1', 'T1')
    const input = {
      findingId: 'finding-a',
      slotId: 'source',
      document: sourceDocument,
      evidenceLocations: [duplicate, { ...duplicate }],
    }

    const first = deriveSourceEvidenceViewportDescriptors(input)
    const second = deriveSourceEvidenceViewportDescriptors(input)

    expect(first).toHaveLength(2)
    expect(first[0]!.evidenceLocationKey).toBe(first[1]!.evidenceLocationKey)
    expect(first[0]!.viewportKey).not.toBe(first[1]!.viewportKey)
    expect(first.map((descriptor) => descriptor.viewportKey)).toEqual(
      second.map((descriptor) => descriptor.viewportKey),
    )
  })
})

describe('source evidence viewport render identity', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it('generates different DOM ids for the same source in different viewports', () => {
    expect(sourceBlockRenderId('viewport-a', 'P1')).not.toBe(
      sourceBlockRenderId('viewport-b', 'P1'),
    )
    expect(sourceSentenceRenderId('viewport-a', 'doc-a', 'P1:S1')).not.toBe(
      sourceSentenceRenderId('viewport-b', 'doc-a', 'P1:S1'),
    )
    expect(sourceBlockIdentityAttributes({
      slotId: 'source',
      documentId: 'doc-a',
      sourceBlockId: 'P1',
    })).toEqual({
      'data-slot-id': 'source',
      'data-doc-id': 'doc-a',
      'data-block-id': 'P1',
    })
    expect(sourceSentenceIdentityAttributes({
      slotId: 'source',
      documentId: 'doc-a',
      sentenceId: 'P1:S1',
    })).toEqual({
      'data-slot-id': 'source',
      'data-doc-id': 'doc-a',
      'data-sentence-id': 'P1:S1',
    })
  })

  it('finds duplicate source identities only inside the supplied root', () => {
    const rootA = document.createElement('div')
    const rootB = document.createElement('div')
    const blockA = document.createElement('section')
    const blockB = document.createElement('section')
    const sentenceA = document.createElement('span')
    const sentenceB = document.createElement('span')

    for (const blockElement of [blockA, blockB]) {
      blockElement.dataset.slotId = 'source'
      blockElement.dataset.docId = 'doc-a'
      blockElement.dataset.blockId = 'P1'
    }
    for (const sentenceElement of [sentenceA, sentenceB]) {
      sentenceElement.dataset.slotId = 'source'
      sentenceElement.dataset.docId = 'doc-a'
      sentenceElement.dataset.sentenceId = 'P1:S1'
    }
    rootA.append(blockA, sentenceA)
    rootB.append(blockB, sentenceB)
    document.body.append(rootA, rootB)

    expect(findSourceBlockWithinRoot(rootA, {
      slotId: 'source',
      documentId: 'doc-a',
      sourceBlockId: 'P1',
    })).toBe(blockA)
    expect(findSourceBlockWithinRoot(rootB, {
      slotId: 'source',
      documentId: 'doc-a',
      sourceBlockId: 'P1',
    })).toBe(blockB)
    expect(findSourceSentenceWithinRoot(rootA, {
      slotId: 'source',
      documentId: 'doc-a',
      sentenceId: 'P1:S1',
    })).toBe(sentenceA)
    expect(findSourceSentenceWithinRoot(rootB, {
      slotId: 'source',
      documentId: 'doc-a',
      sentenceId: 'P1:S1',
    })).toBe(sentenceB)
  })
})
