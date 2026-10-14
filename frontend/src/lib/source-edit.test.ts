import { describe, expect, it } from 'vitest'

import { isValidEditDraft } from '@/lib/source-edit'

describe('source-edit', () => {
  it('rejects whitespace-only replacement drafts', () => {
    expect(isValidEditDraft('')).toBe(false)
    expect(isValidEditDraft('   ')).toBe(false)
    expect(isValidEditDraft('80.0%')).toBe(true)
  })
})
