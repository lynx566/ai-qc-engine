import { describe, expect, it } from 'vitest'

import {
  resultEvidenceHighlightSurfaceClassName,
  resultFindingSelectedSurfaceClassName,
  resultReviewContainerBorderClassName,
  resultReviewInternalSeparatorBorderClassName,
  resultReviewWorkspaceDividerBorderClassName,
} from '@/lib/result-review-visual-tokens'
import {
  findingReviewQueueSelectedSurfaceClassName,
} from '@/lib/finding-review-presentation'
import {
  focusedFindingTargetSentenceClassName,
  resultFindingSelectedSurfaceClassName as exportedQueueSelectedClass,
} from '@/lib/sentence-navigation-focus'

describe('result review visual tokens', () => {
  it('orders neutral border tokens workspace divider > container > internal separator', () => {
    expect(resultReviewWorkspaceDividerBorderClassName).toBe('border-[#AEB8C4]')
    expect(resultReviewContainerBorderClassName).toBe('border-[#C5CDD6]')
    expect(resultReviewInternalSeparatorBorderClassName).toBe('border-[#E6EAF0]')
  })

  it('uses a muted blue hierarchy for selected finding vs evidence highlight', () => {
    expect(resultFindingSelectedSurfaceClassName).not.toBe(
      resultEvidenceHighlightSurfaceClassName,
    )
    expect(findingReviewQueueSelectedSurfaceClassName).toBe(resultFindingSelectedSurfaceClassName)
    expect(exportedQueueSelectedClass).toBe(resultFindingSelectedSurfaceClassName)
    expect(focusedFindingTargetSentenceClassName).toContain(
      resultEvidenceHighlightSurfaceClassName,
    )
    expect(focusedFindingTargetSentenceClassName).not.toContain(
      resultFindingSelectedSurfaceClassName,
    )
  })
})
