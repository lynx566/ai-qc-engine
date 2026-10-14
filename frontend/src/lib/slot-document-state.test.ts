import { describe, expect, it } from 'vitest'

import {
  createInitialSlotDocumentState,
  getActiveDocument,
  getActiveDocumentLoadStatus,
} from '@/lib/slot-document-state'
import type { DocumentView } from '@/types/document-review'

const document: DocumentView = {
  docId: 'doc_a',
  fileName: 'a.docx',
  displayName: 'A',
  blocks: [],
}

describe('slot document state helpers', () => {
  it('returns cached active document and status', () => {
    const state = {
      ...createInitialSlotDocumentState(),
      documentsBySlotId: { source_a: document },
      documentLoadStatusBySlotId: { source_a: 'ready' },
    }

    expect(getActiveDocument(state, 'source_a')).toEqual(document)
    expect(getActiveDocumentLoadStatus(state, 'source_a')).toBe('ready')
  })
})
