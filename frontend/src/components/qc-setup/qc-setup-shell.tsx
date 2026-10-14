import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'

import {
  buildCandidateScopeNextRequest,
  fetchCandidateScopeState,
  submitCandidateScopeNext,
} from '@/api/candidate-scope'
import { DocumentConsistencyQcApiError } from '@/api/document-consistency-qc-error'
import { composeDocumentBlockId } from '@/adapters/extract-document'
import { QcSetupSidebar } from '@/components/qc-setup/qc-setup-sidebar'
import { TaskSidebarTitle } from '@/components/task-run/task-sidebar-title'
import { DocumentIdentity } from '@/components/task-run/document-identity'
import { DocumentReader } from '@/components/review/document-reader'
import { Button } from '@/components/ui/button'
import { canonicalizeDraftSelection } from '@/lib/candidate-scope-selection'
import { blockDomId } from '@/lib/document-anchors'
import { scrollElementIntoReaderView } from '@/lib/document-navigation'
import { getFlowParticipantFileContextLabel } from '@/lib/launcher-presentation'
import { useBlockNavigationFocus } from '@/lib/use-block-navigation-focus'
import {
  resolveQcSetupProductMessage,
  RESULT_FLOW_FAILED_USER_MESSAGE,
  RESULT_NOT_READY_USER_MESSAGE,
  TASK_STATE_REFRESH_FAILED_USER_MESSAGE,
} from '@/lib/task-run-product-state'
import {
  getActiveDocument,
  getActiveDocumentLoadStatus,
  type SlotDocumentLoadStatus,
} from '@/lib/slot-document-state'
import { useSlotDocumentLoader } from '@/lib/use-slot-document-loader'
import {
  anySlotBlocksNext,
  buildAppliedSelectionsBySlotId,
  createInitialSlotReviews,
  getActiveSlotState,
  resolveInitialActiveSlotId,
} from '@/lib/slot-review-state'
import type {
  CandidateHeading,
  CandidateScopeFlowState,
  CandidateScopeSlotState,
  DocumentTypeDiagnostic,
  SlotReviewState,
} from '@/types/candidate-scope'
import type { QcExecutionStatus } from '@/types/qc-setup'
import type { DocumentView } from '@/types/document-review'
import type { TaskRunState } from '@/types/task-run'
import { cn } from '@/lib/utils'

type QcSetupShellProps = {
  taskDisplayName: string
  flowRunId: string
  onProceedToResult: () => void
  taskState: TaskRunState
  refreshTaskRunState: () => Promise<TaskRunState | null>
}

export type QcSetupShellLoadedProps = {
  taskDisplayName: string
  document: DocumentView
  documentsBySlotId: Record<string, DocumentView>
  documentStatus: SlotDocumentLoadStatus
  documentError: string | null
  flowState: CandidateScopeFlowState
  activeSlot: CandidateScopeSlotState
  activeReview: SlotReviewState
  focusedBlockId: string | null
  onClearFocusedBlock: () => void
  onSelectSlot: (slotId: string) => void
  onStartEdit: () => void
  onApply: () => void
  onCancelEdit: () => void
  onToggleHeading: (heading: CandidateHeading, checked: boolean) => void
  onScrollToBlock: (blockId: string) => void
  nextStatus: QcExecutionStatus
  nextError: string | null
  onNext: () => void
  taskState: TaskRunState
  isNextDisabled: boolean
}

function DocumentTypeWarning({ diagnostic }: { diagnostic?: DocumentTypeDiagnostic }) {
  if (diagnostic?.status !== 'mismatch' && diagnostic?.status !== 'uncertain') {
    return null
  }
  return (
    <p className="flex items-start gap-1.5 text-[12px] leading-5 text-[#667085]">
      <span aria-hidden="true" className="mt-0.5 size-3.5 shrink-0 text-[14px] leading-none text-amber-500">
        {'⚠ '}
      </span>
      <span className="min-w-0">{`请确认上传文件是否为 ${diagnostic.expectedDocumentType}。`}</span>
    </p>
  )
}

