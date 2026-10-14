import { describe, expect, it } from 'vitest'

import {
  buildFindingReviewNoteSavePatch,
  clearFindingReviewNotePatch,
  serializeFindingReviewPatch,
} from '@/adapters/finding-review'

describe('finding review patch serialization', () => {
  it('omits note when note field is absent', () => {
    expect(serializeFindingReviewPatch({ decision: 'confirmed' })).toEqual({ decision: 'confirmed' })
    expect(serializeFindingReviewPatch({ marked: true })).toEqual({ marked: true })
  })

  it('sends explicit empty note to clear saved note', () => {
    expect(serializeFindingReviewPatch(clearFindingReviewNotePatch())).toEqual({ note: '' })
    expect(serializeFindingReviewPatch(buildFindingReviewNoteSavePatch(''))).toEqual({ note: '' })
  })

  it('distinguishes omitted note from clear-note patch', () => {
    const omitted = serializeFindingReviewPatch({ marked: true })
    const cleared = serializeFindingReviewPatch(clearFindingReviewNotePatch())

    expect(omitted).not.toHaveProperty('note')
    expect(cleared).toEqual({ note: '' })
  })

  it('normalizes whitespace-only save to clear-note patch', () => {
    expect(buildFindingReviewNoteSavePatch('   ')).toEqual({ note: '' })
    expect(serializeFindingReviewPatch(buildFindingReviewNoteSavePatch('   '))).toEqual({
      note: '',
    })
  })
})
