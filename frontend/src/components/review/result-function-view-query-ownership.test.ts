import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import { ResultOutlineSidebar } from '@/components/review/result-outline-sidebar'
import { resolveInitialResultFunctionViewQuery } from '@/lib/result-function-view-query'
import type { DocumentOutlineEntry } from '@/lib/document-outline'
import type { InternalResultScopeResult } from '@/types/document-consistency-qc'

const scopeResult: InternalResultScopeResult = {
  slotId: 'source',
  docId: 'doc_test',
  scopeId: 'HS0001',
  headingPath: ['4. 临床安全性'],
  outlineHeadingBlockId: 'C0030',
  semanticModuleId: 'clinical_safety',
  executionStatus: 'partial',
  hasSuccessfulCheck: true,
}

const outlineEntries: DocumentOutlineEntry[] = [
  {
    blockId: 'doc_test:C0030',
    title: '4. 临床安全性',
    headingLevel: 1,
    headingPath: ['4. 临床安全性'],
    docOrderIndex: 80,
  },
]

describe('ResultFunctionViewQuery ownership', () => {
  it('initializes to all mode from scopeResults semanticModuleId', () => {
    expect(resolveInitialResultFunctionViewQuery([scopeResult])).toEqual({ mode: 'all' })
  })

  it('does not thread functionViewQuery into document navigator', () => {
    const navigatorSource = readFileSync(
      resolve(import.meta.dirname, 'result-document-navigator.tsx'),
      'utf8',
    )
    const outlineSource = readFileSync(
      resolve(import.meta.dirname, 'result-outline-sidebar.tsx'),
      'utf8',
    )

    expect(navigatorSource).not.toContain('functionViewQuery')
    expect(outlineSource).not.toContain('functionViewQuery')
  })

  it('keeps outline navigation free of retired finding counts', () => {
    const html = renderToStaticMarkup(
      createElement(ResultOutlineSidebar, {
        outlineEntries,
        scopeResultsByOutlineBlockId: new Map([['doc_test:C0030', [scopeResult]]]),
        reviewState: null,
        activeOutlineBlockId: 'doc_test:C0030',
        onSelectHeading: () => {},
      }),
    )

    expect(html).toContain('4. 临床安全性')
    expect(html).not.toContain('问题/已解决')
  })
})
