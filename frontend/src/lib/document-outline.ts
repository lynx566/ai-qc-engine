import type { DocumentBlock, DocumentView } from '@/types/document-review'

export type DocumentOutlineEntry = {
  blockId: string
  title: string
  headingLevel: number
  headingPath: string[]
  docOrderIndex: number
}

export function buildDocumentOutlineEntries(document: DocumentView): DocumentOutlineEntry[] {
  return document.blocks
    .filter((block): block is DocumentBlock & { kind: 'heading' } => block.kind === 'heading')
    .map((block) => ({
      blockId: block.blockId,
      title: block.displayText?.trim() || block.headingPath.at(-1) || block.blockId,
      headingLevel: block.headingLevel ?? 1,
      headingPath: [...block.headingPath],
      docOrderIndex: block.docOrderIndex,
    }))
    .sort((left, right) => left.docOrderIndex - right.docOrderIndex)
}
