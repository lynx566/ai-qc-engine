import { describe, expect, it } from 'vitest'

import {
  resultFindingReadingColumnClamp,
  resultFindingSourceDocumentPanelClassName,
  resultOverviewFindingsWorkspaceGridClassName,
  resultReviewSourceEvidencePanelCanvasPaddingClassName,
  resultReviewSourceEvidencePanelPaddingRightClassName,
  resultReviewSourceEvidenceScrollbarGutterPx,
} from '@/lib/result-review-stage-layout'

describe('result review stage layout', () => {
  it('retains the Overview bounded finding reading width', () => {
    expect(resultFindingReadingColumnClamp).toBe('clamp(28.75rem,34%,35rem)')
    expect(resultOverviewFindingsWorkspaceGridClassName).toContain(
      resultFindingReadingColumnClamp,
    )
  })

  it('keeps source workspace on minmax(0,1fr) with min-w-0 friendly flex track', () => {
    expect(resultOverviewFindingsWorkspaceGridClassName).toBe(
      'min-[840px]:grid-cols-[minmax(0,1fr)_clamp(28.75rem,34%,35rem)]',
    )
  })

  it('adds scrollbar gutter on the source evidence scroll pane without changing canvas inset', () => {
    expect(resultReviewSourceEvidenceScrollbarGutterPx).toBe(12)
    expect(resultReviewSourceEvidencePanelCanvasPaddingClassName).toBe('p-2 sm:p-3')
    expect(resultReviewSourceEvidencePanelPaddingRightClassName).toBe('pr-5 sm:pr-6')
    expect(resultFindingSourceDocumentPanelClassName).toContain('overflow-auto')
    expect(resultFindingSourceDocumentPanelClassName).toContain('pt-2 pb-2 pl-2')
    expect(resultFindingSourceDocumentPanelClassName).toContain(
      resultReviewSourceEvidencePanelPaddingRightClassName,
    )
    expect(resultFindingSourceDocumentPanelClassName).not.toContain('p-2 sm:p-3')
  })
})
