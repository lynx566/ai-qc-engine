export type DocumentNavigationFocusDismissalInput = {
  clickedPersistedHighlight: boolean
  hasValidSourceSelection: boolean
}

/** @deprecated Use DocumentNavigationFocusDismissalInput */
export type FocusedSentenceDismissalInput = DocumentNavigationFocusDismissalInput

/**
 * Document navigation focus (sentence or block) clears on ordinary document
 * interaction, but stays during valid drag-selection (highlight / comment
 * creation workflow).
 */
export function shouldClearDocumentNavigationFocusOnDocumentMouseUp(
  input: DocumentNavigationFocusDismissalInput,
): boolean {
  if (input.hasValidSourceSelection) {
    return false
  }
  return true
}

/** @deprecated Use shouldClearDocumentNavigationFocusOnDocumentMouseUp */
export function shouldClearFocusedSentenceOnDocumentMouseUp(
  input: DocumentNavigationFocusDismissalInput,
): boolean {
  return shouldClearDocumentNavigationFocusOnDocumentMouseUp(input)
}

