import { describe, expect, it } from 'vitest'

import { buildDocumentOutlineEntries } from '@/lib/document-outline'
import type { DocumentView } from '@/types/document-review'

const document: DocumentView = {
  docId: 'doc_test',
  fileName: 'sample.docx',
  displayName: 'sample.docx',
  blocks: [
    {
      blockId: 'doc_test:C0001',
      kind: 'heading',
      docOrderIndex: 10,
      headingLevel: 1,
      headingPath: ['1. 执行概要'],
      displayText: '1. 执行概要',
    },
    {
      blockId: 'doc_test:C0002',
      kind: 'paragraph',
      docOrderIndex: 20,
      headingPath: ['1. 执行概要'],
      displayText: '正文',
    },
    {
      blockId: 'doc_test:C0030',
      kind: 'heading',
      docOrderIndex: 80,
      headingLevel: 2,
      headingPath: ['4. 临床安全性', '4.1 总体不良事件概览'],
      displayText: '4.1 总体不良事件概览',
    },
  ],
}

describe('buildDocumentOutlineEntries', () => {
  it('includes all document headings in document order', () => {
    const entries = buildDocumentOutlineEntries(document)
    expect(entries.map((entry) => entry.blockId)).toEqual([
      'doc_test:C0001',
      'doc_test:C0030',
    ])
  })
})
