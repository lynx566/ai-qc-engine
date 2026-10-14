import { describe, expect, it } from 'vitest'

import { canonicalizeDraftSelection } from '@/lib/candidate-scope-selection'
import type { CandidateHeading } from '@/types/candidate-scope'

const headingsByAnchor = new Map<string, CandidateHeading>([
  [
    'C0010',
    {
      docId: 'doc_test',
      filterJobId: 'dsur_overview',
      anchorBlockId: 'C0010',
      title: '1. 执行概要',
      headingPath: ['1. 执行概要'],
      level: 1,
      docOrderIndex: 10,
    },
  ],
  [
    'C0014',
    {
      docId: 'doc_test',
      filterJobId: 'dsur_clinical_safety',
      anchorBlockId: 'C0014',
      title: '2. 报告范围与方法',
      headingPath: ['2. 报告范围与方法'],
      level: 1,
      docOrderIndex: 20,
    },
  ],
  [
    'C0044',
    {
      docId: 'doc_test',
      filterJobId: 'dsur_overview',
      anchorBlockId: 'C0044',
      title: '6. 结论',
      headingPath: ['6. 结论'],
      level: 1,
      docOrderIndex: 60,
    },
  ],
  [
    'C0047',
    {
      docId: 'doc_test',
      filterJobId: 'dsur_clinical_safety',
      anchorBlockId: 'C0047',
      title: '7. 附录',
      headingPath: ['7. 附录'],
      level: 1,
      docOrderIndex: 70,
    },
  ],
])

function applyLocal(current: Set<string>, draft: Set<string>): Set<string> {
  return canonicalizeDraftSelection(draft, headingsByAnchor)
}

describe('candidate scope local apply', () => {
  it('starts from automatic selection', () => {
    const automatic = new Set(['C0010', 'C0044'])
    expect([...automatic].sort()).toEqual(['C0010', 'C0044'])
  })

  it('preserves prior selections across sequential applies', () => {
    let current = new Set(['C0010', 'C0044'])

    current = applyLocal(current, new Set([...current, 'C0014']))
    expect([...current].sort()).toEqual(['C0010', 'C0014', 'C0044'])

    current = applyLocal(current, new Set([...current, 'C0047']))
    expect([...current].sort()).toEqual(['C0010', 'C0014', 'C0044', 'C0047'])

    current = applyLocal(current, new Set(['C0010', 'C0044', 'C0047']))
    expect([...current].sort()).toEqual(['C0010', 'C0044', 'C0047'])
  })

  it('cancel restores draft from current without changing current', () => {
    const current = new Set(['C0010', 'C0044', 'C0047'])
    const draft = new Set(['C0010', 'C0014', 'C0044'])

    const restoredDraft = new Set(current)
    expect([...restoredDraft].sort()).toEqual(['C0010', 'C0044', 'C0047'])
    expect([...current].sort()).toEqual(['C0010', 'C0044', 'C0047'])
    expect([...draft].sort()).not.toEqual([...restoredDraft].sort())
  })
})
