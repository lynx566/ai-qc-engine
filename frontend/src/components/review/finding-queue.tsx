import { useLayoutEffect, useRef } from 'react'

import { buildFindingPresentation } from '@/lib/finding-review-presentation'
import {
  FINDING_REVIEW_QUEUE_LEFT_EDGE_CLIP_PATH,
  FINDING_REVIEW_QUEUE_LEFT_EDGE_DROP_SHADOW_FILTER,
  FINDING_REVIEW_QUEUE_LEFT_EDGE_POSITION_CLASS,
  FINDING_REVIEW_QUEUE_LEFT_EDGE_WIDTH_CLASS,
  FINDING_REVIEW_QUEUE_LEFT_EDGE_VERTICAL_INSET_CLASS,
  findingReviewQueueCardShellClassName,
  findingReviewQueueLeftEdgeIndicatorClassName,
  findingReviewQueueSelectFocusRingClassName,
  resolveFindingReviewQueueLeftEdge,
} from '@/lib/finding-review-presentation'
import { findingVerdictAccessibleLabel } from '@/lib/finding-verdict-presentation'
import {
  anchorSelectedFindingInQueueViewport,
  resolveFindingQueueScrollViewport,
} from '@/lib/finding-queue-selection-scroll'
import {
  FindingReviewCard,
  type FindingReviewPatchHandler,
} from '@/components/review/finding-review-card'
import { cn } from '@/lib/utils'
import { startFindingQueueSelectionNavigation } from '@/lib/finding-queue-selection-navigation'
import type { OverviewFindingAnchor } from '@/lib/overview-source-placement'
import type { InternalResultFinding } from '@/types/document-consistency-qc'
import type { FindingReviewStatePayload } from '@/types/finding-review'

export type { FindingReviewPatchHandler } from '@/components/review/finding-review-card'

type FindingQueueProps = {
  findings: readonly InternalResultFinding[]
  reviewState: FindingReviewStatePayload | null
  selectedFindingId: string | null
  selectionNavigationKey?: string
  selectionNavigationEnabled?: boolean
  onSelectionSettled?: (anchor: OverviewFindingAnchor) => void
  savingFindingId: string | null
  onSelectFinding: (findingId: string) => void
  onPatchFindingReview: FindingReviewPatchHandler
}

function FindingQueueItem({
  presentation,
  queuePosition,
  queueTotal,
  selected,
  saving,
  onSelectFinding,
  onPatchFindingReview,
}: {
  presentation: ReturnType<typeof buildFindingPresentation>
  queuePosition: number
  queueTotal: number
  selected: boolean
  saving: boolean
  onSelectFinding: (findingId: string) => void
  onPatchFindingReview: FindingReviewPatchHandler
}) {
  const { finding } = presentation
  const hasNote = Boolean(presentation.note)
  const leftEdge = resolveFindingReviewQueueLeftEdge(presentation.decision, finding.label)
  const selectionLabel = `${findingVerdictAccessibleLabel(finding.label)}：${finding.conclusion}`

  return (
    <li
      className={cn(
        'rounded-md border-[1.3px] px-2 py-2.5 transition-colors',
        findingReviewQueueCardShellClassName(selected, leftEdge),
      )}
      data-finding-queue-item={finding.findingId}
      data-finding-selected={selected ? 'true' : 'false'}
      data-finding-decision={presentation.decision}
      data-finding-marked={presentation.marked ? 'true' : 'false'}
      data-finding-has-note={hasNote ? 'true' : 'false'}
      data-finding-queue-card-treatment={selected ? 'selected' : 'default'}
      data-finding-queue-left-edge={leftEdge ?? 'none'}
      data-finding-queue-position={queuePosition}
      data-finding-queue-position-total={queueTotal}
    >
      {leftEdge !== null ? (
        <span
          aria-hidden="true"
          data-finding-queue-left-edge-indicator
          data-finding-queue-left-edge-tone={leftEdge}
          className={cn(
            'pointer-events-none absolute z-[1] rounded-none',
            FINDING_REVIEW_QUEUE_LEFT_EDGE_POSITION_CLASS,
            FINDING_REVIEW_QUEUE_LEFT_EDGE_WIDTH_CLASS,
            FINDING_REVIEW_QUEUE_LEFT_EDGE_VERTICAL_INSET_CLASS,
            findingReviewQueueLeftEdgeIndicatorClassName(leftEdge),
          )}
          style={{
            clipPath: FINDING_REVIEW_QUEUE_LEFT_EDGE_CLIP_PATH,
            filter: FINDING_REVIEW_QUEUE_LEFT_EDGE_DROP_SHADOW_FILTER,
          }}
        />
      ) : null}
      <button
        type="button"
        data-finding-queue-select="true"
        className={cn(
          'absolute inset-0 z-0 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-offset-0',
          findingReviewQueueSelectFocusRingClassName(),
        )}
        aria-label={selectionLabel}
        aria-current={selected ? 'true' : undefined}
        onClick={() => onSelectFinding(finding.findingId)}
      />
      <div className="relative z-10 flex min-w-0 flex-col gap-1 pointer-events-none">
        <p
          className="text-xs tabular-nums text-muted-foreground"
          data-finding-queue-position-label="true"
        >
          {queuePosition} / {queueTotal}
        </p>
        <FindingReviewCard
          presentation={presentation}
          saving={saving}
          onPatchFindingReview={onPatchFindingReview}
          onSelectFinding={onSelectFinding}
        />
      </div>
    </li>
  )
}

