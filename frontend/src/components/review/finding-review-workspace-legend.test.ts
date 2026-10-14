// @vitest-environment happy-dom

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ResultFindingsPanel } from '@/components/review/result-findings-panel'
import {
  FINDING_REVIEW_WORKSPACE_LEGEND_ACTION_ITEMS,
  FINDING_REVIEW_WORKSPACE_LEGEND_STATUS_ITEMS,
  FINDING_REVIEW_WORKSPACE_LEGEND_TRIGGER_LABEL,
  FindingReviewWorkspaceLegendContent,
  FindingReviewWorkspaceLegendTrigger,
} from '@/components/review/finding-review-workspace-legend'
import { renderToStaticMarkup } from 'react-dom/server'
import type { InternalResultFinding } from '@/types/document-consistency-qc'
import type { DocumentView } from '@/types/document-review'

const panelSource = readFileSync(
  resolve(import.meta.dirname, 'result-findings-panel.tsx'),
  'utf8',
)
const cardSource = readFileSync(
  resolve(import.meta.dirname, 'finding-review-card.tsx'),
  'utf8',
)
const legendSource = readFileSync(
  resolve(import.meta.dirname, 'finding-review-workspace-legend.tsx'),
  'utf8',
)

const documentView: DocumentView = {
  docId: 'doc_test',
  fileName: 'sample.docx',
  displayName: 'sample.docx',
  blocks: [],
}

const findings: InternalResultFinding[] = [
  {
    findingId: 'F1',
    label: 'fail',
    conclusion: 'Sample finding',
    comparisonModeId: 'scope_local',
    evidenceRefs: [],
  },
]

function mountLegendTrigger(): { host: HTMLElement; root: Root } {
  const host = document.createElement('div')
  window.document.body.appendChild(host)
  const root = createRoot(host)
  act(() => {
    root.render(createElement(FindingReviewWorkspaceLegendTrigger))
  })
  return { host, root }
}

describe('FindingReviewWorkspaceLegend', () => {
  it('renders status and action legend rows with queue left-edge tokens', () => {
    const html = renderToStaticMarkup(createElement(FindingReviewWorkspaceLegendContent))

    expect(html).toContain('data-finding-review-workspace-legend="true"')
    expect(html).toContain('data-finding-review-workspace-legend-layout="two-column"')
    expect(html).toContain('grid-cols-[auto_auto]')
    expect(html).toContain('状态说明')
    expect(html).toContain('操作说明')
    expect(html.indexOf('状态说明')).toBeLessThan(html.indexOf('操作说明'))

    for (const item of FINDING_REVIEW_WORKSPACE_LEGEND_STATUS_ITEMS) {
      expect(html).toContain(item.label)
      expect(html).toContain(`data-finding-review-legend-status-row="${item.key}"`)
      expect(html).toContain(`data-finding-review-legend-status-swatch="${item.key}"`)
    }

    for (const item of FINDING_REVIEW_WORKSPACE_LEGEND_ACTION_ITEMS) {
      expect(html).toContain(item.label)
      expect(html).toContain(`data-finding-review-legend-action-row="${item.label}"`)
    }

    expect(html).toContain('data-finding-queue-left-edge-indicator')
    expect(html).toContain('data-finding-queue-left-edge-tone="fail"')
    expect(html).toContain('bg-red-500')
    expect(html).toContain('bg-amber-400')
    expect(html).toContain('bg-slate-400')
    expect(legendSource).toContain('findingReviewQueueLeftEdgeIndicatorClassName')
    expect(legendSource).toContain('FINDING_REVIEW_QUEUE_LEFT_EDGE_CLIP_PATH')
  })

  it('reuses shared action glyph components with FindingReviewCard', () => {
    expect(cardSource).toContain('FindingReviewConfirmGlyph')
    expect(cardSource).toContain('FindingReviewIgnoreGlyph')
    expect(cardSource).toContain('FindingReviewFlagGlyph')
    expect(cardSource).toContain('FindingReviewNoteGlyph')
    expect(legendSource).toContain('FindingReviewConfirmGlyph')

    const html = renderToStaticMarkup(createElement(FindingReviewWorkspaceLegendContent))
    expect(html).toContain('data-finding-review-action-glyph="confirm"')
    expect(html).toContain('data-finding-review-action-glyph="ignore"')
    expect(html).toContain('data-finding-review-action-glyph="flag"')
    expect(html).toContain('data-finding-review-action-glyph="note"')
    expect(html).toContain('lucide-check')
    expect(html).toContain('lucide-eye-closed')
    expect(html).toContain('lucide-flag')
    expect(html).toContain('lucide-pencil')
  })

  it('renders a lightweight info trigger without requiring click', () => {
    const html = renderToStaticMarkup(createElement(FindingReviewWorkspaceLegendTrigger))

    expect(html).toContain('data-finding-review-workspace-legend-trigger="true"')
    expect(html).toContain(`aria-label="${FINDING_REVIEW_WORKSPACE_LEGEND_TRIGGER_LABEL}"`)
    expect(html).toContain('lucide-info')
    expect(html).toContain('data-slot="tooltip-trigger"')
    expect(html).not.toContain('data-slot="dialog"')
  })
})

