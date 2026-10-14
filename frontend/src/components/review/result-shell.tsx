import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'

import { fetchCandidateScopeDocument } from '@/api/candidate-scope-document'
import {
  DocumentConsistencyQcApiError,
  fetchDocumentConsistencyQcResult,
} from '@/api/document-consistency-qc'
import { fetchFindingReviewState, patchFindingReview } from '@/api/finding-review'
import { downloadQcReport } from '@/api/qc-report'
import { toast } from 'sonner'
import { ResultSaveContext } from '@/components/review/result-save-context'
import { ResultSaveCoordinator } from '@/lib/result-save-coordinator'
import { downloadBlob } from '@/lib/browser-download'
import {
  createSourceComment,
  createSourceEdit,
  createSourceHighlight,
  deleteSourceAnnotation,
  fetchSourceAnnotations,
  patchSourceAnnotationContent,
  patchSourceAnnotationReplacementText,
} from '@/api/source-annotation'
import { adaptExtractBundleToDocumentView, composeDocumentBlockId } from '@/adapters/extract-document'
import { DocumentReader } from '@/components/review/document-reader'
import {
  centeredDocumentCanvasHorizontalClassName,
  fullDocumentSurfaceMaxWidthClassName,
} from '@/lib/document-surface-layout'
import { FindingSourceDocumentPanel } from '@/components/review/finding-source-document-panel'
import { SourceAnnotationContext, SourceAnnotationNavigator } from '@/components/review/source-annotation-navigator'
import { ResultFindingsPanel } from '@/components/review/result-findings-panel'
import { ResultDocumentNavigator } from '@/components/review/result-document-navigator'
import { Button } from '@/components/ui/button'
import { ListTree } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  deriveQueueFindings,
  resolveDefaultQueueFindingId,
} from '@/lib/finding-queue-order'
import { applyFindingReviewPayload } from '@/lib/finding-review-presentation'
import {
  deriveResultDocumentCapabilities,
  type ResultDocumentRenderer,
} from '@/lib/result-document-capabilities'
import { resultOverviewFindingsWorkspaceGridClassName } from '@/lib/result-review-stage-layout'
import {
  resultReviewContainerBorderClassName,
  resultReviewWorkspaceDividerBorderClassName,
} from '@/lib/result-review-visual-tokens'
import type { OverviewFindingAnchor } from '@/lib/overview-source-placement'
import {
  projectScopeResultsForFunctionViewQuery,
  resolveAvailableSemanticModuleIds,
  resolveInitialResultFunctionViewQuery,
  type ResultFunctionViewQuery,
} from '@/lib/result-function-view-query'
import { buildDocumentOutlineEntries } from '@/lib/document-outline'
import { blockDomId } from '@/lib/document-anchors'
import {
  buildCommentNavigationSequence,
  buildRevisionNavigationSequence,
  resolveActiveAnnotationAfterDelete,
  resolveComposedBlockId,
  resolveNextAnnotationIndex,
} from '@/lib/source-annotation-navigation'
import {
  captureSourceAnnotationCreate,
  captureSourceAnnotationMutation,
  createSourceAnnotationMutationSession,
  mergeSourceAnnotation,
  releaseCapturedSourceAnnotationCreate,
  releaseCapturedSourceAnnotationMutation,
  removeSourceAnnotationFromMap,
  shouldReconcileCapturedSourceAnnotationCreate,
  shouldReconcileCapturedSourceAnnotationMutation,
} from '@/lib/source-annotation-mutation-reconciliation'
import {
  scrollElementIntoReaderView,
  scrollToSentenceTarget,
  scrollToSourceAnnotationElement,
  type SentenceNavigationTarget,
} from '@/lib/document-navigation'
import type { FocusedSentence } from '@/lib/sentence-navigation-focus'
import {
  deriveReviewWorkspaceSelection,
  focusEvidence as focusReviewEvidence,
  reconcileReviewWorkspaceSelection,
  selectFinding as selectReviewFinding,
} from '@/lib/result-review-selection'
import { useBlockNavigationFocus } from '@/lib/use-block-navigation-focus'
import {
  buildScopeResultsByOutlineBlockId,
  resolveInitialActiveScope,
  resolveInitialOutlineBlockId,
} from '@/lib/result-scope-state'
import {
  createInitialSlotDocumentState,
  getActiveDocument,
  getActiveDocumentLoadStatus,
  type SlotDocumentLoadStatus,
} from '@/lib/slot-document-state'
import type {
  DocumentConsistencyQcResult,
  InternalResultEvidenceRef,
  InternalResultFinding,
  InternalResultScopeResult,
} from '@/types/document-consistency-qc'
import type {
  FindingReviewPatch,
  FindingReviewStatePayload,
} from '@/types/finding-review'
import type { SourceAnnotation, SourceSentenceAnchor, SourceTextRange } from '@/types/source-annotation'
import type { DocumentView } from '@/types/document-review'
import type { DocumentOutlineEntry } from '@/lib/document-outline'

type ResultShellProps = {
  taskRunId?: string
  flowRunId: string
  taskDisplayName: string
}

type ResultLoadStatus = 'loading' | 'ready' | 'error'

type ResultView = 'findings' | 'document'

export type ResultShellLoadedProps = {
  onExportReport?: () => void
  exportingReport?: boolean
  taskDisplayName: string
  functionViewQuery: ResultFunctionViewQuery | null
  availableSemanticModuleIds: readonly string[]
  result: DocumentConsistencyQcResult
  reviewState: FindingReviewStatePayload | null
  document: DocumentView
  documentStatus: SlotDocumentLoadStatus
  documentError: string | null
  outlineEntries: DocumentOutlineEntry[]
  scopeResultsByOutlineBlockId: Map<string, InternalResultScopeResult[]>
  activeOutlineBlockId: string | null
  selectedFindingId: string | null
  selectedFinding: InternalResultFinding | null
  selectedEvidenceLocations: readonly InternalResultEvidenceRef[]
  focusedEvidenceLocationKey: string | null
  focusedEvidenceLocation: InternalResultEvidenceRef | null
  focusedBlockId: string | null
  focusedSentence: FocusedSentence | null
  sourceAnnotations: Map<string, SourceAnnotation>
  revisionItems: SourceAnnotation[]
  commentItems: SourceAnnotation[]
  activeSourceAnnotationId: string | null
  savingAnnotationId: string | null
  savingFindingId: string | null
  onNavigateRevision: (direction: 'next' | 'previous') => void
  onNavigateComment: (direction: 'next' | 'previous') => void
  onSourceAnnotationActivate: (annotationId: string) => void
  onCreateHighlight: (input: {
    anchor: SourceSentenceAnchor
    range: SourceTextRange
  }) => Promise<void>
  onDeleteHighlight: (annotationId: string) => Promise<void>
  onCreateComment: (input: {
    anchor: SourceSentenceAnchor
    range: SourceTextRange
    content: string
  }) => Promise<void>
  onUpdateComment: (input: {
    annotationId: string
    content: string
  }) => Promise<void>
  onDeleteComment: (annotationId: string) => Promise<void>
  onCreateEdit: (input: {
    anchor: SourceSentenceAnchor
    range: SourceTextRange
    replacementText: string
  }) => Promise<void>
  onUpdateEdit: (input: {
    annotationId: string
    replacementText: string
  }) => Promise<void>
  onDeleteEdit: (annotationId: string) => Promise<void>
  onSelectHeading: (
    entry: DocumentOutlineEntry,
    renderer: ResultDocumentRenderer,
  ) => void
  onSelectFinding: (findingId: string) => void
  onFocusEvidence: (
    location: InternalResultEvidenceRef,
    renderer: ResultDocumentRenderer,
  ) => void
  onPatchFindingReview: (
    findingId: string,
    patch: FindingReviewPatch,
  ) => Promise<void>
  onClearFocusedSentence: () => void
  onClearFocusedBlock: () => void
  onClearActiveSourceAnnotation: () => void
  onFunctionViewQueryChange: (query: ResultFunctionViewQuery) => void
}