export function FindingQueue({
  findings,
  reviewState,
  selectedFindingId,
  selectionNavigationKey,
  selectionNavigationEnabled = true,
  onSelectionSettled,
  savingFindingId,
  onSelectFinding,
  onPatchFindingReview,
}: FindingQueueProps) {
  const queueRef = useRef<HTMLOListElement>(null)

  const onSelectionSettledRef = useRef(onSelectionSettled)
  onSelectionSettledRef.current = onSelectionSettled

  useLayoutEffect(() => {
    const queueEl = queueRef.current
    if (!selectionNavigationEnabled || selectedFindingId === null || queueEl === null) return
    const viewport = resolveFindingQueueScrollViewport(queueEl)
    if (!viewport) return
    let frame = 0
    let cancelNavigation: (() => void) | undefined
    const navigate = () => {
      cancelAnimationFrame(frame)
      cancelNavigation?.()
      frame = requestAnimationFrame(() => {
        const selectedItem = queueEl.querySelector<HTMLElement>(
          '[data-finding-queue-item="' + selectedFindingId + '"]',
        )
        if (!selectedItem) return
        if (!onSelectionSettledRef.current) {
          anchorSelectedFindingInQueueViewport(viewport, selectedItem)
          return
        }
        if (viewport.clientHeight <= 0 || selectedItem.getBoundingClientRect().height <= 0) return
        cancelNavigation = startFindingQueueSelectionNavigation(viewport, selectedItem, centerScreenY => {
          onSelectionSettledRef.current?.({ findingId: selectedFindingId, centerScreenY })
        })
      })
    }
    navigate()
    let width = viewport.clientWidth
    let height = viewport.clientHeight
    const observer = new ResizeObserver(() => {
      const nextWidth = viewport.clientWidth
      const nextHeight = viewport.clientHeight
      if (width !== nextWidth || height !== nextHeight) {
        width = nextWidth
        height = nextHeight
        navigate()
      }
    })
    observer.observe(viewport)
    window.addEventListener('resize', navigate)
    return () => {
      cancelAnimationFrame(frame)
      cancelNavigation?.()
      observer.disconnect()
      window.removeEventListener('resize', navigate)
    }
  }, [selectedFindingId, selectionNavigationEnabled, selectionNavigationKey])

  return (
    <ol
      ref={queueRef}
      className="w-full min-w-0 max-w-full space-y-4 px-3 pb-3 pt-1"
      data-finding-queue="true"
    >
      {findings.map((finding, index) => (
        <FindingQueueItem
          key={finding.findingId}
          presentation={buildFindingPresentation(finding, reviewState)}
          queuePosition={index + 1}
          queueTotal={findings.length}
          selected={finding.findingId === selectedFindingId}
          saving={savingFindingId !== null}
          onSelectFinding={onSelectFinding}
          onPatchFindingReview={onPatchFindingReview}
        />
      ))}
    </ol>
  )
}
