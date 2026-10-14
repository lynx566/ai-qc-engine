import {
  deriveSourceEvidenceViewportDescriptors,
  SourceEvidenceViewportDescriptorError,
  type SourceEvidenceViewportDescriptor,
} from '@/lib/source-evidence-viewport'
import type { InternalResultEvidenceRef } from '@/types/document-consistency-qc'
import type { DocumentView } from '@/types/document-review'

export type FindingSourceViewportState =
  | { kind: 'empty' }
  | { kind: 'unavailable' }
  | { kind: 'ready'; descriptors: SourceEvidenceViewportDescriptor[] }

export function deriveFindingSourceViewportState({
  findingId,
  slotId,
  document,
  evidenceLocations,
}: {
  findingId: string | null
  slotId: string
  document: DocumentView
  evidenceLocations: readonly InternalResultEvidenceRef[]
}): FindingSourceViewportState {
  if (!findingId || evidenceLocations.length === 0) {
    return { kind: 'empty' }
  }

  try {
    const descriptors = deriveSourceEvidenceViewportDescriptors({
      findingId,
      slotId,
      document,
      evidenceLocations,
    })
    if (descriptors.length !== evidenceLocations.length) {
      return { kind: 'unavailable' }
    }
    return { kind: 'ready', descriptors }
  } catch (error) {
    if (error instanceof SourceEvidenceViewportDescriptorError) {
      return { kind: 'unavailable' }
    }
    throw error
  }
}
