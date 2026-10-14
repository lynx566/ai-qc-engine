import { useMemo } from 'react'
import type { OverviewFindingAnchor } from '@/lib/overview-source-placement'
import { DocumentIdentity } from '@/components/task-run/document-identity'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import {
  FindingQueue,
  type FindingReviewPatchHandler,
} from '@/components/review/finding-queue'
import { FindingReviewWorkspaceLegendTrigger } from '@/components/review/finding-review-workspace-legend'
import { ResultFunctionContext } from '@/components/review/result-function-context'
import type { ResultFunctionViewQuery } from '@/lib/result-function-view-query'
import type {
  InternalResultEvidenceRef,
  InternalResultFinding,
} from '@/types/document-consistency-qc'
import type { DocumentView } from '@/types/document-review'
import type { FindingReviewStatePayload } from '@/types/finding-review'
import { deriveQueueFindings } from '@/lib/finding-queue-order'
import {
  resultReviewContainerBorderClassName,
  resultReviewInternalSeparatorBorderClassName,
} from '@/lib/result-review-visual-tokens'
import { cn } from '@/lib/utils'

export type ResultFindingsPanelProps = {
  onExportReport?: () => void
  exportingReport?: boolean
  taskDisplayName: string
  documentDisplayName: string
  flowId: string
  functionViewQuery: ResultFunctionViewQuery | null
  availableSemanticModuleIds: readonly string[]
  onFunctionViewQueryChange: (query: ResultFunctionViewQuery) => void
  activeOutlineBlockId: string | null
  findings: readonly InternalResultFinding[]
  reviewState: FindingReviewStatePayload | null
  savingFindingId: string | null
  selectionNavigationKey?: string
  selectionNavigationEnabled?: boolean
  onSelectionSettled?: (anchor: OverviewFindingAnchor) => void
  selectedFindingId: string | null
  selectedFinding: InternalResultFinding | null
  selectedEvidenceLocations: readonly InternalResultEvidenceRef[]
  focusedEvidenceLocationKey: string | null
  focusedEvidenceLocation: InternalResultEvidenceRef | null
  onSelectFinding: (findingId: string) => void
  onFocusEvidence: (location: InternalResultEvidenceRef) => void
  onPatchFindingReview: FindingReviewPatchHandler
  document: DocumentView
}

const findingsPanelViewportClassName =
  '[&>div]:!block [&>div]:!w-full [&>div]:!min-w-0 [&>div]:!max-w-full'

export function ResultFindingsPanel({
  onExportReport,
  exportingReport = false,
  taskDisplayName,
  documentDisplayName,
  flowId,
  functionViewQuery,
  availableSemanticModuleIds,
  onFunctionViewQueryChange,
  findings,
  reviewState,
  savingFindingId,
  selectedFindingId,
  selectionNavigationKey,
  selectionNavigationEnabled,
  onSelectionSettled,
  onSelectFinding,
  onPatchFindingReview,
}: ResultFindingsPanelProps) {
  const queueFindings = useMemo(() => deriveQueueFindings(findings), [findings])

  return (
    <div className="flex h-full min-h-0 w-full min-w-0 max-w-full flex-col">
      <ScrollArea
        className="min-h-0 w-full min-w-0 max-w-full flex-1 [&_[data-slot=scroll-area-scrollbar]]:z-20"
        viewportClassName={findingsPanelViewportClassName}
        data-result-findings-scroll="true"
      >
        <header
          className={cn(
            'border-b px-4 pb-3 pt-3',
            resultReviewInternalSeparatorBorderClassName,
          )}
          data-result-pane-header
        >
          <div className="min-w-0 space-y-1">
            <div className="flex min-w-0 flex-wrap items-center justify-between gap-x-2 gap-y-1">
              <h1
                className="min-w-0 break-words text-[15px] font-semibold leading-snug text-[#262626]"
                data-task-page-title
              >
                质控结果
              </h1>
              {onExportReport ? (
                <Button
                  type="button"
                  variant="outline"
                  size="xs"
                  className={cn(
                    resultReviewContainerBorderClassName,
                    'shrink-0 rounded-[4px] whitespace-nowrap',
                  )}
                  data-qc-report-export="true"
                  aria-label="导出报告"
                  aria-busy={exportingReport}
                  disabled={exportingReport}
                  onClick={onExportReport}
                >
                  {exportingReport ? '正在导出…' : '导出报告'}
                </Button>
              ) : null}
            </div>
            <DocumentIdentity
              className="text-[12px]"
              documentTypeLabel={taskDisplayName}
              displayName={documentDisplayName}
            />
          </div>
        </header>

        <div className="px-4 pt-3 pb-1">
          <ResultFunctionContext
            flowId={flowId}
            functionViewQuery={functionViewQuery}
            availableSemanticModuleIds={availableSemanticModuleIds}
            onFunctionViewQueryChange={onFunctionViewQueryChange}
            functionLabelAccessory={<FindingReviewWorkspaceLegendTrigger />}
          />
        </div>

        {findings.length === 0 ? (
          <p
            data-result-findings-empty="true"
            className="px-4 py-8 text-center text-sm text-muted-foreground"
          >
            暂无质控结果
          </p>
        ) : (
          <FindingQueue
            findings={queueFindings}
            reviewState={reviewState}
            selectedFindingId={selectedFindingId}
            selectionNavigationKey={selectionNavigationKey}
            selectionNavigationEnabled={selectionNavigationEnabled}
            onSelectionSettled={onSelectionSettled}
            savingFindingId={savingFindingId}
            onSelectFinding={onSelectFinding}
            onPatchFindingReview={onPatchFindingReview}
          />
        )}
      </ScrollArea>
    </div>
  )
}
