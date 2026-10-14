import { describe, expect, it } from 'vitest'

import { deriveFindingSourceViewportState } from '@/lib/finding-source-viewport-state'
import type { InternalResultEvidenceRef } from '@/types/document-consistency-qc'
import type { DocumentView } from '@/types/document-review'

const documentView: DocumentView = {
  docId: 'doc-a',
  fileName: 'doc-a.docx',
  displayName: 'Document A',
  blocks: [
    {
      blockId: 'doc-a:H1', sourceBlockId: 'H1', kind: 'heading', docOrderIndex: 0,
      headingLevel: 1, headingPath: ['Section'], displayText: 'Section',
      sentences: [{ sentenceId: 'H1:S1', rawText: 'Section', normalizedText: 'Section' }],
    },
    {
      blockId: 'doc-a:P1', sourceBlockId: 'P1', kind: 'paragraph', docOrderIndex: 1,
      headingPath: ['Section'], displayText: 'Alpha. Beta.',
      sentences: [
        { sentenceId: 'P1:S1', rawText: 'Alpha.', normalizedText: 'Alpha.' },
        { sentenceId: 'P1:S2', rawText: 'Beta.', normalizedText: 'Beta.' },
      ],
    },
  ],
}

function evidence(sentenceId: string, docId = 'doc-a'): InternalResultEvidenceRef {
  return {
    slotId: 'source', docId, blockId: 'P1', sentenceId, sentenceAlias: sentenceId,
  }
}

describe('deriveFindingSourceViewportState', () => {
  it('returns empty only when the finding has no evidence occurrences', () => {
    expect(deriveFindingSourceViewportState({
      findingId: 'finding-a', slotId: 'source', document: documentView, evidenceLocations: [],
    })).toEqual({ kind: 'empty' })
  })

  it('returns one canonically ordered descriptor per evidence occurrence including exact duplicates', () => {
    const locations = [evidence('P1:S1'), evidence('P1:S2'), evidence('P1:S1')]
    const state = deriveFindingSourceViewportState({
      findingId: 'finding-a', slotId: 'source', document: documentView, evidenceLocations: locations,
    })

    expect(state.kind).toBe('ready')
    if (state.kind !== 'ready') return
    expect(state.descriptors).toHaveLength(3)
    expect(state.descriptors.map((item) => item.evidenceSentenceId)).toEqual([
      'P1:S1', 'P1:S1', 'P1:S2',
    ])
    expect(new Set(state.descriptors.map((item) => item.viewportKey)).size).toBe(3)
  })

  it('makes a mixed valid and invalid evidence list wholly unavailable', () => {
    expect(deriveFindingSourceViewportState({
      findingId: 'finding-a',
      slotId: 'source',
      document: documentView,
      evidenceLocations: [evidence('P1:S1'), evidence('P1:S2', 'doc-b')],
    })).toEqual({ kind: 'unavailable' })
  })

  it('returns unavailable when evidence references another loaded document', () => {
    expect(deriveFindingSourceViewportState({
      findingId: 'finding-a',
      slotId: 'source',
      document: documentView,
      evidenceLocations: [evidence('P1:S1', 'doc-b')],
    })).toEqual({ kind: 'unavailable' })
  })

  it('returns unavailable when a sentence cannot be resolved in the active document', () => {
    expect(deriveFindingSourceViewportState({
      findingId: 'finding-a',
      slotId: 'source',
      document: documentView,
      evidenceLocations: [evidence('P1:S999')],
    })).toEqual({ kind: 'unavailable' })
  })

  it('returns eight ordered descriptors for eight evidence occurrences', () => {
    const locations = Array.from({ length: 8 }, (_, index) => ({
      ...evidence(index % 2 === 0 ? 'P1:S1' : 'P1:S2'),
      sentenceAlias: `T${index + 1}`,
    }))
    const state = deriveFindingSourceViewportState({
      findingId: 'finding-a',
      slotId: 'source',
      document: documentView,
      evidenceLocations: locations,
    })
    expect(state.kind).toBe('ready')
    if (state.kind !== 'ready') return
    expect(state.descriptors).toHaveLength(8)
  })
})
