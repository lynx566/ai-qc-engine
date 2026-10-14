import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ExtractBundleDto } from '@/adapters/extract-bundle.dto'
import { adaptExtractBundleToDocumentView, composeDocumentBlockId } from '@/adapters/extract-document'
import { buildSidebarEntries } from '@/adapters/candidate-scope-view'
import { QcSetupShellLoaded, toReaderBlockId } from '@/components/qc-setup/qc-setup-shell'
import type { CandidateScopeSlotState } from '@/types/candidate-scope'

const fixtureDir = dirname(fileURLToPath(import.meta.url))
const showcaseBundle = JSON.parse(
  readFileSync(
    join(fixtureDir, '../../../fixtures/extract/canonical-showcase-bundle.json'),
    'utf8',
  ),
) as ExtractBundleDto

describe('qc setup runtime document wiring', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('does not import showcase fixture from candidate scope page module', async () => {
    const source = readFileSync(
      join(fixtureDir, '../../pages/qc-setup-page.tsx'),
      'utf8',
    )
    expect(source).not.toContain('canonical-showcase-bundle.json')
    expect(source).not.toContain('adaptExtractBundleToDocumentView')
  })

  it('keeps anchor scroll targets aligned with runtime reader block ids', () => {
    const document = adaptExtractBundleToDocumentView(showcaseBundle)
    const slotState: CandidateScopeSlotState = {
      slotId: 'source',
      docId: document.docId,
      automaticAnchorBlockIds: ['C0006'],
      currentAnchorBlockIds: ['C0006'],
      headings: [
        {
          docId: document.docId,
          filterJobId: 'dsur_overview',
          anchorBlockId: 'C0006',
          title: '执行概要',
          headingPath: ['执行概要'],
          level: 1,
          docOrderIndex: 3,
        },
      ],
    }

    const entries = buildSidebarEntries(slotState, new Set(['C0006']))
    const leaf = entries.find((entry) => entry.kind === 'leaf')
    expect(leaf?.kind).toBe('leaf')
    if (leaf?.kind !== 'leaf') {
      return
    }

    const readerBlockId = toReaderBlockId(slotState.docId, 'C0006')
    expect(leaf.scrollTargetBlockId).toBe(readerBlockId)
    expect(document.blocks.some((block) => block.blockId === readerBlockId)).toBe(true)
    expect(readerBlockId).toBe(composeDocumentBlockId(document.docId, 'C0006'))
  })

  it('renders loading state while active slot document is not ready', () => {
    const html = renderToStaticMarkup(
      createElement(QcSetupShellLoaded, {
        taskDisplayName: 'DSUR',
        document: {
          docId: 'doc_test',
          fileName: 'pending.docx',
          displayName: 'pending.docx',
          blocks: [],
        },
        documentsBySlotId: {},
        documentStatus: 'loading',
        documentError: null,
        flowState: {
          flowId: 'document_consistency_qc',
          flowRunId: 'flow_1',
          capabilityId: 'internal_dsur',
          capabilityTitle: 'title',
          flowStatus: 'paused_at_candidate_scope',
          canResume: true,
          contentDomainGroups: [
            {
              contentDomainId: 'clinical_safety',
              displayLabel: '临床安全性',
              filterJobIds: ['dsur_clinical_safety', 'dsur_overview'],
            },
          ],
          slots: [
            {
              slotId: 'source',
              docId: 'doc_test',
              automaticAnchorBlockIds: [],
              currentAnchorBlockIds: [],
              headings: [],
            },
          ],
        },
        activeSlot: {
          slotId: 'source',
          docId: 'doc_test',
          automaticAnchorBlockIds: [],
          currentAnchorBlockIds: [],
          headings: [],
        },
        activeReview: {
          currentSelected: new Set(),
          draftSelected: new Set(),
          isEditing: false,
        },
        focusedBlockId: null,
        onClearFocusedBlock: () => {},
        onSelectSlot: () => {},
        onStartEdit: () => {},
        onApply: () => {},
        onCancelEdit: () => {},
        onToggleHeading: () => {},
        onScrollToBlock: () => {},
        nextStatus: 'idle',
        nextError: null,
        onNext: () => {},
        onProceedToResult: () => {},
        taskState: {
          inputReady: true,
          productPhase: 'flow_execution_requested',
          productFailure: null,
          allocatedFlow: {
            flowId: 'document_consistency_qc',
            flowRunId: 'flow_runtime_test',
          },
          flowOutcome: 'paused_at_candidate_scope',
          requiresUserAction: true,
          resultAvailable: false,
        },
        isNextDisabled: false,
      }),
    )

    expect(html).toContain('正在加载文档')
  })
})
