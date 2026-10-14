import { describe, expect, it } from 'vitest'

import {
  resolveDocumentConsistencyQcFlowRun,
  TaskRunDcqcFlowResolutionError,
} from '@/lib/task-run-flow-contribution'
import { DOCUMENT_CONSISTENCY_QC_FLOW_ID } from '@/lib/launcher-presentation'

describe('resolveDocumentConsistencyQcFlowRun', () => {
  it('returns the sole document_consistency_qc child flow_run_id', () => {
    expect(
      resolveDocumentConsistencyQcFlowRun([
        {
          flowId: DOCUMENT_CONSISTENCY_QC_FLOW_ID,
          flowRunId: 'document_consistency_qc_test',
        },
      ]),
    ).toBe('document_consistency_qc_test')
  })

  it('errors when no DCQC child is present', () => {
    expect(() =>
      resolveDocumentConsistencyQcFlowRun([
        { flowId: 'other_flow', flowRunId: 'other_run' },
      ]),
    ).toThrow(TaskRunDcqcFlowResolutionError)
    expect(() =>
      resolveDocumentConsistencyQcFlowRun([
        { flowId: 'other_flow', flowRunId: 'other_run' },
      ]),
    ).toThrow('TaskRun has no document_consistency_qc child flow')
  })

  it('errors when multiple DCQC children are present', () => {
    expect(() =>
      resolveDocumentConsistencyQcFlowRun([
        {
          flowId: DOCUMENT_CONSISTENCY_QC_FLOW_ID,
          flowRunId: 'document_consistency_qc_first',
        },
        {
          flowId: DOCUMENT_CONSISTENCY_QC_FLOW_ID,
          flowRunId: 'document_consistency_qc_second',
        },
      ]),
    ).toThrow('TaskRun has multiple document_consistency_qc child flows')
  })
})
