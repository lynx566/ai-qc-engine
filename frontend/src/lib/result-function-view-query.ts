import type { InternalResultScopeResult } from '@/types/document-consistency-qc'

export type ResultFunctionViewQuery =
  | { mode: 'all' }
  | { mode: 'semantic_module'; semanticModuleId: string }

/**
 * Semantic modules available within the current function result.
 * Sourced only from `scopeResults[].semanticModuleId`.
 */
export function resolveAvailableSemanticModuleIds(
  scopeResults: readonly InternalResultScopeResult[],
): string[] {
  const ids: string[] = []
  const seen = new Set<string>()
  for (const scopeResult of scopeResults) {
    if (!scopeResult.hasSuccessfulCheck) {
      continue
    }
    if (seen.has(scopeResult.semanticModuleId)) {
      continue
    }
    seen.add(scopeResult.semanticModuleId)
    ids.push(scopeResult.semanticModuleId)
  }
  return ids
}

export function resolveInitialResultFunctionViewQuery(
  scopeResults: readonly InternalResultScopeResult[],
): ResultFunctionViewQuery | null {
  const available = resolveAvailableSemanticModuleIds(scopeResults)
  if (available.length === 0) {
    return null
  }
  return { mode: 'all' }
}

function successfulScopeResults(
  scopeResults: readonly InternalResultScopeResult[],
): InternalResultScopeResult[] {
  return scopeResults.filter((scopeResult) => scopeResult.hasSuccessfulCheck)
}

/** Scope rows visible under the active function's current view query. */
export function projectScopeResultsForFunctionViewQuery(
  scopeResults: readonly InternalResultScopeResult[],
  functionViewQuery: ResultFunctionViewQuery | null,
): InternalResultScopeResult[] {
  if (!functionViewQuery) {
    return []
  }
  const successful = successfulScopeResults(scopeResults)
  if (functionViewQuery.mode === 'all') {
    return successful
  }
  return successful.filter(
    (scopeResult) => scopeResult.semanticModuleId === functionViewQuery.semanticModuleId,
  )
}

export function isResultFunctionViewQueryActive(
  functionViewQuery: ResultFunctionViewQuery | null,
  candidate: ResultFunctionViewQuery,
): boolean {
  if (!functionViewQuery) {
    return false
  }
  if (candidate.mode === 'all') {
    return functionViewQuery.mode === 'all'
  }
  return (
    functionViewQuery.mode === 'semantic_module' &&
    functionViewQuery.semanticModuleId === candidate.semanticModuleId
  )
}
