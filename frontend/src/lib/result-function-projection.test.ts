import { describe, expect, it } from 'vitest'

import { projectScopeResultsForFunctionViewQuery } from '@/lib/result-function-view-query'
import {
  buildScopeResultsByOutlineBlockId,
  resolveActiveProjectedScopeResultsForOutlineBlock,
} from '@/lib/result-scope-state'
import type { InternalResultScopeResult } from '@/types/document-consistency-qc'

const scope = (overrides: Partial<InternalResultScopeResult> & { scopeId: string }): InternalResultScopeResult => ({
  slotId: 'source', docId: 'doc_test', headingPath: ['Clinical safety'],
  outlineHeadingBlockId: 'C0030', executionStatus: 'complete', hasSuccessfulCheck: true,
  semanticModuleId: 'clinical_safety', ...overrides,
})

describe('function scope projection', () => {
  it('keeps multiple successful-check scopes on one outline heading without overwrite', () => {
    const grouped = buildScopeResultsByOutlineBlockId(projectScopeResultsForFunctionViewQuery([
      scope({ scopeId: 'HS_CLINICAL' }),
      scope({ scopeId: 'HS_OTHER', semanticModuleId: 'other' }),
    ], { mode: 'all' }))
    expect(grouped.get('doc_test:C0030')?.map((row) => row.scopeId))
      .toEqual(['HS_CLINICAL', 'HS_OTHER'])
  })

  it('re-resolves outline scopes when the semantic-module query changes', () => {
    const grouped = buildScopeResultsByOutlineBlockId(projectScopeResultsForFunctionViewQuery([
      scope({ scopeId: 'HS_CLINICAL' }),
      scope({ scopeId: 'HS_OTHER', semanticModuleId: 'other' }),
    ], { mode: 'semantic_module', semanticModuleId: 'clinical_safety' }))
    expect(resolveActiveProjectedScopeResultsForOutlineBlock(grouped, 'doc_test:C0030')
      .map((row) => row.scopeId)).toEqual(['HS_CLINICAL'])
  })
})
