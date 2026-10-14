import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { ResultFindingsPanel } from '@/components/review/result-findings-panel'
import type { InternalResultFinding } from '@/types/document-consistency-qc'
import type { DocumentView } from '@/types/document-review'

const document: DocumentView = {
  docId: 'doc_test',
  fileName: 'sample.docx',
  displayName: 'sample.docx',
  blocks: [
    {
      blockId: 'doc_test:C0030', kind: 'heading', docOrderIndex: 30, headingLevel: 1,
      headingPath: ['Clinical safety'], displayText: '4. Clinical safety',
    },
    {
      blockId: 'doc_test:C0031', kind: 'paragraph', docOrderIndex: 31,
      headingPath: ['Clinical safety'], displayText: 'Evidence sentence must stay out',
      sentences: [{
        sentenceId: 'C0031:S001',
        rawText: 'Evidence sentence must stay out',
        normalizedText: 'Evidence sentence must stay out',
      }],
    },
  ],
}

const findings: InternalResultFinding[] = [
  {
    findingId: 'F9',
    label: 'fail',
    conclusion: 'Product-final first task',
    comparisonModeId: 'scope_local',
    evidenceRefs: [
      {
        slotId: 'source',
        docId: 'doc_test',
        blockId: 'C0031',
        sentenceId: 'C0031:S001',
        sentenceAlias: 'T0001',
      },
      {
        slotId: 'source',
        docId: 'doc_test',
        blockId: 'C0041',
        sentenceId: 'C0041:S001',
        sentenceAlias: 'T0002',
      },
    ],
  },
  {
    findingId: 'F1',
    label: 'need_review',
    conclusion: 'Product-final second task',
    comparisonModeId: 'cross_scope',
    evidenceRefs: [],
  },
]

const props = {
  taskDisplayName: 'DSUR',
  documentDisplayName: document.displayName,
  flowId: 'document_consistency_qc',
  functionViewQuery: { mode: 'all' } as const,
  availableSemanticModuleIds: ['clinical_safety', 'other_module'],
  onFunctionViewQueryChange: () => {},
  activeOutlineBlockId: 'doc_test:C0030',
  findings,
  reviewState: {
    flowRunId: 'run_1',
    entriesByFindingId: new Map([
      ['F9', {
        findingId: 'F9',
        decision: 'confirmed',
        marked: true,
        note: 'Private reviewer note',
        updatedAt: '2026-10-04T00:00:00Z',
      }],
    ]),
  },
  savingFindingId: null,
  selectedFindingId: 'F9',
  selectedFinding: findings[0],
  selectedEvidenceLocations: findings[0]!.evidenceRefs,
  focusedEvidenceLocationKey: null,
  focusedEvidenceLocation: null,
  onSelectFinding: () => {},
  onFocusEvidence: () => {},
  onPatchFindingReview: async () => {},
  document,
}

