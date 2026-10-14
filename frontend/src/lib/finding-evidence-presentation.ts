import { composeDocumentBlockId } from '@/adapters/extract-document'
import type { InternalResultEvidenceRef } from '@/types/document-consistency-qc'
import type { DocumentBlock, DocumentView, SentenceView } from '@/types/document-review'

export class FindingEvidencePresentationError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'FindingEvidencePresentationError'
  }
}

export type FindingEvidenceSentence = {
  sentenceId: string
  sentenceText: string
  contentBlockId: string
}

export type FindingEvidenceGroup = {
  headingKey: string
  headingDisplayName: string
  headingBlockId: string
  sentences: FindingEvidenceSentence[]
}

export type FindingEvidencePresentation = {
  groups: FindingEvidenceGroup[]
}

type DocumentEvidenceIndexes = {
  blockById: Map<string, DocumentBlock>
  sentenceById: Map<string, { block: DocumentBlock; sentence: SentenceView }>
  headingBlockByPathKey: Map<string, DocumentBlock>
}

function headingPathKey(headingPath: readonly string[]): string {
  return headingPath.join('\u001f')
}

export function buildDocumentEvidenceIndexes(document: DocumentView): DocumentEvidenceIndexes {
  const blockById = new Map<string, DocumentBlock>()
  const sentenceById = new Map<string, { block: DocumentBlock; sentence: SentenceView }>()
  const headingBlockByPathKey = new Map<string, DocumentBlock>()

  for (const block of document.blocks) {
    blockById.set(block.blockId, block)
    if (block.kind === 'heading') {
      headingBlockByPathKey.set(headingPathKey(block.headingPath), block)
    }
    for (const sentence of block.sentences ?? []) {
      if (sentenceById.has(sentence.sentenceId)) {
        throw new FindingEvidencePresentationError(
          `duplicate sentence_id ${sentence.sentenceId}`,
        )
      }
      sentenceById.set(sentence.sentenceId, { block, sentence })
    }
  }

  return {
    blockById,
    sentenceById,
    headingBlockByPathKey,
  }
}

function resolveHeadingContext(
  contentBlock: DocumentBlock,
  indexes: DocumentEvidenceIndexes,
): { headingKey: string; headingDisplayName: string; headingBlockId: string } {
  const headingKey = headingPathKey(contentBlock.headingPath)
  const headingBlock = indexes.headingBlockByPathKey.get(headingKey)
  if (headingBlock) {
    return {
      headingKey,
      headingDisplayName:
        headingBlock.displayText?.trim() ||
        contentBlock.headingPath.at(-1) ||
        '未命名章节',
      headingBlockId: headingBlock.blockId,
    }
  }

  const fallbackName = contentBlock.headingPath.at(-1) ?? '未命名章节'
  return {
    headingKey,
    headingDisplayName: fallbackName,
    headingBlockId: contentBlock.blockId,
  }
}

export function projectFindingEvidence(
  document: DocumentView,
  evidenceRefs: readonly InternalResultEvidenceRef[],
  indexes?: DocumentEvidenceIndexes,
): FindingEvidencePresentation {
  const resolvedIndexes = indexes ?? buildDocumentEvidenceIndexes(document)
  const groups = new Map<string, FindingEvidenceGroup>()
  const groupOrder: string[] = []

  for (const evidenceRef of evidenceRefs) {
    const contentBlockId = composeDocumentBlockId(evidenceRef.docId, evidenceRef.blockId)
    const contentBlock = resolvedIndexes.blockById.get(contentBlockId)
    if (!contentBlock) {
      throw new FindingEvidencePresentationError(
        `unknown evidence block_id ${evidenceRef.blockId}`,
      )
    }

    const sentenceEntry = resolvedIndexes.sentenceById.get(evidenceRef.sentenceId)
    if (!sentenceEntry) {
      throw new FindingEvidencePresentationError(
        `unknown evidence sentence_id ${evidenceRef.sentenceId}`,
      )
    }
    if (sentenceEntry.block.blockId !== contentBlockId) {
      throw new FindingEvidencePresentationError(
        `sentence_id ${evidenceRef.sentenceId} does not belong to block_id ${evidenceRef.blockId}`,
      )
    }

    const headingContext = resolveHeadingContext(contentBlock, resolvedIndexes)
    let group = groups.get(headingContext.headingKey)
    if (!group) {
      group = {
        headingKey: headingContext.headingKey,
        headingDisplayName: headingContext.headingDisplayName,
        headingBlockId: headingContext.headingBlockId,
        sentences: [],
      }
      groups.set(headingContext.headingKey, group)
      groupOrder.push(headingContext.headingKey)
    }

    group.sentences.push({
      sentenceId: evidenceRef.sentenceId,
      sentenceText: sentenceEntry.sentence.rawText,
      contentBlockId,
    })
  }

  return {
    groups: groupOrder.map((key) => groups.get(key)!),
  }
}
