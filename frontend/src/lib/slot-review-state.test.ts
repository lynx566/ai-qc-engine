import { describe, expect, it } from 'vitest'

import {
  anySlotBlocksNext,
  buildAppliedSelectionsBySlotId,
  createInitialSlotReviews,
  resolveInitialActiveSlotId,
} from '@/lib/slot-review-state'
import type { CandidateScopeFlowState } from '@/types/candidate-scope'

const flowState: CandidateScopeFlowState = {
  flowId: 'document_consistency_qc',
  flowRunId: 'flow_run_test',
  capabilityId: 'internal_dsur',
  capabilityTitle: '试验药临床安全性核查',
  flowStatus: 'paused_at_candidate_scope',
  canResume: true,
  contentDomainGroups: [
    {
      contentDomainId: 'clinical_safety',
      displayLabel: '临床安全性',
      filterJobIds: ['dsur_clinical_safety', 'dsur_overview'],
    },
  ],
  slots: [
    {
      slotId: 'source',
      docId: 'doc_test',
      automaticAnchorBlockIds: ['C0010'],
      currentAnchorBlockIds: ['C0010', 'C0030'],
      headings: [],
    },
    {
      slotId: 'source_b',
      docId: 'doc_other',
      automaticAnchorBlockIds: ['H0010'],
      currentAnchorBlockIds: ['H0010'],
      headings: [],
    },
  ],
}

describe('slot review state', () => {
  it('initializes per-slot review state from slots[]', () => {
    const reviews = createInitialSlotReviews(flowState)
    expect(reviews.source?.currentSelected).toEqual(new Set(['C0010', 'C0030']))
    expect(reviews.source_b?.currentSelected).toEqual(new Set(['H0010']))
  })

  it('uses first slot as initial active slot', () => {
    expect(resolveInitialActiveSlotId(flowState)).toBe('source')
  })

  it('blocks next when any slot is editing or has unapplied draft', () => {
    const reviews = createInitialSlotReviews(flowState)
    expect(anySlotBlocksNext(reviews)).toBe(false)

    reviews.source_b = {
      ...reviews.source_b!,
      draftSelected: new Set(['H0010', 'H0020']),
    }
    expect(anySlotBlocksNext(reviews)).toBe(true)
  })

  it('builds applied selections keyed by slot_id', () => {
    const reviews = createInitialSlotReviews(flowState)
    const applied = buildAppliedSelectionsBySlotId(reviews)
    expect(applied.get('source')).toEqual(new Set(['C0010', 'C0030']))
    expect(applied.get('source_b')).toEqual(new Set(['H0010']))
  })
})