describe('ResultFindingsPanel flat Finding Queue', () => {
  it('renders the full document identity with the same wrapping semantics as Setup', () => {
    const longFilename = '艾美妥珠单抗 研发期间安全性更新报告#2_fe_stub.docx'
    const html = renderToStaticMarkup(createElement(ResultFindingsPanel, {
      ...props,
      documentDisplayName: longFilename,
    }))
    const identity = html.match(/<p[^>]*data-document-identity="true"[^>]*>[\s\S]*?<\/p>/)?.[0]

    expect(identity).toBeTruthy()
    expect(identity).toContain('whitespace-normal')
    expect(identity).toContain('break-words')
    expect(identity).not.toMatch(/truncate|whitespace-nowrap|line-clamp|break-all|overflow-wrap:anywhere/)
    expect(identity).not.toMatch(/\bgrid\b|grid-cols|\bflex\b|text-indent|\bindent-|\bpl-/)
    expect(identity).not.toContain('data-document-identity-prefix')
    expect(identity).not.toContain('data-document-identity-filename')
    expect(identity).toContain(`>DSUR · ${longFilename}</p>`)
    expect(identity).toContain(`aria-label="DSUR · ${longFilename}"`)
  })

  it('renders result findings once in queue presentation order without section-owned evidence', () => {
    const html = renderToStaticMarkup(createElement(ResultFindingsPanel, props))

    expect(html).toContain('data-result-function-context')
    expect(html).toContain('data-result-pane-header="true"')
    expect(html).toContain('data-task-page-title="true"')
    expect(html).toContain('>质控结果<')
    expect(html).toContain('data-document-identity="true"')
    expect(html).toContain('DSUR · sample.docx')
    expect(html).toContain('撰写准确性与一致性核查')
    expect(html).toContain('临床安全性')
    expect(html.match(/>质控结果</g)).toHaveLength(1)
    expect(html.match(/data-document-identity=/g)).toHaveLength(1)
    expect(html.indexOf('data-result-function-context')).toBeLessThan(
      html.indexOf('data-finding-queue-item'),
    )
    expect(html.match(/data-finding-queue-item=/g)).toHaveLength(2)
    expect(html.indexOf('Product-final first task')).toBeLessThan(
      html.indexOf('Product-final second task'),
    )
    expect(html.match(/data-finding-queue-item="F9"/g)).toHaveLength(1)
    expect(html).not.toContain('处原文')
    expect(html).toContain('data-finding-selected="true"')
    expect(html).toContain('aria-current="true"')
    expect(html).not.toContain('line-clamp-2')
    expect(html).not.toContain('T0001')
    expect(html).not.toContain('Evidence sentence must stay out')
    expect(html).toContain('data-finding-note-preview="true"')
    expect(html).toContain('data-finding-queue-tier="note"')
    expect(html).toContain('Private reviewer note')
    expect(html).toContain('aria-pressed="true"')
    expect(html).not.toContain('4. Clinical safety')
    expect(html).not.toContain('data-result-scope-heading-title')
    expect(html).not.toContain('data-result-section-findings-empty')
    expect(html).not.toContain('data-finding-expanded')
  })

  it('orders fail before need_review while preserving product-final order within each label', () => {
    const mixed: InternalResultFinding[] = [
      {
        findingId: 'N1',
        label: 'need_review',
        conclusion: 'Need review first in product-final',
        comparisonModeId: 'scope_local',
        evidenceRefs: [],
      },
      {
        findingId: 'F1',
        label: 'fail',
        conclusion: 'Fail second in product-final',
        comparisonModeId: 'scope_local',
        evidenceRefs: [],
      },
      {
        findingId: 'N2',
        label: 'need_review',
        conclusion: 'Need review third in product-final',
        comparisonModeId: 'scope_local',
        evidenceRefs: [],
      },
      {
        findingId: 'F2',
        label: 'fail',
        conclusion: 'Fail fourth in product-final',
        comparisonModeId: 'scope_local',
        evidenceRefs: [],
      },
    ]

    const html = renderToStaticMarkup(createElement(ResultFindingsPanel, {
      ...props,
      findings: mixed,
      selectedFindingId: null,
      selectedFinding: null,
      selectedEvidenceLocations: [],
    }))

    const queueItemOrder = [...html.matchAll(/data-finding-queue-item="([^"]+)"/g)].map(
      (match) => match[1],
    )
    expect(queueItemOrder).toEqual(['F1', 'F2', 'N1', 'N2'])
    expect(html.indexOf('Fail second in product-final')).toBeLessThan(
      html.indexOf('Fail fourth in product-final'),
    )
    expect(html.indexOf('Need review first in product-final')).toBeLessThan(
      html.indexOf('Need review third in product-final'),
    )
    expect(html.indexOf('Fail fourth in product-final')).toBeLessThan(
      html.indexOf('Need review first in product-final'),
    )
  })

  it('does not let semantic-module query state filter or reorder the queue', () => {
    const html = renderToStaticMarkup(createElement(ResultFindingsPanel, {
      ...props,
      functionViewQuery: {
        mode: 'semantic_module',
        semanticModuleId: 'clinical_safety',
      },
    }))

    expect(html.match(/data-finding-queue-item=/g)).toHaveLength(2)
    expect(html.indexOf('Product-final first task')).toBeLessThan(
      html.indexOf('Product-final second task'),
    )
  })


  it('renders a Result-level empty state independent of the active outline section', () => {
    const html = renderToStaticMarkup(createElement(ResultFindingsPanel, {
      ...props,
      findings: [],
      selectedFindingId: null,
      selectedFinding: null,
      selectedEvidenceLocations: [],
    }))

    expect(html).toContain('data-result-findings-empty="true"')
    expect(html).toContain('暂无质控结果')
    expect(html).not.toContain('当前章节')
    expect(html).not.toContain('4. Clinical safety')
  })
})

describe('ResultFindingsPanel scroll layout', () => {
  const panelSource = readFileSync(
    resolve(import.meta.dirname, 'result-findings-panel.tsx'),
    'utf8',
  )

  it('keeps panel context in the same scroll viewport as the queue', () => {
    const paneHeaderBlock =
      panelSource.match(
        /<header[\s\S]*?data-result-pane-header[\s\S]*?<\/header>/,
      )?.[0] ?? ''
    expect(paneHeaderBlock).not.toMatch(/sticky/)

    const functionContextBlock =
      panelSource.match(
        /<div className="px-4 pt-3 pb-1">[\s\S]*?ResultFunctionContext[\s\S]*?<\/div>/,
      )?.[0] ?? ''
    expect(functionContextBlock).not.toMatch(/sticky/)

    expect(panelSource).toContain('data-result-findings-scroll="true"')
    expect(panelSource).not.toContain('data-result-findings-context="true"')
    expect(panelSource).not.toContain('data-result-finding-queue-scroll="true"')
    expect(panelSource).toMatch(
      /data-result-findings-scroll="true"[\s\S]*data-result-pane-header[\s\S]*FindingQueue/,
    )
    expect(panelSource).toMatch(
      /\[&_\[data-slot=scroll-area-scrollbar\]\]:z-20/,
    )
    expect(panelSource).not.toContain('TaskSidebarTitle')
  })

  it('renders pane identity, function context, and queue inside one scroll area', () => {
    const html = renderToStaticMarkup(createElement(ResultFindingsPanel, {
      ...props,
    }))

    expect(html).toContain('data-result-findings-scroll="true"')
    const scrollAreaIndex = html.indexOf('data-result-findings-scroll="true"')
    expect(scrollAreaIndex).toBeGreaterThan(-1)
    expect(html.indexOf('data-result-pane-header="true"')).toBeGreaterThan(scrollAreaIndex)
    expect(html.indexOf('data-result-function-context')).toBeGreaterThan(scrollAreaIndex)
    expect(html.indexOf('data-finding-queue="true"')).toBeGreaterThan(
      html.indexOf('data-result-function-context'),
    )
  })
})