function resolveResultSlotId(result: DocumentConsistencyQcResult): string {
  const slotIds = [...new Set(result.scopeResults.map((scope) => scope.slotId))]
  if (slotIds.length !== 1) {
    throw new DocumentConsistencyQcApiError('Result read model requires exactly one slot')
  }
  return slotIds[0]!
}

function resolveKindActiveIndex(
  items: SourceAnnotation[],
  activeSourceAnnotationId: string | null,
): number | null {
  if (!activeSourceAnnotationId) {
    return null
  }

  const index = items.findIndex(
    (annotation) => annotation.annotationId === activeSourceAnnotationId,
  )
  return index >= 0 ? index : null
}

type SourceAnnotationNavigatorControlsProps = {
  revisionItems: SourceAnnotation[]
  commentItems: SourceAnnotation[]
  activeSourceAnnotationId: string | null
  onNavigateRevision: (direction: 'next' | 'previous') => void
  onNavigateComment: (direction: 'next' | 'previous') => void
}

function SourceAnnotationNavigatorControls({
  revisionItems,
  commentItems,
  activeSourceAnnotationId,
  onNavigateRevision,
  onNavigateComment,
}: SourceAnnotationNavigatorControlsProps) {
  return (
    <SourceAnnotationNavigator
      revisionTotal={revisionItems.length}
      revisionActiveIndex={resolveKindActiveIndex(revisionItems, activeSourceAnnotationId)}
      commentTotal={commentItems.length}
      commentActiveIndex={resolveKindActiveIndex(commentItems, activeSourceAnnotationId)}
      onRevisionPrevious={() => onNavigateRevision('previous')}
      onRevisionNext={() => onNavigateRevision('next')}
      onCommentPrevious={() => onNavigateComment('previous')}
      onCommentNext={() => onNavigateComment('next')}
    />
  )
}

function DocumentMainPanel({
  document,
  documentStatus,
  documentError,
  slotId,
  focusedBlockId,
  focusedSentence,
  sourceAnnotations,
  activeSourceAnnotationId,
  savingAnnotationId,
  onSourceAnnotationActivate,
  onCreateHighlight,
  onDeleteHighlight,
  onCreateComment,
  onUpdateComment,
  onDeleteComment,
  onCreateEdit,
  onUpdateEdit,
  onDeleteEdit,
  onClearFocusedSentence,
  onClearFocusedBlock,
  onClearActiveSourceAnnotation,
}: {
  document: DocumentView
  documentStatus: SlotDocumentLoadStatus
  documentError: string | null
  slotId: string
  focusedBlockId: string | null
  focusedSentence: FocusedSentence | null
  sourceAnnotations: Map<string, SourceAnnotation>
  activeSourceAnnotationId: string | null
  savingAnnotationId: string | null
  onSourceAnnotationActivate: (annotationId: string) => void
  onCreateHighlight: (input: {
    anchor: SourceSentenceAnchor
    range: SourceTextRange
  }) => Promise<void>
  onDeleteHighlight: (annotationId: string) => Promise<void>
  onCreateComment: (input: {
    anchor: SourceSentenceAnchor
    range: SourceTextRange
    content: string
  }) => Promise<void>
  onUpdateComment: (input: {
    annotationId: string
    content: string
  }) => Promise<void>
  onDeleteComment: (annotationId: string) => Promise<void>
  onCreateEdit: (input: {
    anchor: SourceSentenceAnchor
    range: SourceTextRange
    replacementText: string
  }) => Promise<void>
  onUpdateEdit: (input: {
    annotationId: string
    replacementText: string
  }) => Promise<void>
  onDeleteEdit: (annotationId: string) => Promise<void>
  onClearFocusedSentence: () => void
  onClearFocusedBlock: () => void
  onClearActiveSourceAnnotation: () => void
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
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <DocumentReader
        document={document}
        slotId={slotId}
        contentPlacement="center"
        surfaceWidth="full-document"
        canvasLayout="workspace"
        focusedBlockId={focusedBlockId}
        focusedSentence={focusedSentence}
        sourceAnnotations={sourceAnnotations}
        savingAnnotationId={savingAnnotationId}
        onCreateHighlight={onCreateHighlight}
        onDeleteHighlight={onDeleteHighlight}
        onCreateComment={onCreateComment}
        onUpdateComment={onUpdateComment}
        onDeleteComment={onDeleteComment}
        onCreateEdit={onCreateEdit}
        onUpdateEdit={onUpdateEdit}
        onDeleteEdit={onDeleteEdit}
        activeSourceAnnotationId={activeSourceAnnotationId}
        onSourceAnnotationActivate={onSourceAnnotationActivate}
        onClearActiveSourceAnnotation={onClearActiveSourceAnnotation}
        onClearFocusedSentence={onClearFocusedSentence}
        onClearFocusedBlock={onClearFocusedBlock}
      />
    </div>
  )
}

