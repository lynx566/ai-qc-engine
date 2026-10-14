// @vitest-environment happy-dom

import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { FindingSourceDocumentPanel } from '@/components/review/finding-source-document-panel'
import { resultFindingSourceDocumentPanelClassName } from '@/lib/result-review-stage-layout'
import type { InternalResultEvidenceRef } from '@/types/document-consistency-qc'
import type { DocumentView } from '@/types/document-review'

const documentView: DocumentView = {
  docId: 'doc-a', fileName: 'doc-a.docx', displayName: 'Document A',
  blocks: [
    {
      blockId: 'doc-a:H1', sourceBlockId: 'H1', kind: 'heading', docOrderIndex: 0,
      headingLevel: 1, headingPath: ['Section'], displayText: 'Section',
      sentences: [{ sentenceId: 'H1:S1', rawText: 'Section', normalizedText: 'Section' }],
    },
    {
      blockId: 'doc-a:P1', sourceBlockId: 'P1', kind: 'paragraph', docOrderIndex: 1,
      headingPath: ['Section'], displayText: 'Alpha.',
      sentences: [{ sentenceId: 'P1:S1', rawText: 'Alpha.', normalizedText: 'Alpha.' }],
    },
  ],
}

const validEvidence: InternalResultEvidenceRef = {
  slotId: 'source', docId: 'doc-a', blockId: 'P1', sentenceId: 'P1:S1', sentenceAlias: 'T1',
}

function markup(overrides: Record<string, unknown>) {
  return renderToStaticMarkup(createElement(FindingSourceDocumentPanel, {
    findingId: 'finding-a',
    slotId: 'source',
    document: documentView,
    documentStatus: 'ready',
    documentError: null,
    evidenceLocations: [validEvidence],
    overviewFindingAnchor: null,
    overviewPairActive: false,
    ...overrides,
  }))
}

describe('FindingSourceDocumentPanel', () => {
  it('waits for a null anchor only while paired with the Overview Queue', () => {
    const paired = markup({ overviewPairActive: true })
    expect(paired).toContain('data-result-review-source-placement-status="pending"')
    expect(paired).toContain('visibility:hidden')

    const unpaired = markup({ overviewPairActive: false })
    expect(unpaired).toContain('data-result-review-source-alignment-mode="top"')
    expect(unpaired).not.toContain('visibility:hidden')
    expect(unpaired).not.toContain('data-finding-source-presentation')
  })

  it('keeps empty, unavailable, loading, and error presentations distinct', () => {
    expect(markup({ evidenceLocations: [] })).toContain('data-finding-source-empty="true"')
    expect(markup({ evidenceLocations: [{ ...validEvidence, docId: 'doc-b' }] }))
      .toContain('data-finding-source-unavailable="true"')
    expect(markup({ documentStatus: 'loading' })).toContain('正在加载文档')
    expect(markup({ documentStatus: 'error', documentError: 'load failed' }))
      .toContain('load failed')
  })

  it('uses the shared source pane scroll gutter on the outer viewport', () => {
    const html = markup({ overviewPairActive: false })
    expect(html).toContain(`class="${resultFindingSourceDocumentPanelClassName}"`)
  })

  it('renders the complete ready descriptor set without legacy expansion controls', () => {
    const html = markup({ evidenceLocations: [validEvidence, { ...validEvidence }] })
    const root = document.createElement('div')
    root.innerHTML = html
    expect(root.querySelectorAll('[data-source-evidence-viewport="true"]')).toHaveLength(2)
    expect(root.textContent).not.toContain('查看全文')
    expect(root.textContent).not.toContain('显示更多')
  })
})
