import { describe, expect, it } from 'vitest'

import {
  shouldClearDocumentNavigationFocusOnDocumentMouseUp,
  shouldClearFocusedSentenceOnDocumentMouseUp,
} from '@/lib/focused-sentence-lifecycle'

describe('shouldClearDocumentNavigationFocusOnDocumentMouseUp', () => {
  it('preserves focus during valid source selection (creation workflow)', () => {
    expect(
      shouldClearDocumentNavigationFocusOnDocumentMouseUp({
        clickedPersistedHighlight: false,
        hasValidSourceSelection: true,
      }),
    ).toBe(false)
  })

  it('clears focus on ordinary click without valid selection', () => {
    expect(
      shouldClearDocumentNavigationFocusOnDocumentMouseUp({
        clickedPersistedHighlight: false,
        hasValidSourceSelection: false,
      }),
    ).toBe(true)
  })

  it('clears focus when clicking persisted highlight', () => {
    expect(
      shouldClearDocumentNavigationFocusOnDocumentMouseUp({
        clickedPersistedHighlight: true,
        hasValidSourceSelection: false,
      }),
    ).toBe(true)
  })
})

describe('shouldClearFocusedSentenceOnDocumentMouseUp', () => {
  it('remains an alias for shared document navigation dismissal', () => {
    const input = {
      clickedPersistedHighlight: false,
      hasValidSourceSelection: true,
    }

    expect(shouldClearFocusedSentenceOnDocumentMouseUp(input)).toBe(
      shouldClearDocumentNavigationFocusOnDocumentMouseUp(input),
    )
  })
})
