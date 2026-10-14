import type { SentenceNavigationTarget, SentenceScrollResult } from '@/lib/document-navigation'
import {
  resultEvidenceHighlightSurfaceClassName,
  resultFindingSelectedSurfaceClassName,
} from '@/lib/result-review-visual-tokens'

export type FocusedSentence = {
  docId: string
  sentenceId: string
}

/** Muted evidence target surface (non-primary finding targets in section). */
export const findingEvidenceHighlightSurfaceClassName =
  resultEvidenceHighlightSurfaceClassName

export const sentenceNavigationFocusClassName =
  `${findingEvidenceHighlightSurfaceClassName} box-decoration-clone`

/** Evidence / finding sentence highlight (matches navigation blue family). */
export const findingTargetSentenceClassName =
  `cursor-pointer ${findingEvidenceHighlightSurfaceClassName} box-decoration-clone`

export const focusedFindingTargetSentenceClassName =
  `${resultEvidenceHighlightSurfaceClassName} box-decoration-clone`

export const atomicFindingTargetClassName = findingEvidenceHighlightSurfaceClassName

export const focusedAtomicFindingTargetClassName =
  resultEvidenceHighlightSurfaceClassName

/** Re-export for queue card parity tests. */
export { resultFindingSelectedSurfaceClassName }

export function sentenceNavigationFocusUpdate(
  result: SentenceScrollResult,
  target: SentenceNavigationTarget,
): FocusedSentence | null {
  if (result === 'sentence') {
    return {
      docId: target.docId,
      sentenceId: target.sentenceId,
    }
  }
  return null
}

export function isSentenceNavigationFocused(
  focusedSentence: FocusedSentence | null | undefined,
  docId: string,
  sentenceId: string,
): boolean {
  return (
    focusedSentence?.docId === docId && focusedSentence.sentenceId === sentenceId
  )
}
