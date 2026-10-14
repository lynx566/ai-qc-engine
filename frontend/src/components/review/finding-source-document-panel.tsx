import { useMemo } from 'react'
import type { OverviewFindingAnchor } from '@/lib/overview-source-placement'
import { useOverviewSourcePlacement } from '@/lib/use-overview-source-placement'

import {
  SourceEvidenceViewportWorkspace,
  type SourceEvidenceViewportWorkspaceProps,
} from '@/components/review/source-evidence-viewport-workspace'
import { resultFindingSourceDocumentPanelClassName } from '@/lib/result-review-stage-layout'
import { deriveFindingSourceViewportState } from '@/lib/finding-source-viewport-state'
import type { SlotDocumentLoadStatus } from '@/lib/slot-document-state'
import type { InternalResultEvidenceRef } from '@/types/document-consistency-qc'
import type { DocumentView } from '@/types/document-review'

export type FindingSourceDocumentPanelProps = Omit<
  SourceEvidenceViewportWorkspaceProps,
  'document' | 'descriptors' | 'sourceContentRef'
> & {
  findingId: string | null
  slotId: string
  document: DocumentView
  documentStatus: SlotDocumentLoadStatus
  documentError: string | null
  evidenceLocations: readonly InternalResultEvidenceRef[]
  overviewFindingAnchor: OverviewFindingAnchor | null
  overviewPresentationKey?: string
  overviewPairActive?: boolean
}

export function FindingSourceDocumentPanel({
  findingId,
  slotId,
  document,
  documentStatus,
  documentError,
  evidenceLocations,
  overviewFindingAnchor,
  overviewPresentationKey,
  overviewPairActive = true,
  ...interaction
}: FindingSourceDocumentPanelProps) {
  const state = useMemo(
    () => deriveFindingSourceViewportState({
      findingId,
      slotId,
      document,
      evidenceLocations,
    }),
    [document, evidenceLocations, findingId, slotId],
  )

  const overviewPlacement = useOverviewSourcePlacement({
    enabled: overviewPairActive && documentStatus === 'ready' && state.kind === 'ready',
    findingId,
    anchor: overviewFindingAnchor,
    presentationKey: overviewPresentationKey,
  })
  const pending = overviewPairActive && overviewPlacement.placement.status === 'pending'
  const placement = !overviewPairActive
    ? { mode: 'top' as const, topPx: 0 }
    : overviewPlacement.placement.status === 'ready' ? overviewPlacement.placement : null

  if (documentStatus === 'loading') {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-sm text-muted-foreground">
        正在加载文档…
      </div>
    )
  }

  if (documentStatus === 'error') {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-sm text-destructive">
        {documentError ?? '文档加载失败'}
      </div>
    )
  }

  if (state.kind === 'empty') {
    return (
      <div data-finding-source-empty="true" className="flex flex-1 items-center justify-center p-8 text-sm text-muted-foreground">
        No source context is available for this finding.
      </div>
    )
  }

  if (state.kind === 'unavailable') {
    return (
      <div data-finding-source-unavailable="true" className="flex flex-1 items-center justify-center p-8 text-sm text-muted-foreground">
        Source evidence is unavailable for the active document.
      </div>
    )
  }

  return (
    <div
      ref={overviewPlacement.viewportRef}
      data-finding-source-document-panel="true"
      data-overview-source-placement-viewport="true"
      className={resultFindingSourceDocumentPanelClassName}
    >
      <div
        data-result-review-source-placement="true"
        data-result-review-source-placement-status={overviewPairActive ? pending ? 'pending' : 'ready' : undefined}
        data-result-review-source-alignment-mode={pending ? 'pending' : placement?.mode}
        style={pending
          ? { visibility: 'hidden' }
          : placement && placement.topPx > 0 ? { paddingTop: placement.topPx } : undefined}
      >
        <SourceEvidenceViewportWorkspace
          document={document}
          descriptors={state.descriptors}
          sourceContentRef={overviewPlacement.contentRef}
          {...interaction}
        />
      </div>
    </div>
  )
}
