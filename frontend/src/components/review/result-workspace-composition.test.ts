import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import { ResultDocumentNavigator } from '@/components/review/result-document-navigator'
import { ResultFindingsPanel } from '@/components/review/result-findings-panel'

describe('Result workspace composition ownership', () => {
  it('keeps document navigator independent from function context', () => {
    const html = renderToStaticMarkup(
      createElement(ResultDocumentNavigator, {
        outlineEntries: [],
        scopeResultsByOutlineBlockId: new Map(),
        reviewState: null,
        activeOutlineBlockId: null,
        onSelectHeading: () => {},
      }),
    )

    expect(html).toContain('data-result-document-navigator')
    expect(html).toContain('文档目录')
    expect(html).not.toContain('data-result-function-context')
  })

  it('keeps the flat queue at Result level without section ownership', () => {
    const html = renderToStaticMarkup(
      createElement(ResultFindingsPanel, {
        taskDisplayName: 'DSUR',
        documentDisplayName: 'sample.docx',
        flowId: 'document_consistency_qc',
        functionViewQuery: { mode: 'all' },
        availableSemanticModuleIds: ['clinical_safety'],
        onFunctionViewQueryChange: () => {},
        activeOutlineBlockId: null,
        findings: [],
        reviewState: null,
        savingFindingId: null,
        selectedFindingId: null,
        selectedFinding: null,
        selectedEvidenceLocations: [],
        focusedEvidenceLocationKey: null,
        focusedEvidenceLocation: null,
        onSelectFinding: () => {},
        onFocusEvidence: () => {},
        onPatchFindingReview: async () => {},
        document: {
          docId: 'doc_test',
          fileName: 'sample.docx',
          displayName: 'sample.docx',
          blocks: [],
        },
      }),
    )

    expect(html).not.toContain('DSUR质控结果')
    expect(html).not.toContain('data-result-panel-title')
    expect(html).toContain('>质控结果<')
    expect(html).toContain('DSUR · sample.docx')
    expect(html).toContain('data-result-function-context')
    expect(html).toContain('data-result-findings-empty="true"')
    expect(html).not.toContain('data-result-scope-heading-title')
  })

  it('keeps function context in the leftmost Queue column without a global navigation rail', () => {
    const shellSource = readFileSync(resolve(import.meta.dirname, 'result-shell.tsx'), 'utf8')
    const findingsColumn = shellSource.match(
      /data-result-findings-panel="true"[\s\S]*?<\/aside>/,
    )?.[0]

    expect(shellSource).not.toContain('data-result-navigation-rail="true"')
    expect(findingsColumn).toContain('ResultFindingsPanel')
    expect(shellSource).toContain('functionViewQuery')
  })
})
