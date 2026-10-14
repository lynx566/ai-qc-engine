import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('useBlockNavigationFocus', () => {
  it('keeps block focus until explicit clear or replace', () => {
    const source = readFileSync(
      resolve(import.meta.dirname, 'use-block-navigation-focus.ts'),
      'utf8',
    )

    expect(source).toContain('applyBlockNavigationFocus(blockId)')
    expect(source).toContain('clearBlockNavigationFocusState')
    expect(source).not.toContain('setTimeout')
    expect(source).not.toContain('fade')
  })
})
