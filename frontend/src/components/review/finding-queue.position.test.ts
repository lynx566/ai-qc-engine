import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { FindingQueue } from '@/components/review/finding-queue'
import type { InternalResultFinding } from '@/types/document-consistency-qc'

const findings: InternalResultFinding[] = [
  {
    findingId: 'A',
    label: 'fail',
    conclusion: 'Alpha',
    comparisonModeId: 'scope_local',
    evidenceRefs: [],
  },
  {
    findingId: 'B',
    label: 'fail',
    conclusion: 'Beta',
    comparisonModeId: 'scope_local',
    evidenceRefs: [],
  },
  {
    findingId: 'C',
    label: 'need_review',
    conclusion: 'Gamma',
    comparisonModeId: 'scope_local',
    evidenceRefs: [],
  },
]

describe('FindingQueue position labels', () => {
  it('renders queue position metadata aligned with presentation order', () => {
    const html = renderToStaticMarkup(
      createElement(FindingQueue, {
        findings,
        reviewState: null,
        selectedFindingId: 'B',
        savingFindingId: null,
        onSelectFinding: () => {},
        onPatchFindingReview: async () => {},
      }),
    )

    const itemA = html.match(/data-finding-queue-item="A"[\s\S]*?<\/li>/)?.[0] ?? ''
    const itemB = html.match(/data-finding-queue-item="B"[\s\S]*?<\/li>/)?.[0] ?? ''
    const itemC = html.match(/data-finding-queue-item="C"[\s\S]*?<\/li>/)?.[0] ?? ''

    expect(itemA).toContain('data-finding-queue-position="1"')
    expect(itemA).toContain('data-finding-queue-position-total="3"')
    expect(itemA).toContain('>1 / 3<')

    expect(itemB).toContain('data-finding-queue-position="2"')
    expect(itemB).toContain('>2 / 3<')

    expect(itemC).toContain('data-finding-queue-position="3"')
    expect(itemC).toContain('>3 / 3<')
  })
})
