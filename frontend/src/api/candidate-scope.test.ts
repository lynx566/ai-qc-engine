import { describe, expect, it } from 'vitest'

import {
  buildCandidateScopeNextRequest,
  serializeCandidateScopeNextRequest,
} from '@/api/candidate-scope'
import type { CandidateScopeFlowState } from '@/types/candidate-scope'

const flowState: CandidateScopeFlowState = {
  flowId: 'document_consistency_qc',
  flowRunId: 'document_consistency_qc_20260910_150115_296031Z',
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
      automaticAnchorBlockIds: ['C0010', 'C0030'],
      currentAnchorBlockIds: ['C0010', 'C0030'],
      headings: [
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
          title: '4.2 严重不良事件与重要风险',
          headingPath: ['4. 临床安全性', '4.2 严重不良事件与重要风险'],
          level: 2,
          docOrderIndex: 90,
        },
      ],
    },
  ],
}

describe('candidate scope next request serialization', () => {
  it('serializes slot_decisions[] to bridge snake_case', () => {
    const request = buildCandidateScopeNextRequest(
      flowState,
      new Map([
        [
          'source',
          new Set(['C0010', 'C0030', 'C0038']),
        ],
      ]),
    )
    const payload = serializeCandidateScopeNextRequest(request)

    expect(payload).toEqual({
      flow_run_id: 'document_consistency_qc_20260910_150115_296031Z',
      slot_decisions: [
        {
          slot_id: 'source',
          candidate_scope: [
            {
              filter_job_id: 'dsur_clinical_safety',
              anchor_block_ids: ['C0030', 'C0038'],
            },
            {
              filter_job_id: 'dsur_overview',
              anchor_block_ids: ['C0010'],
            },
          ],
        },
      ],
    })
  })

  it('includes every slot in slot_decisions even for single-slot flows', () => {
    const request = buildCandidateScopeNextRequest(
      flowState,
      new Map([['source', new Set(['C0010'])]]),
    )

    expect(request.slotDecisions).toHaveLength(1)
    expect(request.slotDecisions[0]?.slotId).toBe('source')
  })
})
