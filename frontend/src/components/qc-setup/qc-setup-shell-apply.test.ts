import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('qc setup shell apply boundary', () => {
  it('does not call candidate-scope apply API', () => {
    const source = readFileSync(
      resolve(import.meta.dirname, 'qc-setup-shell.tsx'),
      'utf8',
    )

    expect(source).not.toContain('applyCandidateScopeChanges')
    expect(source).not.toContain('/apply')
    expect(source).not.toContain('buildPerJobChanges')
  })
})
