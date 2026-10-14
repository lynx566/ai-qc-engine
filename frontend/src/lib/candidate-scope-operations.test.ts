import { describe, expect, it } from 'vitest'

import { groupSelectedByJob } from '@/lib/candidate-scope-operations'
import type { CandidateHeading } from '@/types/candidate-scope'

const headings: CandidateHeading[] = [
  {
    docId: 'doc_test',
    filterJobId: 'dsur_overview',
    anchorBlockId: 'C0010',
    title: '1. 执行概要',
    headingPath: ['1. 执行概要'],
    level: 1,
    docOrderIndex: 10,
  },
  {
    docId: 'doc_test',
    filterJobId: 'dsur_clinical_safety',
    anchorBlockId: 'C0030',
    title: '4.1 总体不良事件概览',
    headingPath: ['4. 临床安全性', '4.1 总体不良事件概览'],
    level: 2,
    docOrderIndex: 80,
  },
  {
    docId: 'doc_test',
    filterJobId: 'dsur_clinical_safety',
    anchorBlockId: 'C0038',
    title: '4.3 其他安全性观察',
    headingPath: ['4. 临床安全性', '4.3 其他安全性观察'],
    level: 2,
    docOrderIndex: 100,
  },
]

describe('groupSelectedByJob', () => {
  it('groups selected anchors by filter job id', () => {
    const grouped = groupSelectedByJob(headings, new Set(['C0010', 'C0030', 'C0038']))
    expect([...(grouped.get('dsur_overview') ?? [])]).toEqual(['C0010'])
    expect([...(grouped.get('dsur_clinical_safety') ?? [])].sort()).toEqual([
      'C0030',
      'C0038',
    ])
  })
})