function QcSetupFlowHeader({
  taskDisplayName,
  flowState,
  documentsBySlotId,
  activeSlotId,
  onSelectSlot,
}: {
  taskDisplayName: string
  flowState: CandidateScopeFlowState
  documentsBySlotId: Record<string, DocumentView>
  activeSlotId: string
  onSelectSlot: (slotId: string) => void
}) {
  const isMultiFile = flowState.slots.length > 1

  return (
    <div className="shrink-0 px-5 pt-4 pb-0">
      <div className="space-y-1">
        <TaskSidebarTitle taskDisplayName="质控功能" context="qc-setup" />
        {isMultiFile ? (
          <div className="space-y-2 pt-1">
            {flowState.slots.map((slot) => {
              const slotLabel = getFlowParticipantFileContextLabel(
                flowState.capabilityId,
                slot.slotId,
              )
              const displayName =
                documentsBySlotId[slot.slotId]?.displayName ?? slot.slotId
              const isActive = slot.slotId === activeSlotId
              return (
                <div key={slot.slotId} className="space-y-0.5">
                  {slotLabel ? (
                    <p className="text-[12px] font-bold tracking-wide text-[#8C8C8C] uppercase">
                      {slotLabel}
                    </p>
                  ) : null}
                  <Button
                    type="button"
                    variant="ghost"
                    className={cn(
                      'h-auto w-full justify-start rounded-md px-2.5 py-1.5 text-left text-[13px] font-normal whitespace-normal break-all',
                      isActive
                        ? 'bg-[#F0F5FF] font-semibold text-[#1890FF] hover:bg-[#F0F5FF]'
                        : 'text-[#595959] hover:bg-[#F0F5FF]/60',
                    )}
                    onClick={() => onSelectSlot(slot.slotId)}
                  >
                    {displayName}
                  </Button>
                  <DocumentTypeWarning diagnostic={slot.documentTypeDiagnostic} />
                </div>
              )
            })}
          </div>
        ) : (
          <>
            <DocumentIdentity
              documentTypeLabel={taskDisplayName}
              displayName={
                documentsBySlotId[flowState.slots[0]?.slotId ?? '']?.displayName ??
                flowState.slots[0]?.slotId ??
                ''
              }
            />
            <DocumentTypeWarning diagnostic={flowState.slots[0]?.documentTypeDiagnostic} />
          </>
        )}
      </div>
    </div>
  )
}

function DocumentMainPanel({
  document,
  documentStatus,
  documentError,
  slotId,
  focusedBlockId,
  onClearFocusedBlock,
}: {
  document: DocumentView
  documentStatus: SlotDocumentLoadStatus
  documentError: string | null
  slotId: string
  focusedBlockId: string | null
  onClearFocusedBlock: () => void
}) {
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

  return (
    <DocumentReader
      document={document}
      slotId={slotId}
      focusedBlockId={focusedBlockId}
      onClearFocusedBlock={onClearFocusedBlock}
      contentPlacement="expanded"
      canvasLayout="workspace"
    />
  )
}

export function QcSetupShellLoaded({
  taskDisplayName,
  document,
  documentsBySlotId,
  documentStatus,
  documentError,
  flowState,
  activeSlot,
  activeReview,
  focusedBlockId,
  onClearFocusedBlock,
  onSelectSlot,
  onStartEdit,
  onApply,
  onCancelEdit,
  onToggleHeading,
  onScrollToBlock,
  nextStatus,
  nextError,
  onNext,
  taskState,
  isNextDisabled,
}: QcSetupShellLoadedProps) {
  const productMessage = resolveQcSetupProductMessage(taskState)
  return (
    <div className="flex h-full min-h-0 w-full overflow-hidden launcher-tech-bg max-[840px]:grid max-[840px]:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] max-[840px]:grid-rows-[minmax(0,1fr)]">
      <main className="flex min-h-0 min-w-0 flex-1 flex-col bg-[#F2F4F7]">
        {productMessage ? (
          <div className="border-b bg-background px-4 py-3 text-sm text-destructive">
            {productMessage}
          </div>
        ) : null}
        <DocumentMainPanel
          document={document}
          documentStatus={documentStatus}
          documentError={documentError}
          slotId={activeSlot.slotId}
          focusedBlockId={focusedBlockId}
          onClearFocusedBlock={onClearFocusedBlock}
        />
      </main>

      <aside className="flex h-full min-h-0 flex-col border-l border-[#D8DEE7] bg-white max-[840px]:min-w-0 min-[840px]:w-96 min-[840px]:shrink-0">
        <QcSetupFlowHeader
          taskDisplayName={taskDisplayName}
          flowState={flowState}
          documentsBySlotId={documentsBySlotId}
          activeSlotId={activeSlot.slotId}
          onSelectSlot={onSelectSlot}
        />

        <QcSetupSidebar
          flowId={flowState.flowId}
          slotState={activeSlot}
          contentDomainGroups={flowState.contentDomainGroups}
          currentSelected={activeReview.currentSelected}
          draftSelected={activeReview.draftSelected}
          isEditing={activeReview.isEditing}
          onStartEdit={onStartEdit}
          onApply={onApply}
          onCancelEdit={onCancelEdit}
          onToggleHeading={onToggleHeading}
          onScrollToBlock={onScrollToBlock}
          focusedBlockId={focusedBlockId}
          nextStatus={nextStatus}
          nextError={nextError}
          onNext={onNext}
          isNextDisabled={isNextDisabled}
          canResume={flowState.canResume}
        />
      </aside>
    </div>
  )
}

