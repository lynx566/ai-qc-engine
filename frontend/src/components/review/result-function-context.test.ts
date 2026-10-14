import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

import { describe, expect, it } from 'vitest'

import { ResultFunctionContext } from '@/components/review/result-function-context'
import { projectScopeResultsForFunctionViewQuery } from '@/lib/result-function-view-query'
import type { InternalResultScopeResult } from '@/types/document-consistency-qc'

const scopeResult = (semanticModuleId: string): InternalResultScopeResult => ({
  slotId: 'source',
  docId: 'doc_test',
  scopeId: `HS_${semanticModuleId}`,
  headingPath: ['4. 临床安全性'],
  outlineHeadingBlockId: 'C0030',
  semanticModuleId,
  executionStatus: 'complete',
  hasSuccessfulCheck: true,
})

describe('ResultFunctionContext view scope selector', () => {
  it('shows read-only scope label for a single semantic module', () => {
    const html = renderToStaticMarkup(
      createElement(ResultFunctionContext, {
        flowId: 'document_consistency_qc',
        functionViewQuery: { mode: 'all' },
        availableSemanticModuleIds: ['clinical_safety'],
        onFunctionViewQueryChange: () => {},
      }),
    )

    expect(html).toContain('撰写准确性与一致性核查')
    expect(html).toContain('data-result-function-scope-label')
    expect(html).toContain('data-semantic-module-id="clinical_safety"')
    expect(html).toContain('临床安全性')
    expect(html).toContain('border-[#91caff]')
    expect(html).toContain('data-result-function-scope-label')
    expect(html).not.toContain('data-result-function-view-query')
    expect(html).not.toContain('全部')
    expect(html).not.toContain('data-function-view-query-mode')
    expect(html).not.toContain('查看范围')
  })

  it('hides selector when no semantic modules are available', () => {
    const html = renderToStaticMarkup(
      createElement(ResultFunctionContext, {
        flowId: 'document_consistency_qc',
        functionViewQuery: null,
        availableSemanticModuleIds: [],
        onFunctionViewQueryChange: () => {},
      }),
    )

    expect(html).toContain('撰写准确性与一致性核查')
    expect(html).not.toContain('data-result-function-view-query')
    expect(html).not.toContain('clinical_safety')
    expect(html).not.toContain('临床安全性')
    expect(html).not.toContain('data-result-function-view-query-empty')
  })

  it('shows chip selector when two or more modules are available', () => {
    const html = renderToStaticMarkup(
      createElement(ResultFunctionContext, {
        flowId: 'document_consistency_qc',
        functionViewQuery: { mode: 'semantic_module', semanticModuleId: 'clinical_safety' },
        availableSemanticModuleIds: ['clinical_safety', 'other_module'],
        onFunctionViewQueryChange: () => {},
      }),
    )

    expect(html).toContain('data-result-function-view-query')
    expect(html).toContain('data-function-view-query-mode="all"')
    expect(html).toContain('全部')
    expect(html).toContain('data-semantic-module-id="clinical_safety"')
    expect(html).toContain('data-semantic-module-id="other_module"')
  })

  it('does not change projection when selector is hidden for a single module', () => {
    const scopes = [scopeResult('clinical_safety')]
    const allMode = projectScopeResultsForFunctionViewQuery(scopes, { mode: 'all' })
    const moduleMode = projectScopeResultsForFunctionViewQuery(scopes, {
      mode: 'semantic_module',
      semanticModuleId: 'clinical_safety',
    })

    expect(allMode).toEqual(moduleMode)
  })
})
