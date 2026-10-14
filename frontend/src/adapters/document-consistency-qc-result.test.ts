import { describe, expect, it } from 'vitest'

import { adaptDocumentConsistencyQcResult } from '@/adapters/document-consistency-qc-result'
import { DocumentConsistencyQcApiError } from '@/api/document-consistency-qc-error'

const rawPayload = {
  flow_id: 'document_consistency_qc',
  flow_run_id: 'document_consistency_qc_test',
  capability_id: 'internal_dsur',
  flow_status: 'success',
  comparison_run_status: 'success',
  finalization_status: 'completed_with_fallback',
  fallback_comparison_modes: ['focus_comparison'],
  findings: [
    {
      finding_id: 'L031',
      label: 'need_review',
      conclusion: 'cross-section issue',
      comparison_mode_id: 'focus_comparison',
      evidence_refs: [
        {
          block_id: 'C0031',
          sentence_id: 'C0031:S001',
          slot_id: 'source',
          doc_id: 'doc_test',
          sentence_alias: 'T0001',
        },
        {
          block_id: 'C0041',
          sentence_id: 'C0041:S001',
          slot_id: 'source',
          doc_id: 'doc_test',
          sentence_alias: 'T0002',
        },
      ],
    },
    {
      finding_id: 'L002',
      label: 'fail',
      conclusion: 'second in product order',
      comparison_mode_id: 'scope_local',
      evidence_refs: [],
    },
  ],
  scope_results: [
    {
      slot_id: 'source',
      doc_id: 'doc_test',
      scope_id: 'HS0001',
      heading_path: ['4. 临床安全性'],
      outline_heading_block_id: 'C0030',
      semantic_module_id: 'clinical_safety',
      execution_status: 'partial',
      has_successful_check: true,
    },
  ],
}

describe('adaptDocumentConsistencyQcResult', () => {
  it('maps snake_case payload to camelCase frontend model', () => {
    const result = adaptDocumentConsistencyQcResult(rawPayload)

    expect(result.flowId).toBe('document_consistency_qc')
    expect(result.flowRunId).toBe('document_consistency_qc_test')
    expect(result.capabilityId).toBe('internal_dsur')
    expect(result.comparisonRunStatus).toBe('success')
    expect(result.finalizationStatus).toBe('completed_with_fallback')
    expect(result.fallbackComparisonModes).toEqual(['focus_comparison'])
    expect(result.findings.map((finding) => finding.findingId)).toEqual(['L031', 'L002'])
    expect(result.scopeResults).toHaveLength(1)

    const scope = result.scopeResults[0]
    expect(scope.slotId).toBe('source')
    expect(scope.outlineHeadingBlockId).toBe('C0030')
    expect(scope.executionStatus).toBe('partial')
    expect(scope.hasSuccessfulCheck).toBe(true)
  })

  it('preserves canonical ids for document navigation', () => {
    const result = adaptDocumentConsistencyQcResult(rawPayload)
    const evidence = result.findings[0].evidenceRefs[0]

    expect(evidence.blockId).toBe('C0031')
    expect(evidence.sentenceId).toBe('C0031:S001')
    expect(evidence.slotId).toBe('source')
    expect(evidence.docId).toBe('doc_test')
    expect(evidence.sentenceAlias).toBe('T0001')
  })

  it('rejects unsupported finding labels', () => {
    expect(() =>
      adaptDocumentConsistencyQcResult({
        ...rawPayload,
        findings: [
          {
            ...rawPayload.findings[0],
            label: 'red',
          },
        ],
      }),
    ).toThrow(DocumentConsistencyQcApiError)
  })

  it('rejects the removed pass finding label', () => {
    expect(() =>
      adaptDocumentConsistencyQcResult({
        ...rawPayload,
        findings: [
          {
            ...rawPayload.findings[0],
            label: 'pass',
          },
        ],
      }),
    ).toThrow(DocumentConsistencyQcApiError)
  })
})
