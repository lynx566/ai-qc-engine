import { describe, expect, it } from 'vitest'

import { canonicalizeDraftSelection } from '@/lib/candidate-scope-selection'
import type { CandidateHeading } from '@/types/candidate-scope'

const headings: CandidateHeading[] = [
  {
    docId: 'doc_test',
    filterJobId: 'dsur_clinical_safety',
    anchorBlockId: 'C0038',
    title: '4.3 其他安全性观察',
    headingPath: ['4. 临床安全性', '4.3 其他安全性观察'],
    level: 2,
    docOrderIndex: 100,
  },
  {
    docId: 'doc_test',
    filterJobId: 'dsur_clinical_safety',
    anchorBlockId: 'C0040',
    title: '4.3.1 安全性参考信息的一致性',
    headingPath: [
      '4. 临床安全性',
      '4.3 其他安全性观察',
      '4.3.1 安全性参考信息的一致性',
    ],
    level: 3,
    docOrderIndex: 110,
  },
]

describe('candidate scope draft canonicalization', () => {
  it('drops descendant when ancestor is selected', () => {
    const map = new Map(headings.map((item) => [item.anchorBlockId, item]))
    const canonical = canonicalizeDraftSelection(new Set(['C0038', 'C0040']), map)
    expect([...canonical]).toEqual(['C0038'])
  })
})
