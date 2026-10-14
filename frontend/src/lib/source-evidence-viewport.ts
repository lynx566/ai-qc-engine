import { evidenceLocationKey } from '@/lib/result-review-selection'
import { resolveContainingSourceSection } from '@/lib/source-document-section'
import type { InternalResultEvidenceRef } from '@/types/document-consistency-qc'
import type { DocumentView } from '@/types/document-review'

export type SourceEvidenceViewportDescriptor = {
  viewportKey: string
  slotId: string
  documentId: string
  evidenceLocationKey: string
  sourceBlockId: string
  sourceBlockIndex: number
  evidenceSentenceId: string
  evidenceSentenceIndex: number
  sectionHeadingSourceBlockId: string | null
  sectionStartBlockIndex: number
  sectionEndBlockIndexExclusive: number
}

export type SourceBlockIdentity = {
  slotId: string
  documentId: string
  sourceBlockId: string
}

export type SourceSentenceIdentity = {
  slotId: string
  documentId: string
  sentenceId: string
}

export class SourceEvidenceViewportDescriptorError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'SourceEvidenceViewportDescriptorError'
  }
}

function renderIdentity(prefix: string, parts: readonly (string | number)[]): string {
  return `${prefix}-${encodeURIComponent(JSON.stringify(parts))}`
}

function viewportKey(
  findingId: string,
  sourceLocationKey: string,
  sourceLocationOccurrence: number,
): string {
  return renderIdentity('source-evidence-viewport', [
    findingId,
    sourceLocationKey,
    sourceLocationOccurrence,
  ])
}

export function deriveSourceEvidenceViewportDescriptors({
  findingId,
  slotId,
  document,
  evidenceLocations,
}: {
  findingId: string
  slotId: string
  document: DocumentView
  evidenceLocations: readonly InternalResultEvidenceRef[]
}): SourceEvidenceViewportDescriptor[] {
  const occurrenceBySourceLocation = new Map<string, number>()

  const descriptors = evidenceLocations.map((evidenceLocation) => {
    if (evidenceLocation.slotId !== slotId || evidenceLocation.docId !== document.docId) {
      throw new SourceEvidenceViewportDescriptorError(
        `evidence location ${evidenceLocation.sentenceId} does not belong to loaded document ${slotId}/${document.docId}`,
      )
    }

    const sourceBlockIndex = document.blocks.findIndex(
      (block) => block.sourceBlockId === evidenceLocation.blockId,
    )
    if (sourceBlockIndex < 0) {
      throw new SourceEvidenceViewportDescriptorError(
        `unknown evidence block_id ${evidenceLocation.blockId}`,
      )
    }

    const sourceBlock = document.blocks[sourceBlockIndex]!
    const evidenceSentenceIndex = (sourceBlock.sentences ?? []).findIndex(
      (sentence) => sentence.sentenceId === evidenceLocation.sentenceId,
    )
    if (evidenceSentenceIndex < 0) {
      throw new SourceEvidenceViewportDescriptorError(
        `sentence_id ${evidenceLocation.sentenceId} does not belong to block_id ${evidenceLocation.blockId}`,
      )
    }

    const sourceLocationKey = evidenceLocationKey(evidenceLocation)
    const sourceLocationOccurrence = occurrenceBySourceLocation.get(sourceLocationKey) ?? 0
    occurrenceBySourceLocation.set(sourceLocationKey, sourceLocationOccurrence + 1)
    const section = resolveContainingSourceSection(document, sourceBlockIndex)

    return {
      viewportKey: viewportKey(findingId, sourceLocationKey, sourceLocationOccurrence),
      slotId,
      documentId: document.docId,
      evidenceLocationKey: sourceLocationKey,
      sourceBlockId: evidenceLocation.blockId,
      sourceBlockIndex,
      evidenceSentenceId: evidenceLocation.sentenceId,
      evidenceSentenceIndex,
      sectionHeadingSourceBlockId: section.sectionHeadingSourceBlockId,
      sectionStartBlockIndex: section.startBlockIndex,
      sectionEndBlockIndexExclusive: section.endBlockIndexExclusive,
    }
  })

  // Each projection belongs to one document/slot (validated above). Use its
  // canonical block ordinal and sentence-array position, never model alias order.
  // Sort only after assigning occurrence keys so duplicate anchors stay separate.
  return descriptors.sort((left, right) =>
    document.blocks[left.sourceBlockIndex]!.docOrderIndex -
      document.blocks[right.sourceBlockIndex]!.docOrderIndex ||
    left.evidenceSentenceIndex - right.evidenceSentenceIndex,
  )
}

export function sourceBlockRenderId(viewportKey: string, sourceBlockId: string): string {
  return renderIdentity('source-block-instance', [viewportKey, sourceBlockId])
}

export function sourceSentenceRenderId(
  viewportKey: string,
  documentId: string,
  sentenceId: string,
): string {
  return renderIdentity('source-sentence-instance', [viewportKey, documentId, sentenceId])
}

export function sourceBlockIdentityAttributes(identity: SourceBlockIdentity) {
  return {
    'data-slot-id': identity.slotId,
    'data-doc-id': identity.documentId,
    'data-block-id': identity.sourceBlockId,
  } as const
}

export function sourceSentenceIdentityAttributes(identity: SourceSentenceIdentity) {
  return {
    'data-slot-id': identity.slotId,
    'data-doc-id': identity.documentId,
    'data-sentence-id': identity.sentenceId,
  } as const
}

function hasIdentity(
  element: HTMLElement,
  expected: Readonly<Record<string, string>>,
): boolean {
  return Object.entries(expected).every(
    ([attribute, value]) => element.getAttribute(attribute) === value,
  )
}

export function findSourceBlockWithinRoot(
  root: ParentNode,
  identity: SourceBlockIdentity,
): HTMLElement | null {
  const expected = sourceBlockIdentityAttributes(identity)
  return [...root.querySelectorAll<HTMLElement>('[data-block-id]')].find(
    (element) => hasIdentity(element, expected),
  ) ?? null
}

export function findSourceSentenceWithinRoot(
  root: ParentNode,
  identity: SourceSentenceIdentity,
): HTMLElement | null {
  const expected = sourceSentenceIdentityAttributes(identity)
  return [...root.querySelectorAll<HTMLElement>('[data-sentence-id]')].find(
    (element) => hasIdentity(element, expected),
  ) ?? null
}