export function QcSetupShell({
  taskDisplayName,
  flowRunId,
  onProceedToResult,
  taskState,
  refreshTaskRunState,
}: QcSetupShellProps) {
  const [flowState, setFlowState] = useState<CandidateScopeFlowState | null>(null)
  const [activeSlotId, setActiveSlotId] = useState<string | null>(null)
  const [slotReviews, setSlotReviews] = useState<Record<string, SlotReviewState>>({})
  const slotDocumentState = useSlotDocumentLoader(flowRunId, flowState?.slots ?? [])
  const { focusedBlockId, focusBlock, clearBlockFocus } = useBlockNavigationFocus()
  const [loadError, setLoadError] = useState<string | null>(null)
  const [nextStatus, setNextStatus] = useState<QcExecutionStatus>('idle')
  const [nextError, setNextError] = useState<string | null>(null)
  const [submittedFlowRunId, setSubmittedFlowRunId] = useState<string | null>(null)
  const nextAttemptRef = useRef(0)

  useLayoutEffect(() => {
    return () => {
      nextAttemptRef.current += 1
    }
  }, [flowRunId])

  const activeSlot = useMemo(() => {
    if (!flowState || !activeSlotId) {
      return null
    }
    return getActiveSlotState(flowState, activeSlotId) ?? null
  }, [flowState, activeSlotId])

  const activeReview = activeSlotId ? slotReviews[activeSlotId] : undefined
  const activeDocument = getActiveDocument(slotDocumentState, activeSlotId)
  const activeDocumentStatus = getActiveDocumentLoadStatus(slotDocumentState, activeSlotId)
  const activeDocumentError = activeSlotId
    ? slotDocumentState.documentErrorBySlotId[activeSlotId] ?? null
    : null

  const headingsByAnchor = useMemo(() => {
    const map = new Map<string, CandidateHeading>()
    for (const heading of activeSlot?.headings ?? []) {
      map.set(heading.anchorBlockId, heading)
    }
    return map
  }, [activeSlot])

  const loadScope = useCallback(async () => {
    try {
      const state = await fetchCandidateScopeState(flowRunId)
      setFlowState(state)
      setActiveSlotId(resolveInitialActiveSlotId(state))
      setSlotReviews(createInitialSlotReviews(state))
      setLoadError(null)
    } catch (error) {
      const message =
        error instanceof DocumentConsistencyQcApiError ? error.message : '候选范围加载失败'
      setLoadError(message)
    }
  }, [flowRunId])

  useEffect(() => {
    void loadScope()
  }, [loadScope])

  const handleSelectSlot = useCallback(
    (slotId: string) => {
      clearBlockFocus()
      setActiveSlotId(slotId)
    },
    [clearBlockFocus],
  )

  const updateActiveReview = useCallback(
    (updater: (review: SlotReviewState) => SlotReviewState) => {
      if (!activeSlotId) {
        return
      }
      setSlotReviews((previous) => {
        const current = previous[activeSlotId]
        if (!current) {
          return previous
        }
        return {
          ...previous,
          [activeSlotId]: updater(current),
        }
      })
    },
    [activeSlotId],
  )

  const scrollToBlock = useCallback(
    (blockId: string) => {
      const target = window.document.getElementById(blockDomId(blockId))
      if (!target) {
        return
      }
      scrollElementIntoReaderView(target)
      focusBlock(blockId)
    },
    [focusBlock],
  )

  const handleStartEdit = useCallback(() => {
    updateActiveReview((review) => ({
      ...review,
      draftSelected: new Set(review.currentSelected),
      isEditing: true,
    }))
  }, [updateActiveReview])

  const handleCancelEdit = useCallback(() => {
    updateActiveReview((review) => ({
      ...review,
      draftSelected: new Set(review.currentSelected),
      isEditing: false,
    }))
  }, [updateActiveReview])

  const handleToggleHeading = useCallback(
    (heading: CandidateHeading, checked: boolean) => {
      updateActiveReview((review) => {
        const nextDraft = new Set(review.draftSelected)
        if (checked) {
          nextDraft.add(heading.anchorBlockId)
        } else {
          nextDraft.delete(heading.anchorBlockId)
        }
        return {
          ...review,
          draftSelected: canonicalizeDraftSelection(nextDraft, headingsByAnchor),
        }
      })
    },
    [headingsByAnchor, updateActiveReview],
  )

  const isHistoricalView = flowState?.canResume === false

  const isNextDisabled =
    isHistoricalView ||
    nextStatus === 'freezing' ||
    nextStatus === 'completed' ||
    anySlotBlocksNext(slotReviews)

  const handleNext = useCallback(async () => {
    if (!flowState || isNextDisabled) {
      return
    }

    setNextStatus('freezing')
    setNextError(null)
    const attempt = ++nextAttemptRef.current

    if (submittedFlowRunId !== flowRunId) {
      try {
        const request = buildCandidateScopeNextRequest(
          flowState,
          buildAppliedSelectionsBySlotId(slotReviews),
        )
        await submitCandidateScopeNext(request)
        if (attempt !== nextAttemptRef.current) {
          return
        }
        setSubmittedFlowRunId(flowRunId)
      } catch (error) {
        if (attempt !== nextAttemptRef.current) {
          return
        }
        const message =
          error instanceof DocumentConsistencyQcApiError ? error.message : '候选范围提交失败'
        setNextError(message)
        setNextStatus('error')
        return
      }
    }

    let refreshedTaskState: TaskRunState | null
    try {
      refreshedTaskState = await refreshTaskRunState()
    } catch {
      if (attempt !== nextAttemptRef.current) {
        return
      }
      setNextError(TASK_STATE_REFRESH_FAILED_USER_MESSAGE)
      setNextStatus('error')
      return
    }
    if (attempt !== nextAttemptRef.current || !refreshedTaskState) {
      return
    }
    if (refreshedTaskState.resultAvailable) {
      onProceedToResult()
      return
    }
    if (refreshedTaskState.flowOutcome === 'failed') {
      setNextError(RESULT_FLOW_FAILED_USER_MESSAGE)
    } else if (refreshedTaskState.requiresUserAction) {
      await loadScope()
      if (attempt !== nextAttemptRef.current) {
        return
      }
      setSubmittedFlowRunId(null)
      setNextStatus('idle')
      return
    } else {
      setNextError(RESULT_NOT_READY_USER_MESSAGE)
    }
    setNextStatus('error')
  }, [
    flowRunId,
    flowState,
    isNextDisabled,
    loadScope,
    onProceedToResult,
    refreshTaskRunState,
    slotReviews,
    submittedFlowRunId,
  ])

  const handleApply = useCallback(() => {
    updateActiveReview((review) => {
      const canonical = canonicalizeDraftSelection(review.draftSelected, headingsByAnchor)
      return {
        ...review,
        currentSelected: new Set(canonical),
        draftSelected: new Set(canonical),
        isEditing: false,
      }
    })
  }, [headingsByAnchor, updateActiveReview])

  if (loadError) {
    return (
      <div className="flex h-full min-h-0 items-center justify-center p-6 text-sm text-destructive">
        {loadError}
      </div>
    )
  }

  if (!flowState || !activeSlot || !activeReview) {
    return (
      <div className="flex h-full min-h-0 items-center justify-center p-6 text-sm text-muted-foreground">
        正在加载功能…
      </div>
    )
  }

  const documentForShell =
    activeDocument ??
    ({
      docId: activeSlot.docId,
      fileName: activeSlot.slotId,
      displayName: activeSlot.slotId,
      blocks: [],
    } satisfies DocumentView)

  const documentStatus: SlotDocumentLoadStatus = activeDocumentStatus ?? 'loading'

  return (
    <QcSetupShellLoaded
      taskDisplayName={taskDisplayName}
      document={documentForShell}
      documentsBySlotId={slotDocumentState.documentsBySlotId}
      documentStatus={documentStatus}
      documentError={activeDocumentError}
      flowState={flowState}
      activeSlot={activeSlot}
      activeReview={activeReview}
      focusedBlockId={focusedBlockId}
      onClearFocusedBlock={clearBlockFocus}
      onSelectSlot={handleSelectSlot}
      onStartEdit={handleStartEdit}
      onApply={handleApply}
      onCancelEdit={handleCancelEdit}
      onToggleHeading={handleToggleHeading}
      onScrollToBlock={(blockId) => scrollToBlock(blockId)}
      nextStatus={nextStatus}
      nextError={nextError}
      onNext={() => void handleNext()}
      taskState={taskState}
      isNextDisabled={isNextDisabled}
    />
  )
}

export function toReaderBlockId(docId: string, anchorBlockId: string): string {
  return composeDocumentBlockId(docId, anchorBlockId)
}
