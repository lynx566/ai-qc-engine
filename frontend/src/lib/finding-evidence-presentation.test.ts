import { describe, expect, it } from 'vitest'

import { composeDocumentBlockId } from '@/adapters/extract-document'
import {
  buildDocumentEvidenceIndexes,
  projectFindingEvidence,
} from '@/lib/finding-evidence-presentation'
import type { InternalResultEvidenceRef } from '@/types/document-consistency-qc'
import type { DocumentView } from '@/types/document-review'

const document: DocumentView = {
  docId: 'doc_test',
  fileName: 'sample.docx',
  displayName: 'sample.docx',
  blocks: [
    {
      blockId: composeDocumentBlockId('doc_test', 'C0020'),
      kind: 'heading',
      docOrderIndex: 20,
      headingLevel: 1,
      headingPath: ['20. 结论'],
      displayText: '20. 结论',
    },
    {
      blockId: composeDocumentBlockId('doc_test', 'C0021'),
      kind: 'paragraph',
      docOrderIndex: 21,
      headingPath: ['20. 结论'],
      displayText: '结论段落',
      sentences: [
        {
          sentenceId: 'C0021:S001',
          rawText: '原句 A',
          normalizedText: '原句 A',
        },
        {
          sentenceId: 'C0021:S002',
          rawText: '原句 B',
          normalizedText: '原句 B',
        },
      ],
    },
    {
      blockId: composeDocumentBlockId('doc_test', 'C0019'),
      kind: 'heading',
      docOrderIndex: 19,
      headingLevel: 1,
      headingPath: ['19. 重要风险总结'],
      displayText: '19. 重要风险总结',
    },
    {
      blockId: composeDocumentBlockId('doc_test', 'C0019P'),
      kind: 'paragraph',
      docOrderIndex: 22,
      headingPath: ['19. 重要风险总结'],
      displayText: '风险段落',
      sentences: [
        {
          sentenceId: 'C0019P:S001',
          rawText: '原句 C',
          normalizedText: '原句 C',
        },
      ],
    },
  ],
}

const evidenceRefs: InternalResultEvidenceRef[] = [
  {
    slotId: 'source',
    docId: 'doc_test',
    blockId: 'C0021',
    sentenceId: 'C0021:S001',
    sentenceAlias: 'T0001',
  },
  {
    slotId: 'source',
    docId: 'doc_test',
    blockId: 'C0021',
    sentenceId: 'C0021:S002',
    sentenceAlias: 'T0002',
  },
  {
    slotId: 'source',
    docId: 'doc_test',
    blockId: 'C0019P',
    sentenceId: 'C0019P:S001',
    sentenceAlias: 'T0003',
  },
]

describe('projectFindingEvidence', () => {
  it('resolves sentence text by exact sentenceId', () => {
    const presentation = projectFindingEvidence(document, evidenceRefs)
    expect(presentation.groups[0]?.sentences[0]?.sentenceText).toBe('原句 A')
  })

  it('groups evidence sentences under owning heading display name', () => {
    const presentation = projectFindingEvidence(document, evidenceRefs)
    expect(presentation.groups).toHaveLength(2)
    expect(presentation.groups[0]?.headingDisplayName).toBe('20. 结论')
    expect(presentation.groups[0]?.sentences).toHaveLength(2)
    expect(presentation.groups[1]?.headingDisplayName).toBe('19. 重要风险总结')
  })

  it('preserves finding evidence order across groups', () => {
    const presentation = projectFindingEvidence(document, evidenceRefs)
    const orderedSentenceIds = presentation.groups.flatMap((group) =>
      group.sentences.map((sentence) => sentence.sentenceId),
    )
    expect(orderedSentenceIds).toEqual(['C0021:S001', 'C0021:S002', 'C0019P:S001'])
  })

  it('resolves heading block id for heading navigation', () => {
    const indexes = buildDocumentEvidenceIndexes(document)
    const presentation = projectFindingEvidence(document, evidenceRefs, indexes)
    expect(presentation.groups[0]?.headingBlockId).toBe(
      composeDocumentBlockId('doc_test', 'C0020'),
    )
    expect(presentation.groups[0]?.sentences[0]?.contentBlockId).toBe(
      composeDocumentBlockId('doc_test', 'C0021'),
    )
  })
})
