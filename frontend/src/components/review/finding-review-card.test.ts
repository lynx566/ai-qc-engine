import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { FindingReviewCard } from '@/components/review/finding-review-card'
import { buildFindingPresentation } from '@/lib/finding-review-presentation'
import type { InternalResultFinding } from '@/types/document-consistency-qc'

const finding: InternalResultFinding = {
  findingId: 'F1',
  label: 'fail',
  conclusion: 'Shared card conclusion',
  comparisonModeId: 'scope_local',
  evidenceRefs: [
    {
      slotId: 'source',
      docId: 'doc-a',
      blockId: 'B1',
      sentenceId: 'B1:S1',
      sentenceAlias: 'T1',
    },
  ],
}

const reviewState = {
  flowRunId: 'run-1',
  entriesByFindingId: new Map([
    [
      'F1',
      {
        findingId: 'F1',
        decision: 'confirmed',
        marked: true,
        note: 'Reviewer note',
        updatedAt: '2026-10-04T00:00:00Z',
      },
    ],
  ]),
}

describe('FindingReviewCard shared presentation', () => {
  it('renders queue-style conclusion, note preview, and icon review controls', () => {
    const presentation = buildFindingPresentation(finding, reviewState)
    const html = renderToStaticMarkup(
      createElement(FindingReviewCard, {
        presentation,
        saving: false,
        onSelectFinding: () => {},
        onPatchFindingReview: async () => {},
      }),
    )

    expect(html).toContain('data-finding-review-card="true"')
    expect(html).toContain('Shared card conclusion')
    expect(html).toContain('data-finding-note-preview="true"')
    expect(html).toContain('Reviewer note')
    expect(html).toContain('data-finding-review-actions="true"')
    expect(html).toContain('aria-label="取消确认"')
    expect(html).toContain('aria-label="取消标记"')
    expect(html).not.toContain('来源依据')
    expect(html).not.toContain('data-finding-expanded')
  })


})
