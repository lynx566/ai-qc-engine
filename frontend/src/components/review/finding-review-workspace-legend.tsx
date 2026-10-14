import type { ReactNode } from 'react'
import { Info } from 'lucide-react'

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  FindingReviewConfirmGlyph,
  FindingReviewFlagGlyph,
  FindingReviewIgnoreGlyph,
  FindingReviewNoteGlyph,
} from '@/components/review/finding-review-queue-action-glyphs'
import {
  FINDING_REVIEW_QUEUE_LEFT_EDGE_CLIP_PATH,
  FINDING_REVIEW_QUEUE_LEFT_EDGE_DROP_SHADOW_FILTER,
  FINDING_REVIEW_QUEUE_LEFT_EDGE_POSITION_CLASS,
  FINDING_REVIEW_QUEUE_LEFT_EDGE_WIDTH_CLASS,
  findingReviewQueueLeftEdgeIndicatorClassName,
  type FindingReviewQueueLeftEdge,
} from '@/lib/finding-review-presentation'
import { resultReviewContainerBorderClassName } from '@/lib/result-review-visual-tokens'
import { cn } from '@/lib/utils'

export const FINDING_REVIEW_WORKSPACE_LEGEND_TRIGGER_LABEL = '质控结果说明'

type FindingReviewWorkspaceLegendStatusKey = FindingReviewQueueLeftEdge | 'ignored'

export const FINDING_REVIEW_WORKSPACE_LEGEND_STATUS_ITEMS: ReadonlyArray<{
  key: FindingReviewWorkspaceLegendStatusKey
  label: string
}> = [
  { key: 'fail', label: '存在错误' },
  { key: 'need_review', label: '可能有误' },
  { key: 'confirmed', label: '已确认' },
  { key: 'ignored', label: '已忽略' },
]

export const FINDING_REVIEW_WORKSPACE_LEGEND_ACTION_ITEMS: ReadonlyArray<{
  glyph: ReactNode
  label: string
}> = [
  { glyph: <FindingReviewConfirmGlyph />, label: '确认' },
  { glyph: <FindingReviewIgnoreGlyph />, label: '忽略' },
  { glyph: <FindingReviewFlagGlyph />, label: '标记' },
  { glyph: <FindingReviewNoteGlyph />, label: '笔记' },
]

function FindingReviewQueueLeftEdgeLegendSwatch({
  statusKey,
}: {
  statusKey: FindingReviewWorkspaceLegendStatusKey
}) {
  return (
    <span
      className={cn(
        'relative h-4 w-7 shrink-0 overflow-visible rounded-sm border bg-background',
        resultReviewContainerBorderClassName,
      )}
      data-finding-review-legend-status-swatch={statusKey}
      aria-hidden="true"
    >
      {statusKey !== 'ignored' ? (
        <span
          data-finding-queue-left-edge-indicator
          data-finding-queue-left-edge-tone={statusKey}
          className={cn(
            'pointer-events-none absolute z-[1] rounded-none',
            FINDING_REVIEW_QUEUE_LEFT_EDGE_POSITION_CLASS,
            FINDING_REVIEW_QUEUE_LEFT_EDGE_WIDTH_CLASS,
            'top-[3px] bottom-[3px]',
            findingReviewQueueLeftEdgeIndicatorClassName(statusKey),
          )}
          style={{
            clipPath: FINDING_REVIEW_QUEUE_LEFT_EDGE_CLIP_PATH,
            filter: FINDING_REVIEW_QUEUE_LEFT_EDGE_DROP_SHADOW_FILTER,
          }}
        />
      ) : null}
    </span>
  )
}

export function FindingReviewWorkspaceLegendContent() {
  return (
    <div
      className="text-xs leading-snug text-popover-foreground"
      data-finding-review-workspace-legend="true"
    >
      <div
        className="inline-grid grid-cols-[auto_auto] items-start gap-x-4 gap-y-0"
        data-finding-review-workspace-legend-layout="two-column"
      >
        <div className="min-w-0 space-y-1.5">
          <p className="font-medium text-foreground">状态说明</p>
          <ul className="space-y-1">
            {FINDING_REVIEW_WORKSPACE_LEGEND_STATUS_ITEMS.map((item) => (
              <li
                key={item.key}
                className="flex items-center gap-2"
                data-finding-review-legend-status-row={item.key}
              >
                <FindingReviewQueueLeftEdgeLegendSwatch statusKey={item.key} />
                <span>{item.label}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="min-w-0 space-y-1.5">
          <p className="font-medium text-foreground">操作说明</p>
          <ul className="space-y-1">
            {FINDING_REVIEW_WORKSPACE_LEGEND_ACTION_ITEMS.map((item) => (
              <li
                key={item.label}
                className="flex items-center gap-2"
                data-finding-review-legend-action-row={item.label}
              >
                <span
                  className="inline-flex w-7 shrink-0 items-center justify-center text-slate-500"
                  aria-hidden="true"
                >
                  {item.glyph}
                </span>
                <span>{item.label}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}

export function FindingReviewWorkspaceLegendTrigger() {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className="inline-flex size-5 shrink-0 items-center justify-center rounded-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
            aria-label={FINDING_REVIEW_WORKSPACE_LEGEND_TRIGGER_LABEL}
            data-finding-review-workspace-legend-trigger="true"
          >
            <Info className="size-3.5" aria-hidden="true" />
          </button>
        </TooltipTrigger>
        <TooltipContent
          side="bottom"
          align="start"
          className="max-w-[min(20.5rem,calc(100vw-2rem))] px-2.5 py-1.5"
        >
          <FindingReviewWorkspaceLegendContent />
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
