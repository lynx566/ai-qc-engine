/** Desktop Overview: bounded Finding queue + flexible source workspace. */
export const resultFindingReadingColumnClamp = 'clamp(28.75rem,34%,35rem)'
export const resultOverviewFindingsWorkspaceGridClassName =
  'min-[840px]:grid-cols-[minmax(0,1fr)_clamp(28.75rem,34%,35rem)]'

/** Extra space between source evidence cards and the pane vertical scrollbar (px). */
export const resultReviewSourceEvidenceScrollbarGutterPx = 12

/** Canvas inset on the outer source-evidence scroll pane (Tailwind spacing scale). */
export const resultReviewSourceEvidencePanelCanvasPaddingClassName = 'p-2 sm:p-3'

/**
 * Right padding = canvas padding + scrollbar gutter so cards stay aligned while the
 * scrollbar remains on the pane edge.
 */
export const resultReviewSourceEvidencePanelPaddingRightClassName =
  'pr-5 sm:pr-6'

/** Scroll owner for Overview / Result source evidence (`overflow-auto`). */
export const resultFindingSourceDocumentPanelClassName = [
  'min-h-0 min-w-0 flex-1 overflow-auto bg-[#F2F4F7]',
  'pt-2 pb-2 pl-2 sm:pt-3 sm:pb-3 sm:pl-3',
  resultReviewSourceEvidencePanelPaddingRightClassName,
].join(' ')