export function ResultShellLoaded({
  onExportReport,
  exportingReport,
  taskDisplayName,
  functionViewQuery,
  availableSemanticModuleIds,
  result,
  reviewState,
  document,
  documentStatus,
  documentError,
  outlineEntries,
  scopeResultsByOutlineBlockId,
  activeOutlineBlockId,
  selectedFindingId,
  selectedFinding,
  selectedEvidenceLocations,
  focusedEvidenceLocationKey,
  focusedEvidenceLocation,
  focusedBlockId,
  sourceAnnotations,
  revisionItems,
  commentItems,
  activeSourceAnnotationId,
  savingAnnotationId,
  savingFindingId,
  onNavigateRevision,
  onNavigateComment,
  onSourceAnnotationActivate,
  onCreateHighlight,
  onDeleteHighlight,
  onCreateComment,
  onUpdateComment,
  onDeleteComment,
  onCreateEdit,
  onUpdateEdit,
  onDeleteEdit,
  onSelectHeading,
  onSelectFinding,
  onFocusEvidence,
  onPatchFindingReview,
  onClearFocusedSentence,
  onClearFocusedBlock,
  onClearActiveSourceAnnotation,
  onFunctionViewQueryChange,
}: ResultShellLoadedProps) {
  const [outlineOpen, setOutlineOpen] = useState(true)
  const [resultView, setResultView] = useState<ResultView>(
    () => result.findings.length === 0 ? 'document' : 'findings',
  )
  const documentRenderer: ResultDocumentRenderer =
    resultView === 'document' ? 'canonical' : 'evidence_viewports'
  const initializedResultWorkspaceIdentityRef = useRef<string | null>(null)
  const outlineTriggerRef = useRef<HTMLButtonElement | null>(null)
  const outlineRef = useRef<HTMLElement | null>(null)
  const outlineFocusRequestedRef = useRef(false)
  const documentCapabilities = deriveResultDocumentCapabilities(documentRenderer)
  const showDirectoryTrigger =
    documentCapabilities.directory && !outlineOpen
  useLayoutEffect(() => {
    if (!outlineFocusRequestedRef.current) return
    outlineFocusRequestedRef.current = false
    const target = outlineOpen
      ? outlineRef.current?.querySelector<HTMLButtonElement>('[data-result-document-navigator-collapse]')
      : outlineTriggerRef.current
    target?.focus({ preventScroll: true })
  }, [outlineOpen])
  const handleShowResultDocument = useCallback(() => {
    setResultView('document')
  }, [])
  const handleShowFindingsOverview = useCallback(() => {
    setResultView('findings')
  }, [])
  const handleSelectDocumentHeading = useCallback(
    (entry: DocumentOutlineEntry) => onSelectHeading(entry, documentRenderer),
    [documentRenderer, onSelectHeading],
  )
  const handleFocusDocumentEvidence = useCallback(
    (location: InternalResultEvidenceRef) => onFocusEvidence(location, documentRenderer),
    [documentRenderer, onFocusEvidence],
  )
  const handleSelectFinding = useCallback((findingId: string) => {
    onSelectFinding(findingId)
  }, [onSelectFinding])

  const queueFindings = useMemo(
    () => deriveQueueFindings(result.findings),
    [result.findings],
  )
  const resultWorkspaceIdentity = `${result.flowRunId}:${document.docId}`

  useLayoutEffect(() => {
    if (initializedResultWorkspaceIdentityRef.current === resultWorkspaceIdentity) {
      return
    }
    initializedResultWorkspaceIdentityRef.current = resultWorkspaceIdentity

    const initialFindingId = resolveDefaultQueueFindingId(queueFindings)
    setResultView(initialFindingId === null ? 'document' : 'findings')
    if (initialFindingId !== null) {
      onSelectFinding(initialFindingId)
    }
  }, [onSelectFinding, queueFindings, resultWorkspaceIdentity])

  const findingsWorkspaceActive = resultView === 'findings'
  const [overviewAnchorSnapshot, setOverviewAnchorSnapshot] = useState<{
    identity: string
    anchor: OverviewFindingAnchor
  } | null>(null)
  // Each selection transition needs its own settled snapshot, including a
  // rapid A → B → A navigation that would otherwise revive A's old screen Y.
  useLayoutEffect(() => {
    setOverviewAnchorSnapshot(null)
  }, [selectedFindingId, resultWorkspaceIdentity])
  const overviewFindingAnchor = overviewAnchorSnapshot?.identity === resultWorkspaceIdentity
    ? overviewAnchorSnapshot.anchor
    : null
  const overviewSelectionOwnerRef = useRef({ findingId: selectedFindingId, identity: resultWorkspaceIdentity })
  useLayoutEffect(() => {
    overviewSelectionOwnerRef.current = { findingId: selectedFindingId, identity: resultWorkspaceIdentity }
  }, [selectedFindingId, resultWorkspaceIdentity])
  const handleOverviewSelectionSettled = useCallback((anchor: OverviewFindingAnchor) => {
    const owner = overviewSelectionOwnerRef.current
    if (owner.findingId !== anchor.findingId || owner.identity !== resultWorkspaceIdentity) return
    setOverviewAnchorSnapshot({ identity: resultWorkspaceIdentity, anchor })
  }, [resultWorkspaceIdentity])
  const findingsPanelProps = {
    onExportReport,
    exportingReport,
    taskDisplayName,
    documentDisplayName: document.displayName,
    flowId: result.flowId,
    functionViewQuery,
    availableSemanticModuleIds,
    onFunctionViewQueryChange,
    activeOutlineBlockId,
    findings: result.findings,
    reviewState,
    savingFindingId,
    selectedFindingId,
    selectedFinding,
    selectedEvidenceLocations,
    focusedEvidenceLocationKey,
    focusedEvidenceLocation,
    onSelectFinding: handleSelectFinding,
    onFocusEvidence: handleFocusDocumentEvidence,
    onPatchFindingReview,
    document,
  }

  const directoryReopenControl = showDirectoryTrigger ? (
    <div
      data-result-workspace-utilities="true"
      className="flex shrink-0 items-center"
    >
      <Button
        ref={outlineTriggerRef}
        type="button"
        variant="outline"
        size="sm"
        className={cn('gap-1.5', resultReviewContainerBorderClassName)}
        aria-label="打开文档目录"
        aria-expanded={false}
        data-result-document-navigator-trigger="inline"
        onClick={() => {
          outlineFocusRequestedRef.current = true
          setOutlineOpen(true)
        }}
      >
        <ListTree aria-hidden="true" />
        <span>目录</span>
      </Button>
    </div>
  ) : null

  const toolbarActions = documentCapabilities.annotationNavigator
  || (documentCapabilities.annotationContext && !documentCapabilities.annotationNavigator)
  || queueFindings.length > 0 ? (
    <div
      className={findingsWorkspaceActive
        ? 'ml-auto mr-2 flex min-w-0 shrink-0 flex-wrap items-center justify-end gap-2 min-[840px]:mr-3 min-[840px]:gap-2.5'
        : 'ml-auto flex min-w-0 max-w-full flex-wrap items-center justify-end-safe gap-2 min-[840px]:gap-2.5'}
      role="group"
      aria-label="结果导航"
    >
      {documentCapabilities.annotationNavigator ? (
        <div data-document-annotation-toolbar="true" className="min-w-0 max-w-full overflow-x-auto overflow-y-hidden p-1 -m-1 [&_[data-source-annotation-navigator]]:justify-end-safe">
          <SourceAnnotationNavigatorControls
            revisionItems={revisionItems}
            commentItems={commentItems}
            activeSourceAnnotationId={activeSourceAnnotationId}
            onNavigateRevision={onNavigateRevision}
            onNavigateComment={onNavigateComment}
          />
        </div>
      ) : documentCapabilities.annotationContext ? (
        <SourceAnnotationContext
          revisionTotal={revisionItems.length}
          commentTotal={commentItems.length}
        />
      ) : null}
      {queueFindings.length > 0 ? (
        resultView === 'findings' ? (
          <Button
            type="button"
            variant="outline"
            size="default"
            className={cn(resultReviewContainerBorderClassName, 'h-7 rounded-[4px] px-2 text-[13px]')}
            data-result-show-full-document="true"
            onClick={handleShowResultDocument}
          >
            完整文档
          </Button>
        ) : (
          <Button
            type="button"
            variant="outline"
            size="default"
            className={cn(resultReviewContainerBorderClassName, 'h-7 rounded-[4px] px-2 text-[13px]')}
            data-result-show-findings-overview="true"
            onClick={handleShowFindingsOverview}
          >
            质控结果
          </Button>
        )
      ) : null}
    </div>
  ) : null

  return (
    <div
      className={cn(
        'grid min-h-0 w-full flex-1 grid-cols-1 overflow-hidden launcher-tech-bg',
        findingsWorkspaceActive && 'max-[840px]:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]',
        findingsWorkspaceActive && resultOverviewFindingsWorkspaceGridClassName,
      )}
    >
      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-[#F2F4F7]">
        <div
          data-result-workspace-toolbar="true"
          className={cn(
            'shrink-0 border-b bg-background py-2 min-[840px]:py-1.5',
            findingsWorkspaceActive
              ? 'flex flex-wrap items-center gap-2 px-3 min-[840px]:gap-3 min-[840px]:sm:px-4'
              : 'grid items-center',
            !findingsWorkspaceActive && (outlineOpen
              ? 'max-[840px]:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] min-[840px]:grid-cols-[22.5rem_minmax(0,1fr)]'
              : 'grid-cols-1'),
            resultReviewWorkspaceDividerBorderClassName,
          )}
        >
          {findingsWorkspaceActive ? toolbarActions : (
            <>
              {outlineOpen ? (
                <div data-result-toolbar-directory-zone="true" className="min-w-0" />
              ) : null}
              <div
                data-result-toolbar-document-zone="true"
                className={cn('box-border w-full min-w-0 max-w-full', centeredDocumentCanvasHorizontalClassName)}
              >
                <div
                  data-result-toolbar-surface="true"
                  className={cn(
                    'box-border mx-auto flex w-full min-w-0 max-w-full flex-wrap items-center gap-2 min-[840px]:gap-3',
                    fullDocumentSurfaceMaxWidthClassName,
                  )}
                >
                  {!outlineOpen ? (
                    <div data-result-toolbar-directory-zone="true" className="min-w-0 shrink-0">
                      {directoryReopenControl}
                    </div>
                  ) : null}
                  {toolbarActions}
                </div>
              </div>
            </>
          )}
        </div>

        <div
          data-result-main-content="true"
          className="flex min-h-0 min-w-0 flex-1 flex-col"
        >
          <div
            data-result-document-workspace="true"
            className={cn(
              'flex min-h-0 min-w-0 flex-1',
              documentCapabilities.directory && outlineOpen && 'max-[840px]:grid max-[840px]:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] max-[840px]:grid-rows-[minmax(0,1fr)]',
            )}
          >
            {documentCapabilities.directory && outlineOpen ? (
              <aside
                ref={outlineRef}
                data-result-outline-inline="true"
                aria-label="文档目录"
                className={cn(
                  'flex h-full min-h-0 min-w-0 min-[840px]:w-[22.5rem] min-[840px]:shrink-0 flex-col overflow-hidden border-r bg-background',
                  resultReviewWorkspaceDividerBorderClassName,
                )}
              >
                <ResultDocumentNavigator
                  outlineEntries={outlineEntries}
                  scopeResultsByOutlineBlockId={scopeResultsByOutlineBlockId}
                  reviewState={reviewState}
                  activeOutlineBlockId={activeOutlineBlockId}
                  onSelectHeading={handleSelectDocumentHeading}
                  onCollapse={() => {
                    outlineFocusRequestedRef.current = true
                    setOutlineOpen(false)
                  }}
                />
              </aside>
            ) : null}

            <div
              data-result-document-column="true"
              className="flex min-h-0 min-w-0 flex-1 flex-col"
            >

              <div
                data-result-document-pane="true"
                className="flex min-h-0 min-w-0 flex-1 flex-col"
              >
                {documentRenderer === 'canonical' ? (
                  <DocumentMainPanel
                    document={document}
                    documentStatus={documentStatus}
                    documentError={documentError}
                    slotId={result.scopeResults[0]?.slotId ?? 'source'}
                    focusedBlockId={focusedBlockId}
                    focusedSentence={null}
                    sourceAnnotations={sourceAnnotations}
                    activeSourceAnnotationId={activeSourceAnnotationId}
                    savingAnnotationId={savingAnnotationId}
                    onSourceAnnotationActivate={onSourceAnnotationActivate}
                    onCreateHighlight={onCreateHighlight}
                    onDeleteHighlight={onDeleteHighlight}
                    onCreateComment={onCreateComment}
                    onUpdateComment={onUpdateComment}
                    onDeleteComment={onDeleteComment}
                    onCreateEdit={onCreateEdit}
                    onUpdateEdit={onUpdateEdit}
                    onDeleteEdit={onDeleteEdit}
                    onClearFocusedSentence={onClearFocusedSentence}
                    onClearFocusedBlock={onClearFocusedBlock}
                    onClearActiveSourceAnnotation={onClearActiveSourceAnnotation}
                  />
                ) : (
                  <FindingSourceDocumentPanel
                    findingId={selectedFindingId}
                    slotId={result.scopeResults[0]?.slotId ?? 'source'}
                    document={document}
                    documentStatus={documentStatus}
                    documentError={documentError}
                    evidenceLocations={selectedEvidenceLocations}
                    overviewFindingAnchor={overviewFindingAnchor}
                    overviewPresentationKey={resultWorkspaceIdentity}
                    overviewPairActive={findingsWorkspaceActive}
                    sourceAnnotations={sourceAnnotations}
                    activeSourceAnnotationId={activeSourceAnnotationId}
                    savingAnnotationId={savingAnnotationId}
                    onSourceAnnotationActivate={onSourceAnnotationActivate}
                    onClearActiveSourceAnnotation={onClearActiveSourceAnnotation}
                    onClearFocusedSentence={onClearFocusedSentence}
                    onClearFocusedBlock={onClearFocusedBlock}
                    onCreateHighlight={onCreateHighlight}
                    onDeleteHighlight={onDeleteHighlight}
                    onCreateComment={onCreateComment}
                    onUpdateComment={onUpdateComment}
                    onDeleteComment={onDeleteComment}
                    onCreateEdit={onCreateEdit}
                    onUpdateEdit={onUpdateEdit}
                    onDeleteEdit={onDeleteEdit}
                  />
                )}
              </div>
            </div>

          </div>

        </div>
      </main>

      {findingsWorkspaceActive ? (
        <aside
          data-result-findings-panel="true"
          data-result-finding-reading-column="true"
          data-result-findings-panel-open="true"
          className={cn(
            'flex h-full min-h-0 min-w-0 flex-col overflow-hidden border-l bg-background',
            resultReviewWorkspaceDividerBorderClassName,
          )}
        >
          <ResultFindingsPanel
            {...findingsPanelProps}
            selectionNavigationKey={resultWorkspaceIdentity}
            selectionNavigationEnabled={findingsWorkspaceActive}
            onSelectionSettled={handleOverviewSelectionSettled}
          />
        </aside>
      ) : null}
    </div>
  )
}

export function ResultShell({ flowRunId, taskDisplayName, taskRunId }: ResultShellProps) {
  const saveCoordinator = useMemo(() => ({
    flowRunId,
    coordinator: new ResultSaveCoordinator(),
  }), [flowRunId]).coordinator
  const exportScope = useMemo(() => ({ flowRunId, taskRunId }), [flowRunId, taskRunId])
  const activeExportScopeRef = useRef(exportScope)
  const exportingRef = useRef<typeof exportScope | null>(null)
  const [exportingScope, setExportingScope] = useState<typeof exportScope | null>(null)
  const exportingReport = exportingScope === exportScope
  useLayoutEffect(() => {
    activeExportScopeRef.current = exportScope
  }, [exportScope])

  const handleExportReport = useCallback(async () => {
    if (!taskRunId || exportingRef.current === exportScope) return
    exportingRef.current = exportScope
    setExportingScope(exportScope)
    let saved = false
    try {
      await saveCoordinator.flush()
      saved = true
      if (activeExportScopeRef.current !== exportScope) return
      const download = await downloadQcReport(taskRunId)
      if (activeExportScopeRef.current !== exportScope) return
      downloadBlob(download.blob, download.filename)
    } catch (error) {
      if (activeExportScopeRef.current === exportScope) {
        toast.error(!saved ? '保存失败，暂无法导出报告。'
          : error instanceof DocumentConsistencyQcApiError ? error.message
            : '报告生成失败，请稍后重试。')
      }
    } finally {
      if (activeExportScopeRef.current === exportScope) {
        exportingRef.current = null
        setExportingScope(null)
      }
    }
  }, [exportScope, saveCoordinator, taskRunId])
  const activeFlowRunIdRef = useRef(flowRunId)
  const annotationMutationEpochRef = useRef(0)
  const annotationMutationSessionRef = useRef(createSourceAnnotationMutationSession())
  const latestAnnotationMutationRequestRef = useRef(new Map<string, number>())
  const latestAnnotationCreateBusyRequestRef = useRef(new Map<string, number>())
  const [result, setResult] = useState<DocumentConsistencyQcResult | null>(null)
  const [reviewState, setReviewState] = useState<FindingReviewStatePayload | null>(null)
  const [resultLoadStatus, setResultLoadStatus] = useState<ResultLoadStatus>('loading')
  const [resultError, setResultError] = useState<string | null>(null)
  const [slotDocumentState, setSlotDocumentState] = useState(createInitialSlotDocumentState)
  const [activeSlotId, setActiveSlotId] = useState<string | null>(null)
  const [activeOutlineBlockId, setActiveOutlineBlockId] = useState<string | null>(null)
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null)
  const [focusedEvidenceLocationKey, setFocusedEvidenceLocationKey] = useState<string | null>(null)
  const { focusedBlockId, focusBlock, clearBlockFocus } = useBlockNavigationFocus()
  const [sourceAnnotations, setSourceAnnotations] = useState<Map<string, SourceAnnotation>>(
    new Map(),
  )
  const [activeSourceAnnotationId, setActiveSourceAnnotationId] = useState<string | null>(null)
  const [savingAnnotationId, setSavingAnnotationId] = useState<string | null>(null)
  const [savingFindingId, setSavingFindingId] = useState<string | null>(null)
  const [initializedSelection, setInitializedSelection] = useState(false)
  const [functionViewQuery, setFunctionViewQuery] = useState<ResultFunctionViewQuery | null>(
    null,
  )

  const availableSemanticModuleIds = useMemo(
    () => (result ? resolveAvailableSemanticModuleIds(result.scopeResults) : []),
    [result],
  )

  const {
    selectedFinding,
    selectedEvidenceLocations,
    focusedEvidenceLocation,
    focusedSentence,
  } = useMemo(
    () =>
      deriveReviewWorkspaceSelection(result?.findings ?? [], {
        selectedFindingId,
        focusedEvidenceLocationKey,
      }),
    [focusedEvidenceLocationKey, result, selectedFindingId],
  )

  const clearFocusedSentence = useCallback(() => {
    setFocusedEvidenceLocationKey(null)
  }, [])

  const clearActiveSourceAnnotation = useCallback(() => {
    setActiveSourceAnnotationId(null)
  }, [])

  const scrollToBlockPreservingEvidenceFocus = useCallback(
    (blockId: string) => {
      setActiveSourceAnnotationId(null)
      const target = window.document.getElementById(blockDomId(blockId))
      if (!target) {
        return
      }
      scrollElementIntoReaderView(target)
      focusBlock(blockId)
    },
    [focusBlock],
  )

  const scrollToBlock = useCallback(
    (blockId: string) => {
      setFocusedEvidenceLocationKey(null)
      scrollToBlockPreservingEvidenceFocus(blockId)
    },
    [scrollToBlockPreservingEvidenceFocus],
  )

  useEffect(() => {
    activeFlowRunIdRef.current = flowRunId
    annotationMutationEpochRef.current += 1
    annotationMutationSessionRef.current = createSourceAnnotationMutationSession()
    latestAnnotationMutationRequestRef.current = new Map()
    latestAnnotationCreateBusyRequestRef.current = new Map()
    setInitializedSelection(false)
    setSelectedFindingId(null)
    setFocusedEvidenceLocationKey(null)
    setSavingFindingId(null)
    setSavingAnnotationId(null)
    setActiveSourceAnnotationId(null)
  }, [flowRunId])

  useEffect(() => {
    let cancelled = false
    setResultLoadStatus('loading')
    setResultError(null)
    setFunctionViewQuery(null)

    void Promise.all([
      fetchDocumentConsistencyQcResult(flowRunId),
      fetchFindingReviewState(flowRunId),
      fetchSourceAnnotations(flowRunId),
    ])
      .then(([resultPayload, reviewPayload, annotationPayload]) => {
        if (cancelled) {
          return
        }
        setResult(resultPayload)
        setReviewState(reviewPayload)
        setSourceAnnotations(annotationPayload.annotationsById)
        setActiveSlotId(resolveResultSlotId(resultPayload))
        setFunctionViewQuery(
          resolveInitialResultFunctionViewQuery(resultPayload.scopeResults),
        )
        setResultLoadStatus('ready')
      })
      .catch((error) => {
        if (cancelled) {
          return
        }
        const message =
          error instanceof DocumentConsistencyQcApiError ? error.message : '结果加载失败'
        setResultError(message)
        setResultLoadStatus('error')
      })

    return () => {
      cancelled = true
    }
  }, [flowRunId])

  useEffect(() => {
    if (!result || !activeSlotId) {
      return
    }

    const cachedDocument = slotDocumentState.documentsBySlotId[activeSlotId]
    if (cachedDocument) {
      return
    }

    const currentStatus = slotDocumentState.documentLoadStatusBySlotId[activeSlotId]
    if (currentStatus === 'error') {
      return
    }

    let cancelled = false

    setSlotDocumentState((previous) => ({
      ...previous,
      documentLoadStatusBySlotId: {
        ...previous.documentLoadStatusBySlotId,
        [activeSlotId]: 'loading',
      },
      documentErrorBySlotId: {
        ...previous.documentErrorBySlotId,
        [activeSlotId]: '',
      },
    }))

    void fetchCandidateScopeDocument(flowRunId, activeSlotId)
      .then((bundle) => {
        if (cancelled) {
          return
        }
        const document = adaptExtractBundleToDocumentView(bundle)
        const expectedDocId = result.scopeResults.find((scope) => scope.slotId === activeSlotId)?.docId
        if (expectedDocId && document.docId !== expectedDocId) {
          throw new DocumentConsistencyQcApiError(
            `document doc_id ${document.docId} does not match result doc_id ${expectedDocId}`,
          )
        }
        setSlotDocumentState((previous) => ({
          ...previous,
          documentsBySlotId: {
            ...previous.documentsBySlotId,
            [activeSlotId]: document,
          },
          documentLoadStatusBySlotId: {
            ...previous.documentLoadStatusBySlotId,
            [activeSlotId]: 'ready',
          },
        }))
      })
      .catch((error) => {
        if (cancelled) {
          return
        }
        const message =
          error instanceof DocumentConsistencyQcApiError ? error.message : '文档加载失败'
        setSlotDocumentState((previous) => ({
          ...previous,
          documentLoadStatusBySlotId: {
            ...previous.documentLoadStatusBySlotId,
            [activeSlotId]: 'error',
          },
          documentErrorBySlotId: {
            ...previous.documentErrorBySlotId,
            [activeSlotId]: message,
          },
        }))
      })

    return () => {
      cancelled = true
    }
  }, [activeSlotId, flowRunId, result, slotDocumentState.documentsBySlotId])

  const activeDocument = getActiveDocument(slotDocumentState, activeSlotId)
  const activeDocumentStatus = getActiveDocumentLoadStatus(slotDocumentState, activeSlotId) ?? 'loading'
  const activeDocumentError = activeSlotId
    ? slotDocumentState.documentErrorBySlotId[activeSlotId] ?? null
    : null

  const outlineEntries = useMemo(
    () => (activeDocument ? buildDocumentOutlineEntries(activeDocument) : []),
    [activeDocument],
  )

  const projectedScopeResults = useMemo(
    () =>
      result
        ? projectScopeResultsForFunctionViewQuery(result.scopeResults, functionViewQuery)
        : [],
    [result, functionViewQuery],
  )

  const scopeResultsByOutlineBlockId = useMemo(
    () => buildScopeResultsByOutlineBlockId(projectedScopeResults),
    [projectedScopeResults],
  )

  useEffect(() => {
    if (!result || !activeDocument || initializedSelection) {
      return
    }
    if (activeDocumentStatus !== 'ready') {
      return
    }

    const initialScope = resolveInitialActiveScope(projectedScopeResults)
    const initialOutlineBlockId = resolveInitialOutlineBlockId(outlineEntries, initialScope)
    setActiveOutlineBlockId(initialOutlineBlockId)
    if (initialOutlineBlockId) {
      scrollToBlock(initialOutlineBlockId)
    }
    setInitializedSelection(true)
  }, [
    activeDocument,
    activeDocumentStatus,
    initializedSelection,
    outlineEntries,
    projectedScopeResults,
    scrollToBlock,
  ])

  const handleFunctionViewQueryChange = useCallback((query: ResultFunctionViewQuery) => {
    setFunctionViewQuery(query)
  }, [])

  const handleSelectFinding = useCallback(
    (findingId: string) => {
      const next = selectReviewFinding(
        { selectedFindingId, focusedEvidenceLocationKey },
        result?.findings ?? [],
        findingId,
      )
      setSelectedFindingId(next.selectedFindingId)
      setFocusedEvidenceLocationKey(next.focusedEvidenceLocationKey)
    },
    [focusedEvidenceLocationKey, result, selectedFindingId],
  )

  useEffect(() => {
    if (!result || selectedFindingId === null) {
      return
    }

    const reconciled = reconcileReviewWorkspaceSelection(
      { selectedFindingId, focusedEvidenceLocationKey },
      result.findings,
    )
    if (
      reconciled.selectedFindingId !== selectedFindingId ||
      reconciled.focusedEvidenceLocationKey !== focusedEvidenceLocationKey
    ) {
      setSelectedFindingId(reconciled.selectedFindingId)
      setFocusedEvidenceLocationKey(reconciled.focusedEvidenceLocationKey)
    }
  }, [focusedEvidenceLocationKey, result, selectedFindingId])

  const handlePatchFindingReview = useCallback(
    async (findingId: string, patch: FindingReviewPatch) => {
      const requestedFlowRunId = flowRunId
      setSavingFindingId(findingId)
      try {
        const payload = await saveCoordinator.track(`review:${findingId}:${Object.keys(patch).sort().join(',')}`, patchFindingReview(requestedFlowRunId, findingId, patch))
        if (activeFlowRunIdRef.current === requestedFlowRunId) {
          setReviewState((current) => applyFindingReviewPayload(current, payload))
        }
      } finally {
        if (activeFlowRunIdRef.current === requestedFlowRunId) {
          setSavingFindingId((current) => current === findingId ? null : current)
        }
      }
    },
    [flowRunId, saveCoordinator],
  )

  const handleFocusEvidence = useCallback(
    (
      location: InternalResultEvidenceRef,
      renderer: ResultDocumentRenderer,
    ) => {
      const next = focusReviewEvidence(
        { selectedFindingId, focusedEvidenceLocationKey },
        selectedEvidenceLocations,
        location,
      )
      setFocusedEvidenceLocationKey(next.focusedEvidenceLocationKey)
      if (next.focusedEvidenceLocationKey === null) {
        return
      }

      setActiveSourceAnnotationId(null)
      if (renderer === 'evidence_viewports') {
        return
      }
      const navigationResult = scrollToSentenceTarget(
        {
          docId: location.docId,
          blockId: composeDocumentBlockId(location.docId, location.blockId),
          sentenceId: location.sentenceId,
        },
        { scrollToBlock: scrollToBlockPreservingEvidenceFocus },
      )
      if (navigationResult === 'sentence') {
        clearBlockFocus()
      }
    },
    [
      clearBlockFocus,
      focusedEvidenceLocationKey,
      scrollToBlockPreservingEvidenceFocus,
      selectedEvidenceLocations,
      selectedFindingId,
    ],
  )

  const handleSelectHeading = useCallback(
    (entry: DocumentOutlineEntry, _renderer: ResultDocumentRenderer) => {
      setActiveOutlineBlockId(entry.blockId)
      scrollToBlockPreservingEvidenceFocus(entry.blockId)
    },
    [scrollToBlockPreservingEvidenceFocus],
  )

  useEffect(() => {
    setFocusedEvidenceLocationKey(null)
    setActiveSourceAnnotationId(null)
  }, [activeDocument?.docId])

  const revisionItems = useMemo(
    () =>
      activeDocument
        ? buildRevisionNavigationSequence(activeDocument, sourceAnnotations.values())
        : [],
    [activeDocument, sourceAnnotations],
  )

  const commentItems = useMemo(
    () =>
      activeDocument
        ? buildCommentNavigationSequence(activeDocument, sourceAnnotations.values())
        : [],
    [activeDocument, sourceAnnotations],
  )

  useEffect(() => {
    if (!activeSourceAnnotationId) {
      return
    }
    const annotation = sourceAnnotations.get(activeSourceAnnotationId)
    if (!annotation || annotation.anchor.docId !== activeDocument?.docId) {
      setActiveSourceAnnotationId(null)
    }
  }, [activeDocument?.docId, activeSourceAnnotationId, sourceAnnotations])

  const navigateToSourceAnnotation = useCallback(
    (annotation: SourceAnnotation) => {
      if (!activeDocument) {
        return
      }

      clearBlockFocus()
      setActiveSourceAnnotationId(annotation.annotationId)
      const target: SentenceNavigationTarget = {
        docId: annotation.anchor.docId,
        blockId: resolveComposedBlockId(activeDocument, annotation.anchor.blockId),
        sentenceId: annotation.anchor.sentenceId,
      }
      scrollToSourceAnnotationElement(annotation.annotationId, target, {
        scrollToBlock: scrollToBlockPreservingEvidenceFocus,
      })
    },
    [activeDocument, clearBlockFocus, scrollToBlockPreservingEvidenceFocus],
  )

  const handleNavigateRevision = useCallback(
    (direction: 'next' | 'previous') => {
      const nextIndex = resolveNextAnnotationIndex(
        revisionItems,
        activeSourceAnnotationId,
        direction,
      )
      if (nextIndex < 0) {
        return
      }
      const annotation = revisionItems[nextIndex]
      if (!annotation) {
        return
      }
      navigateToSourceAnnotation(annotation)
    },
    [activeSourceAnnotationId, navigateToSourceAnnotation, revisionItems],
  )

  const handleNavigateComment = useCallback(
    (direction: 'next' | 'previous') => {
      const nextIndex = resolveNextAnnotationIndex(
        commentItems,
        activeSourceAnnotationId,
        direction,
      )
      if (nextIndex < 0) {
        return
      }
      const annotation = commentItems[nextIndex]
      if (!annotation) {
        return
      }
      navigateToSourceAnnotation(annotation)
    },
    [activeSourceAnnotationId, commentItems, navigateToSourceAnnotation],
  )

  const handleSourceAnnotationActivate = useCallback((annotationId: string) => {
    setActiveSourceAnnotationId(annotationId)
  }, [])

  const handleCreateHighlight = useCallback(
    async (input: { anchor: SourceSentenceAnchor; range: SourceTextRange }) => {
      const savingKey = 'create:highlight'
      const captured = captureSourceAnnotationCreate({
        session: annotationMutationSessionRef.current,
        latestBusyRequestByKey: latestAnnotationCreateBusyRequestRef.current,
        operationKey: savingKey,
        epoch: annotationMutationEpochRef.current,
        flowRunId,
      })
      setSavingAnnotationId(savingKey)
      try {
        const created = await saveCoordinator.track('annotation:create:highlight', createSourceHighlight(captured.flowRunId, input))
        if (!shouldReconcileCapturedSourceAnnotationCreate(
          activeFlowRunIdRef.current,
          annotationMutationEpochRef.current,
          captured,
        )) {
          return
        }
        setSourceAnnotations((current) => mergeSourceAnnotation(current, created))
      } finally {
        const ownsBusyPresentation = releaseCapturedSourceAnnotationCreate(captured)
        if (
          ownsBusyPresentation &&
          annotationMutationEpochRef.current === captured.epoch
        ) {
          setSavingAnnotationId((current) => (current === savingKey ? null : current))
        }
      }
    },
    [flowRunId, saveCoordinator],
  )

  const handleDeleteHighlight = useCallback(
    async (annotationId: string) => {
      const captured = captureSourceAnnotationMutation({
        session: annotationMutationSessionRef.current,
        latestByAnnotationId: latestAnnotationMutationRequestRef.current,
        epoch: annotationMutationEpochRef.current,
        flowRunId,
        annotationId,
      })
      if (!captured) {
        return
      }
      setSavingAnnotationId(annotationId)
      try {
        const nextActive =
          activeSourceAnnotationId === annotationId ? null : activeSourceAnnotationId
        await saveCoordinator.track(`annotation:${annotationId}`, deleteSourceAnnotation(captured.flowRunId, annotationId))
        if (
          !shouldReconcileCapturedSourceAnnotationMutation(
            activeFlowRunIdRef.current,
            annotationMutationEpochRef.current,
            captured,
            annotationId,
          )
        ) {
          return
        }
        setSourceAnnotations((current) =>
          removeSourceAnnotationFromMap(current, annotationId),
        )
        setActiveSourceAnnotationId(nextActive)
      } finally {
        const stillLatest = releaseCapturedSourceAnnotationMutation(captured, annotationId)
        if (stillLatest && annotationMutationEpochRef.current === captured.epoch) {
          setSavingAnnotationId((current) => (current === annotationId ? null : current))
        }
      }
    },
    [activeSourceAnnotationId, flowRunId, saveCoordinator],
  )

  const handleCreateComment = useCallback(
    async (input: {
      anchor: SourceSentenceAnchor
      range: SourceTextRange
      content: string
    }) => {
      const savingKey = 'create:comment'
      const captured = captureSourceAnnotationCreate({
        session: annotationMutationSessionRef.current,
        latestBusyRequestByKey: latestAnnotationCreateBusyRequestRef.current,
        operationKey: savingKey,
        epoch: annotationMutationEpochRef.current,
        flowRunId,
      })
      setSavingAnnotationId(savingKey)
      try {
        const created = await saveCoordinator.track('annotation:create:comment', createSourceComment(captured.flowRunId, input))
        if (!shouldReconcileCapturedSourceAnnotationCreate(
          activeFlowRunIdRef.current,
          annotationMutationEpochRef.current,
          captured,
        )) {
          return
        }
        setSourceAnnotations((current) => mergeSourceAnnotation(current, created))
        setActiveSourceAnnotationId(created.annotationId)
      } finally {
        const ownsBusyPresentation = releaseCapturedSourceAnnotationCreate(captured)
        if (
          ownsBusyPresentation &&
          annotationMutationEpochRef.current === captured.epoch
        ) {
          setSavingAnnotationId((current) => (current === savingKey ? null : current))
        }
      }
    },
    [flowRunId, saveCoordinator],
  )

  const handleUpdateComment = useCallback(
    async (input: { annotationId: string; content: string }) => {
      const captured = captureSourceAnnotationMutation({
        session: annotationMutationSessionRef.current,
        latestByAnnotationId: latestAnnotationMutationRequestRef.current,
        epoch: annotationMutationEpochRef.current,
        flowRunId,
        annotationId: input.annotationId,
      })
      if (!captured) {
        return
      }
      setSavingAnnotationId(input.annotationId)
      try {
        const updated = await saveCoordinator.track(`annotation:${input.annotationId}`, patchSourceAnnotationContent(captured.flowRunId, input))
        if (
          !shouldReconcileCapturedSourceAnnotationMutation(
            activeFlowRunIdRef.current,
            annotationMutationEpochRef.current,
            captured,
            input.annotationId,
          )
        ) {
          return
        }
        setSourceAnnotations((current) => mergeSourceAnnotation(current, updated))
      } finally {
        const stillLatest = releaseCapturedSourceAnnotationMutation(
          captured,
          input.annotationId,
        )
        if (stillLatest && annotationMutationEpochRef.current === captured.epoch) {
          setSavingAnnotationId((current) =>
            current === input.annotationId ? null : current,
          )
        }
      }
    },
    [flowRunId, saveCoordinator],
  )

  const handleDeleteComment = useCallback(
    async (annotationId: string) => {
      const captured = captureSourceAnnotationMutation({
        session: annotationMutationSessionRef.current,
        latestByAnnotationId: latestAnnotationMutationRequestRef.current,
        epoch: annotationMutationEpochRef.current,
        flowRunId,
        annotationId,
      })
      if (!captured) {
        return
      }
      const savingKey = `delete:${annotationId}`
      setSavingAnnotationId(savingKey)
      try {
        const nextActive = resolveActiveAnnotationAfterDelete(commentItems, annotationId)
        await saveCoordinator.track(`annotation:${annotationId}`, deleteSourceAnnotation(captured.flowRunId, annotationId))
        if (
          !shouldReconcileCapturedSourceAnnotationMutation(
            activeFlowRunIdRef.current,
            annotationMutationEpochRef.current,
            captured,
            annotationId,
          )
        ) {
          return
        }
        setSourceAnnotations((current) =>
          removeSourceAnnotationFromMap(current, annotationId),
        )
        setActiveSourceAnnotationId(nextActive)
      } finally {
        const stillLatest = releaseCapturedSourceAnnotationMutation(captured, annotationId)
        if (stillLatest && annotationMutationEpochRef.current === captured.epoch) {
          setSavingAnnotationId((current) => (current === savingKey ? null : current))
        }
      }
    },
    [commentItems, flowRunId, saveCoordinator],
  )

  const handleCreateEdit = useCallback(
    async (input: {
      anchor: SourceSentenceAnchor
      range: SourceTextRange
      replacementText: string
    }) => {
      const savingKey = 'create:edit'
      const captured = captureSourceAnnotationCreate({
        session: annotationMutationSessionRef.current,
        latestBusyRequestByKey: latestAnnotationCreateBusyRequestRef.current,
        operationKey: savingKey,
        epoch: annotationMutationEpochRef.current,
        flowRunId,
      })
      setSavingAnnotationId(savingKey)
      try {
        const created = await saveCoordinator.track('annotation:create:edit', createSourceEdit(captured.flowRunId, input))
        if (!shouldReconcileCapturedSourceAnnotationCreate(
          activeFlowRunIdRef.current,
          annotationMutationEpochRef.current,
          captured,
        )) {
          return
        }
        setSourceAnnotations((current) => mergeSourceAnnotation(current, created))
        setActiveSourceAnnotationId(created.annotationId)
      } finally {
        const ownsBusyPresentation = releaseCapturedSourceAnnotationCreate(captured)
        if (
          ownsBusyPresentation &&
          annotationMutationEpochRef.current === captured.epoch
        ) {
          setSavingAnnotationId((current) => (current === savingKey ? null : current))
        }
      }
    },
    [flowRunId, saveCoordinator],
  )

  const handleUpdateEdit = useCallback(
    async (input: { annotationId: string; replacementText: string }) => {
      const captured = captureSourceAnnotationMutation({
        session: annotationMutationSessionRef.current,
        latestByAnnotationId: latestAnnotationMutationRequestRef.current,
        epoch: annotationMutationEpochRef.current,
        flowRunId,
        annotationId: input.annotationId,
      })
      if (!captured) {
        return
      }
      setSavingAnnotationId(input.annotationId)
      try {
        const updated = await saveCoordinator.track(`annotation:${input.annotationId}`, patchSourceAnnotationReplacementText(captured.flowRunId, input))
        if (
          !shouldReconcileCapturedSourceAnnotationMutation(
            activeFlowRunIdRef.current,
            annotationMutationEpochRef.current,
            captured,
            input.annotationId,
          )
        ) {
          return
        }
        setSourceAnnotations((current) => mergeSourceAnnotation(current, updated))
      } finally {
        const stillLatest = releaseCapturedSourceAnnotationMutation(
          captured,
          input.annotationId,
        )
        if (stillLatest && annotationMutationEpochRef.current === captured.epoch) {
          setSavingAnnotationId((current) =>
            current === input.annotationId ? null : current,
          )
        }
      }
    },
    [flowRunId, saveCoordinator],
  )

  const handleDeleteEdit = useCallback(
    async (annotationId: string) => {
      const captured = captureSourceAnnotationMutation({
        session: annotationMutationSessionRef.current,
        latestByAnnotationId: latestAnnotationMutationRequestRef.current,
        epoch: annotationMutationEpochRef.current,
        flowRunId,
        annotationId,
      })
      if (!captured) {
        return
      }
      const savingKey = `delete:${annotationId}`
      setSavingAnnotationId(savingKey)
      try {
        const nextActive = resolveActiveAnnotationAfterDelete(revisionItems, annotationId)
        await saveCoordinator.track(`annotation:${annotationId}`, deleteSourceAnnotation(captured.flowRunId, annotationId))
        if (
          !shouldReconcileCapturedSourceAnnotationMutation(
            activeFlowRunIdRef.current,
            annotationMutationEpochRef.current,
            captured,
            annotationId,
          )
        ) {
          return
        }
        setSourceAnnotations((current) =>
          removeSourceAnnotationFromMap(current, annotationId),
        )
        setActiveSourceAnnotationId(nextActive)
      } finally {
        const stillLatest = releaseCapturedSourceAnnotationMutation(captured, annotationId)
        if (stillLatest && annotationMutationEpochRef.current === captured.epoch) {
          setSavingAnnotationId((current) => (current === savingKey ? null : current))
        }
      }
    },
    [flowRunId, revisionItems, saveCoordinator],
  )

  if (resultLoadStatus === 'error') {
    return (
      <div className="flex h-full min-h-0 items-center justify-center p-6 text-sm text-destructive">
        {resultError ?? '结果加载失败'}
      </div>
    )
  }

  if (resultLoadStatus === 'loading' || !result || !activeSlotId) {
    return (
      <div className="flex h-full min-h-0 items-center justify-center p-6 text-sm text-muted-foreground">
        正在加载核查结果…
      </div>
    )
  }

  const documentForShell =
    activeDocument ??
    ({
      docId: result.scopeResults[0]?.docId ?? 'unknown',
      fileName: activeSlotId,
      displayName: activeSlotId,
      blocks: [],
    } satisfies DocumentView)

  return (
    <ResultSaveContext.Provider value={saveCoordinator}>
      <ResultShellLoaded
        onExportReport={taskRunId ? handleExportReport : undefined}
        exportingReport={exportingReport}
        taskDisplayName={taskDisplayName}
        functionViewQuery={functionViewQuery}
        availableSemanticModuleIds={availableSemanticModuleIds}
        result={result}
        reviewState={reviewState}
        document={documentForShell}
        documentStatus={activeDocumentStatus}
        documentError={activeDocumentError}
        outlineEntries={outlineEntries}
        scopeResultsByOutlineBlockId={scopeResultsByOutlineBlockId}
        activeOutlineBlockId={activeOutlineBlockId}
        selectedFindingId={selectedFindingId}
        selectedFinding={selectedFinding}
        selectedEvidenceLocations={selectedEvidenceLocations}
        focusedEvidenceLocationKey={focusedEvidenceLocationKey}
        focusedEvidenceLocation={focusedEvidenceLocation}
        focusedBlockId={focusedBlockId}
        focusedSentence={focusedSentence}
        sourceAnnotations={sourceAnnotations}
        revisionItems={revisionItems}
        commentItems={commentItems}
        activeSourceAnnotationId={activeSourceAnnotationId}
        savingAnnotationId={savingAnnotationId}
        savingFindingId={savingFindingId}
        onNavigateRevision={handleNavigateRevision}
        onNavigateComment={handleNavigateComment}
        onSourceAnnotationActivate={handleSourceAnnotationActivate}
        onCreateHighlight={handleCreateHighlight}
        onDeleteHighlight={handleDeleteHighlight}
        onCreateComment={handleCreateComment}
        onUpdateComment={handleUpdateComment}
        onDeleteComment={handleDeleteComment}
        onCreateEdit={handleCreateEdit}
        onUpdateEdit={handleUpdateEdit}
        onDeleteEdit={handleDeleteEdit}
        onSelectHeading={handleSelectHeading}
        onSelectFinding={handleSelectFinding}
        onFocusEvidence={handleFocusEvidence}
        onPatchFindingReview={handlePatchFindingReview}
        onClearFocusedSentence={clearFocusedSentence}
        onClearFocusedBlock={clearBlockFocus}
        onClearActiveSourceAnnotation={clearActiveSourceAnnotation}
        onFunctionViewQueryChange={handleFunctionViewQueryChange}
      />
    </ResultSaveContext.Provider>
  )
}