describe('FindingReviewWorkspaceLegend interaction', () => {
  let host: HTMLElement
  let root: Root

  beforeEach(() => {
    const mounted = mountLegendTrigger()
    host = mounted.host
    root = mounted.root
  })

  afterEach(() => {
    act(() => root.unmount())
    host.remove()
  })

  function queryLegend(): HTMLElement | null {
    return window.document.body.querySelector('[data-finding-review-workspace-legend="true"]')
  }

  it('reveals the legend on keyboard focus without click', () => {
    const trigger = host.querySelector<HTMLButtonElement>(
      '[data-finding-review-workspace-legend-trigger="true"]',
    )!

    expect(queryLegend()).toBeNull()

    act(() => {
      trigger.focus()
    })

    expect(queryLegend()).not.toBeNull()
    expect(queryLegend()?.textContent).toContain('存在错误')
    expect(queryLegend()?.textContent).toContain('笔记')
  })

  it('reveals the legend on pointer hover without click', async () => {
    vi.useFakeTimers()
    const trigger = host.querySelector<HTMLButtonElement>(
      '[data-finding-review-workspace-legend-trigger="true"]',
    )!

    expect(queryLegend()).toBeNull()
    expect(trigger.getAttribute('data-state')).toBe('closed')

    await act(async () => {
      trigger.dispatchEvent(
        new PointerEvent('pointermove', { bubbles: true, pointerType: 'mouse' }),
      )
      await vi.runAllTimersAsync()
    })

    await vi.waitFor(() => {
      const state = trigger.getAttribute('data-state')
      expect(state === 'open' || state === 'delayed-open').toBe(true)
      expect(queryLegend()).not.toBeNull()
    })

    expect(queryLegend()?.textContent).toContain('已忽略')
    expect(queryLegend()?.textContent).toContain('标记')
    vi.useRealTimers()
  })
})

describe('ResultFindingsPanel legend placement', () => {
  it('renders the help trigger beside the function title', () => {
    const html = renderToStaticMarkup(
      createElement(ResultFindingsPanel, {
        taskDisplayName: 'DSUR',
        documentDisplayName: documentView.displayName,
        flowId: 'document_consistency_qc',
        functionViewQuery: { mode: 'all' },
        availableSemanticModuleIds: ['clinical_safety'],
        onFunctionViewQueryChange: () => {},
        activeOutlineBlockId: null,
        findings,
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
        document: documentView,
      }),
    )

    expect(panelSource).toContain('FindingReviewWorkspaceLegendTrigger')
    expect(html).toContain('撰写准确性与一致性核查')
    expect(html).toContain('data-finding-review-workspace-legend-trigger="true"')
    expect(html.indexOf('data-result-function-label')).toBeLessThan(
      html.indexOf('data-finding-review-workspace-legend-trigger="true"'),
    )
    expect(html.indexOf('data-finding-review-workspace-legend-trigger="true"')).toBeLessThan(
      html.indexOf('data-result-function-scope-label'),
    )
  })
})
