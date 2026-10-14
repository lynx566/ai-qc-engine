import { describe, expect, it } from 'vitest'

import { composeDocumentBlockId } from '@/adapters/extract-document'
import {
  resolveSourceSentenceAnchor,
  resolveSourceSentenceAnchorInDocuments,
} from '@/lib/source-sentence-anchor'

describe('resolveSourceSentenceAnchor', () => {
  it('resolves canonical extract block id from document view', () => {
    const anchor = resolveSourceSentenceAnchor('source', {
      docId: 'doc_test',
      fileName: 'sample.docx',
      displayName: 'sample.docx',
      blocks: [
        {
          blockId: composeDocumentBlockId('doc_test', 'C0002'),
          sourceBlockId: 'C0002',
          kind: 'paragraph',
          docOrderIndex: 1,
          headingPath: [],
          displayText: '第一句。第二句。',
          sentences: [
            { sentenceId: 'C0002:S001', rawText: '第一句。', normalizedText: '第一句。' },
            { sentenceId: 'C0002:S002', rawText: '第二句。', normalizedText: '第二句。' },
          ],
        },
      ],
    }, 'C0002:S002')

    expect(anchor).toEqual({
      slotId: 'source',
      docId: 'doc_test',
      blockId: 'C0002',
      sentenceId: 'C0002:S002',
    })
  })

  it('resolves the selected projected document when sentence ids collide', () => {
    const first = {
      slotId: 'first',
      document: {
        docId: 'same-doc',
        fileName: 'a.docx',
        displayName: 'A',
        blocks: [
          {
            blockId: 'same-doc:B1',
            sourceBlockId: 'B1',
            kind: 'paragraph' as const,
            docOrderIndex: 0,
            headingPath: [],
            displayText: 'First.',
            sentences: [
              { sentenceId: 'B1:S1', rawText: 'First.', normalizedText: 'First.' },
            ],
          },
        ],
      },
    }
    const second = {
      slotId: 'second',
      document: {
        ...first.document,
        fileName: 'b.docx',
        displayName: 'B',
      },
    }

    expect(
      resolveSourceSentenceAnchorInDocuments([first, second], {
        sentenceId: 'B1:S1',
        slotId: 'second',
        docId: 'same-doc',
      }),
    ).toEqual({
      slotId: 'second',
      docId: 'same-doc',
      blockId: 'B1',
      sentenceId: 'B1:S1',
    })
    expect(
      resolveSourceSentenceAnchorInDocuments([first, second], {
        sentenceId: 'B1:S1',
      }),
    ).toBeNull()
  })
})
