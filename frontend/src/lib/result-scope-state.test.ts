import { describe, expect, it } from 'vitest'

import {
  buildScopeResultByOutlineBlockId,
  buildScopeResultsByOutlineBlockId,
  resolveActiveProjectedScopeResultsForOutlineBlock,
  resolveActiveScopeResultForOutlineBlock,
  resolveInitialActiveScope,
  resolveInitialOutlineBlockId,
  resolveResultSemanticModuleLabels,
  resolveResultScopeHeadingTitle,
  resolveSemanticModuleDisplayLabel,
} from '@/lib/result-scope-state'
import type { InternalResultScopeResult } from '@/types/document-consistency-qc'
import type { DocumentView } from '@/types/document-review'

const baseScope = (overrides: Partial<InternalResultScopeResult> = {}): InternalResultScopeResult => ({
  slotId: 'source', docId: 'doc_test', scopeId: 'HS0001', headingPath: ['Clinical safety'],
  outlineHeadingBlockId: 'C0030', semanticModuleId: 'clinical_safety',
  executionStatus: 'complete', hasSuccessfulCheck: true, ...overrides,
})

describe('result scope navigation state', () => {
  it('resolves the display title from the document and then the scope heading path', () => {
    const document: DocumentView = {
      docId: 'doc_test', fileName: 'sample.docx', displayName: 'sample.docx',
      blocks: [{ blockId: 'doc_test:C0030', kind: 'heading', docOrderIndex: 30,
        headingLevel: 1, headingPath: ['Clinical safety'], displayText: '4. Clinical safety' }],
    }
    expect(resolveResultScopeHeadingTitle(baseScope(), document)).toBe('4. Clinical safety')
    expect(resolveResultScopeHeadingTitle(
      baseScope({ outlineHeadingBlockId: 'C0099', headingPath: ['Summary'] }), document,
    )).toBe('Summary')
  })

  it('indexes only successful-check scopes by composed outline block id', () => {
    const successful = baseScope()
    const failed = baseScope({ scopeId: 'HS0002', executionStatus: 'failed', hasSuccessfulCheck: false })
    const singleIndex = buildScopeResultByOutlineBlockId([successful, failed])
    expect(resolveActiveScopeResultForOutlineBlock(singleIndex, 'doc_test:C0030')?.scopeId)
      .toBe('HS0001')
    const grouped = buildScopeResultsByOutlineBlockId([successful, failed])
    expect(grouped.get('doc_test:C0030')?.map((row) => row.scopeId)).toEqual(['HS0001'])
    expect(resolveActiveProjectedScopeResultsForOutlineBlock(grouped, 'doc_test:C0030'))
      .toEqual([successful])
  })

  it('uses the first successful-check scope for initial navigation, including partial scopes', () => {
    const partial = baseScope({ scopeId: 'HS0002', outlineHeadingBlockId: 'C0040',
      executionStatus: 'partial', hasSuccessfulCheck: true })
    expect(resolveInitialActiveScope([
      baseScope({ executionStatus: 'failed', hasSuccessfulCheck: false }), partial,
    ])).toEqual(partial)
    expect(resolveInitialOutlineBlockId([], partial)).toBe('doc_test:C0040')
  })

  it('derives semantic-module labels only from successful-check scopes', () => {
    expect(resolveSemanticModuleDisplayLabel('custom')).toBe('custom')
    expect(resolveResultSemanticModuleLabels([
      baseScope({ semanticModuleId: 'custom' }),
      baseScope({ scopeId: 'HS0002', semanticModuleId: 'ignored',
        executionStatus: 'failed', hasSuccessfulCheck: false }),
    ])).toEqual(['custom'])
  })
})
