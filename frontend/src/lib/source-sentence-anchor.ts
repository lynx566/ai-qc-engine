import type { SourceTextSelectionIdentity } from '@/lib/source-text-selection'
import type { SourceSentenceAnchor } from '@/types/source-annotation'
import type { DocumentView } from '@/types/document-review'

export type SourceSentenceAnchorDocument = {
  slotId: string
  document: DocumentView
}

export function resolveSourceSentenceAnchor(
  slotId: string,
  document: DocumentView,
  sentenceId: string,
): SourceSentenceAnchor | null {
  for (const block of document.blocks) {
    if (!block.sentences?.some((sentence) => sentence.sentenceId === sentenceId)) {
      continue
    }
    return {
      slotId,
      docId: document.docId,
      blockId: block.sourceBlockId,
      sentenceId,
    }
  }
  return null
}

export function resolveSourceSentenceAnchorInDocuments(
  documents: readonly SourceSentenceAnchorDocument[],
  identity: SourceTextSelectionIdentity,
): SourceSentenceAnchor | null {
  const matches = documents.filter((entry) => {
    if (identity.slotId && entry.slotId !== identity.slotId) {
      return false
    }
    if (identity.docId && entry.document.docId !== identity.docId) {
      return false
    }
    return true
  })

  if (identity.slotId || identity.docId) {
    if (matches.length !== 1) {
      return null
    }
    return resolveSourceSentenceAnchor(
      matches[0]!.slotId,
      matches[0]!.document,
      identity.sentenceId,
    )
  }

  if (documents.length !== 1) {
    return null
  }

  return resolveSourceSentenceAnchor(
    documents[0]!.slotId,
    documents[0]!.document,
    identity.sentenceId,
  )
}
