import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('ResultFindingsPanel evidence navigation ownership', () => {
  it('does not wire scope-panel evidence sentence navigation in the findings panel', () => {
    const source = readFileSync(
      resolve(import.meta.dirname, 'result-findings-panel.tsx'),
      'utf8',
    )

    expect(source).not.toContain('onNavigateToSentence')
    expect(source).not.toContain('FindingEvidenceSection')
    expect(source).not.toContain('来源依据')
    expect(source).not.toContain('ResultFindingCard')
  })
})
