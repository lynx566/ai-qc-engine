import { describe, expect, it } from 'vitest'

import {
  projectScopeResultsForFunctionViewQuery,
  resolveAvailableSemanticModuleIds,
  resolveInitialResultFunctionViewQuery,
} from '@/lib/result-function-view-query'
import type { InternalResultScopeResult } from '@/types/document-consistency-qc'

const baseScope = (overrides: Partial<InternalResultScopeResult> = {}): InternalResultScopeResult => ({
  slotId: 'source', docId: 'doc_test', scopeId: 'HS0001', headingPath: ['Clinical safety'],
  outlineHeadingBlockId: 'C0030', semanticModuleId: 'clinical_safety',
  executionStatus: 'complete', hasSuccessfulCheck: true, ...overrides,
})

describe('ResultFunctionViewQuery', () => {
  it('derives semantic modules only from scopes with a successful check', () => {
    expect(resolveAvailableSemanticModuleIds([
      baseScope(),
      baseScope({ scopeId: 'HS0002', semanticModuleId: 'other', executionStatus: 'failed', hasSuccessfulCheck: false }),
    ])).toEqual(['clinical_safety'])
  })

  it('returns null when no scope has a successful check', () => {
    expect(resolveInitialResultFunctionViewQuery([
      baseScope({ executionStatus: 'failed', hasSuccessfulCheck: false }),
    ])).toBeNull()
  })

  it('projects successful scopes for all and semantic-module modes', () => {
    const scopes = [
      baseScope(),
      baseScope({ scopeId: 'HS0002', semanticModuleId: 'other' }),
      baseScope({ scopeId: 'HS0003', executionStatus: 'failed', hasSuccessfulCheck: false }),
    ]
    expect(projectScopeResultsForFunctionViewQuery(scopes, { mode: 'all' }).map((row) => row.scopeId))
      .toEqual(['HS0001', 'HS0002'])
    expect(projectScopeResultsForFunctionViewQuery(scopes, {
      mode: 'semantic_module', semanticModuleId: 'clinical_safety',
    }).map((row) => row.scopeId)).toEqual(['HS0001'])
  })

  it('returns an empty projection before query initialization', () => {
    expect(projectScopeResultsForFunctionViewQuery([baseScope()], null)).toEqual([])
  })
})
