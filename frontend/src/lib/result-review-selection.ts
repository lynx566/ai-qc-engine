import type { FocusedSentence } from '@/lib/sentence-navigation-focus'
import type {
  InternalResultEvidenceRef,
  InternalResultFinding,
} from '@/types/document-consistency-qc'

export type ReviewWorkspaceStoredSelection = {
  selectedFindingId: string | null
  focusedEvidenceLocationKey: string | null
}

export type ReviewWorkspaceSelection = {
  selectedFinding: InternalResultFinding | null
  selectedEvidenceLocations: readonly InternalResultEvidenceRef[]
  focusedEvidenceLocation: InternalResultEvidenceRef | null
  focusedSentence: FocusedSentence | null
}

export const initialReviewWorkspaceStoredSelection: ReviewWorkspaceStoredSelection = {
  selectedFindingId: null,
  focusedEvidenceLocationKey: null,
}

export function evidenceLocationKey(location: InternalResultEvidenceRef): string {
  return JSON.stringify([
    location.slotId,
    location.docId,
    location.blockId,
    location.sentenceId,
  ])
}

export function deriveReviewWorkspaceSelection(
  findings: readonly InternalResultFinding[],
  stored: ReviewWorkspaceStoredSelection,
): ReviewWorkspaceSelection {
  const selectedFinding =
    findings.find((finding) => finding.findingId === stored.selectedFindingId) ?? null
  const selectedEvidenceLocations = selectedFinding?.evidenceRefs ?? []
  const focusedEvidenceLocation = stored.focusedEvidenceLocationKey
    ? selectedEvidenceLocations.find(
        (location) => evidenceLocationKey(location) === stored.focusedEvidenceLocationKey,
      ) ?? null
    : null

  return {
    selectedFinding,
    selectedEvidenceLocations,
    focusedEvidenceLocation,
    focusedSentence: focusedEvidenceLocation
      ? {
          docId: focusedEvidenceLocation.docId,
          sentenceId: focusedEvidenceLocation.sentenceId,
        }
      : null,
  }
}

export function selectFinding(
  stored: ReviewWorkspaceStoredSelection,
  findings: readonly InternalResultFinding[],
  findingId: string,
): ReviewWorkspaceStoredSelection {
  const selectedFinding = findings.find((finding) => finding.findingId === findingId)
  if (!selectedFinding) {
    return initialReviewWorkspaceStoredSelection
  }

  const focusRemainsValid = selectedFinding.evidenceRefs.some(
    (location) => evidenceLocationKey(location) === stored.focusedEvidenceLocationKey,
  )
  return {
    selectedFindingId: selectedFinding.findingId,
    focusedEvidenceLocationKey: focusRemainsValid
      ? stored.focusedEvidenceLocationKey
      : null,
  }
}

export function reconcileReviewWorkspaceSelection(
  stored: ReviewWorkspaceStoredSelection,
  findings: readonly InternalResultFinding[],
): ReviewWorkspaceStoredSelection {
  if (stored.selectedFindingId === null) {
    return initialReviewWorkspaceStoredSelection
  }
  return selectFinding(stored, findings, stored.selectedFindingId)
}

export function focusEvidence(
  stored: ReviewWorkspaceStoredSelection,
  selectedEvidenceLocations: readonly InternalResultEvidenceRef[],
  location: InternalResultEvidenceRef,
): ReviewWorkspaceStoredSelection {
  const candidateKey = evidenceLocationKey(location)
  const focusIsValid = selectedEvidenceLocations.some(
    (selectedLocation) => evidenceLocationKey(selectedLocation) === candidateKey,
  )
  return {
    selectedFindingId: stored.selectedFindingId,
    focusedEvidenceLocationKey: focusIsValid ? candidateKey : null,
  }
}
