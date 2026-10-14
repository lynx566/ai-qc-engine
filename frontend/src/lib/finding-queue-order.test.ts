import { describe, expect, it } from 'vitest'

import {
  deriveQueueFindings,
  resolveAdjacentQueueFindingId,
  resolveDefaultQueueFindingId,
  resolveQueueFindingIndex,
} from '@/lib/finding-queue-order'
import type { InternalResultFinding } from '@/types/document-consistency-qc'

function finding(
  findingId: string,
  label: InternalResultFinding['label'],
): InternalResultFinding {
  return {
    findingId,
    label,
    conclusion: findingId,
    comparisonModeId: 'scope_local',
    evidenceRefs: [],
  }
}

describe('deriveQueueFindings', () => {
  it('places every fail before every need_review', () => {
    const canonical = [
      finding('N1', 'need_review'),
      finding('F1', 'fail'),
      finding('N2', 'need_review'),
      finding('F2', 'fail'),
    ]

    const queue = deriveQueueFindings(canonical)

    expect(queue.map((item) => item.findingId)).toEqual(['F1', 'F2', 'N1', 'N2'])
    expect(queue.map((item) => item.label)).toEqual([
      'fail',
      'fail',
      'need_review',
      'need_review',
    ])
  })

  it('preserves product-final relative order within each label group', () => {
    const canonical = [
      finding('N2', 'need_review'),
      finding('N1', 'need_review'),
      finding('F2', 'fail'),
      finding('F1', 'fail'),
    ]

    expect(deriveQueueFindings(canonical).map((item) => item.findingId)).toEqual([
      'F2',
      'F1',
      'N2',
      'N1',
    ])
  })

  it('does not mutate the canonical findings array', () => {
    const canonical = [
      finding('N1', 'need_review'),
      finding('F1', 'fail'),
    ]
    const snapshot = canonical.map((item) => item.findingId)

    deriveQueueFindings(canonical)

    expect(canonical.map((item) => item.findingId)).toEqual(snapshot)
  })
})

describe('queue finding navigation', () => {
  const queue = deriveQueueFindings([
    finding('N1', 'need_review'),
    finding('F2', 'fail'),
    finding('N2', 'need_review'),
    finding('F1', 'fail'),
  ])

  it('uses queue presentation order for default selection', () => {
    expect(resolveDefaultQueueFindingId(queue)).toBe('F2')
    expect(resolveDefaultQueueFindingId([])).toBeNull()
    expect(resolveQueueFindingIndex(queue, 'F1')).toBe(1)
  })


  it('does not wrap adjacent navigation at queue ends', () => {
    expect(resolveAdjacentQueueFindingId(queue, 'F2', 'previous')).toBeNull()
    expect(resolveAdjacentQueueFindingId(queue, 'N2', 'next')).toBeNull()
    expect(resolveAdjacentQueueFindingId(queue, 'F2', 'next')).toBe('F1')
    expect(resolveAdjacentQueueFindingId(queue, 'F1', 'previous')).toBe('F2')
  })



})
