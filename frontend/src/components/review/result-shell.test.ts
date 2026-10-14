import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import { ResultShellLoaded } from '@/components/review/result-shell'
import type { DocumentOutlineEntry } from '@/lib/document-outline'
import type { DocumentConsistencyQcResult, InternalResultScopeResult } from '@/types/document-consistency-qc'
import type { DocumentView } from '@/types/document-review'

const document: DocumentView = {
  docId: 'doc_test',
  fileName: 'sample.docx',
  displayName: 'sample.docx',
  blocks: [
    {
      blockId: 'doc_test:C0030',
      sourceBlockId: 'C0030',
      kind: 'heading',
      docOrderIndex: 80,
      headingLevel: 1,
      headingPath: ['4. 临床安全性'],
      displayText: '4. 临床安全性',
    },
  ],
}

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

const result: DocumentConsistencyQcResult = {
  flowId: 'document_consistency_qc',
  flowRunId: 'document_consistency_qc_test',
  capabilityId: 'internal_dsur',
  flowStatus: 'success',
  comparisonRunStatus: 'success',
  finalizationStatus: 'completed',
  fallbackComparisonModes: [],
  findings: [],
  scopeResults: [scopeResult],
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

describe('ResultShellLoaded', () => {
  it('renders an empty Result as a canonical document without Finding UI', () => {
    const html = renderToStaticMarkup(
      createElement(MemoryRouter, null, createElement(ResultShellLoaded, {
        taskDisplayName: 'DSUR',
        functionViewQuery: { mode: 'all' },
        availableSemanticModuleIds: ['clinical_safety', 'other_module'],
        result,
        reviewState: null,
        document,
        documentStatus: 'ready',
        documentError: null,
        outlineEntries,
        scopeResultsByOutlineBlockId: new Map([['doc_test:C0030', [scopeResult]]]),
        activeOutlineBlockId: 'doc_test:C0030',
        selectedFindingId: null,
        selectedFinding: null,
        selectedEvidenceLocations: [],
        focusedEvidenceLocationKey: null,
        focusedEvidenceLocation: null,
        focusedBlockId: null,
        focusedSentence: null,
        sourceAnnotations: new Map(),
        revisionItems: [],
        commentItems: [],
        activeSourceAnnotationId: null,
        savingAnnotationId: null,
        savingFindingId: null,
        onNavigateRevision: () => {},
        onNavigateComment: () => {},
        onSourceAnnotationActivate: () => {},
        onCreateHighlight: async () => {},
        onDeleteHighlight: async () => {},
        onCreateComment: async () => {},
        onUpdateComment: async () => {},
        onDeleteComment: async () => {},
        onCreateEdit: async () => {},
        onUpdateEdit: async () => {},
        onDeleteEdit: async () => {},
        onSelectHeading: () => {},
        onSelectFinding: () => {},
        onFocusEvidence: () => {},
        onPatchFindingReview: async () => {},
        onClearFocusedSentence: () => {},
        onClearFocusedBlock: () => {},
        onClearActiveSourceAnnotation: () => {},
        onFunctionViewQueryChange: () => {},
      })),
    )

    expect(html).not.toMatch(/^<div[^>]*>[\s\S]*?<header[^>]*data-result-page-header/)
    expect(html).not.toContain('data-result-navigation-rail="true"')
    expect(html).not.toContain('data-result-document-navigator-trigger="desktop"')
    expect(html).toContain('data-result-outline-inline="true"')
    expect(html).toContain('aria-label="收起文档目录"')
    expect(html).toContain('4. 临床安全性')
    expect(html).not.toContain('data-result-function-context')
    expect(html).not.toContain('data-result-findings-panel="true"')
    expect(html).not.toContain('data-result-findings-trigger="true"')
    expect(html).not.toContain('查看范围')
    expect(html).not.toContain('查看核查范围')
    expect(html).not.toContain('[临床安全性]')
    const navigatorIndex = html.indexOf('data-result-outline-inline="true"')
    const documentPaneIndex = html.indexOf('data-result-document-pane="true"')

    expect(navigatorIndex).toBeGreaterThan(-1)
    expect(documentPaneIndex).toBeGreaterThan(navigatorIndex)
    expect(html).not.toContain('data-result-outline-persistent="true"')
    expect(html).not.toContain('min-[840px]:grid-cols-[clamp(20rem,26vw,24rem)_minmax(0,1fr)]')
    expect(html).not.toContain('data-result-document-header="true"')
    expect(html).not.toContain('DSUR质控结果')
    expect(html).not.toContain('DSUR 质控')
    const documentPane = html.match(/<main[\s\S]*?<\/main>/)?.[0]

    expect(documentPane).not.toContain('data-result-pane-header')
    expect(documentPane).not.toContain('DSUR · sample.docx')
    expect(documentPane).toMatch(
      /^<main[^>]*><div data-result-workspace-toolbar="true"/,
    )
  })
})

describe('result route cold load boundary', () => {
  it('resolves the child flow from the TaskRun-owned result route', () => {
    const pageSource = readFileSync(
      resolve(import.meta.dirname, '../../pages/result-page.tsx'),
      'utf8',
    )
    const shellSource = readFileSync(resolve(import.meta.dirname, 'result-shell.tsx'), 'utf8')
    const findingsPanelSource = readFileSync(
      resolve(import.meta.dirname, 'result-findings-panel.tsx'),
      'utf8',
    )

    expect(pageSource).toContain('resolveDocumentConsistencyQcFlowRun')
    expect(pageSource).toContain('ownedLoadState.taskDisplayName')
    expect(shellSource).toContain('documentDisplayName: document.displayName')
    expect(findingsPanelSource).toContain('<DocumentIdentity')
  })
})
