import { Crosshair } from 'lucide-react'
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type RefObject } from 'react'

import { Button } from '@/components/ui/button'

import {
  SourceDocumentInteraction,
  type SourceDocumentInteractionHandlers,
  type SourceDocumentInteractionProps,
} from '@/components/review/source-document-interaction'
import { SourceSectionReader } from '@/components/review/source-section-reader'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  findSourceSentenceWithinRoot,
  type SourceEvidenceViewportDescriptor,
} from '@/lib/source-evidence-viewport'
import {
  measureViewportReadableLayout,
  scrollViewportToReadableEvidenceAnchor,
  sourceEvidenceViewportChromeAttributes,
  sourceEvidenceViewportReadableSizingAttributes,
  sourceEvidenceViewportScrollAreaClassName,
  sourceEvidenceViewportScrollAttributes,
} from '@/lib/source-evidence-viewport-presentation'
import { shouldShowReturnToEvidenceAnchor } from '@/lib/source-evidence-viewport-evidence-visibility'
import type { SourceAnnotation } from '@/types/source-annotation'
import type { DocumentView } from '@/types/document-review'
import { resolveSourceSentenceAnchor } from '@/lib/source-sentence-anchor'
import {
  resultReviewContainerBorderClassName,
  resultReviewInternalSeparatorBorderClassName,
} from '@/lib/result-review-visual-tokens'
import { cn } from '@/lib/utils'

const emptySourceAnnotations = new Map<string, SourceAnnotation>()

type SourceEvidenceViewportPresentationProps = {
  sourceAnnotations?: Map<string, SourceAnnotation>
  activeSourceAnnotationId?: string | null
  interactionHandlers?: SourceDocumentInteractionHandlers
}

export type SourceEvidenceViewportProps = SourceEvidenceViewportPresentationProps & {
  document: DocumentView
  descriptor: SourceEvidenceViewportDescriptor
}

export function SourceEvidenceViewport({
  document,
  descriptor,
  sourceAnnotations,
  activeSourceAnnotationId,
  interactionHandlers,
}: SourceEvidenceViewportProps) {
  const rootRef = useRef<HTMLElement>(null)
  const viewportRef = useRef<HTMLDivElement>(null)
  const initializedViewportKeyRef = useRef<string | null>(null)
  const userOwnedScrollRef = useRef(false)
  const [viewportBodyHeightPx, setViewportBodyHeightPx] = useState<number | null>(null)
  const [showReturnToEvidence, setShowReturnToEvidence] = useState(false)

  const syncReturnToEvidenceVisibility = useCallback(() => {
    const root = rootRef.current
    const viewport = viewportRef.current
    if (!root || !viewport) {
      setShowReturnToEvidence(false)
      return
    }
    const evidenceSentence = findSourceSentenceWithinRoot(root, {
      slotId: descriptor.slotId,
      documentId: descriptor.documentId,
      sentenceId: descriptor.evidenceSentenceId,
    })
    if (!evidenceSentence) {
      setShowReturnToEvidence(false)
      return
    }
    setShowReturnToEvidence(
      shouldShowReturnToEvidenceAnchor(viewport, evidenceSentence),
    )
  }, [descriptor])

  const measureReadableLayout = useCallback(() => {
    const root = rootRef.current
    const viewport = viewportRef.current
    if (!root || !viewport) {
      return null
    }

    const evidenceSentence = findSourceSentenceWithinRoot(root, {
      slotId: descriptor.slotId,
      documentId: descriptor.documentId,
      sentenceId: descriptor.evidenceSentenceId,
    })
    const bodyElement = root.querySelector<HTMLElement>('[data-source-canonical-body="true"]')
    if (!evidenceSentence || !bodyElement) {
      return null
    }

    const layout = measureViewportReadableLayout(viewport, evidenceSentence, bodyElement)
    setViewportBodyHeightPx(layout.viewportBodyHeightPx)
    viewport.dataset.sourceEvidenceViewportBodyHeightPx = String(layout.viewportBodyHeightPx)
    return layout
  }, [descriptor])

  useLayoutEffect(() => {
    userOwnedScrollRef.current = false
    initializedViewportKeyRef.current = null
    setViewportBodyHeightPx(null)
  }, [descriptor.viewportKey])

  useLayoutEffect(() => {
    measureReadableLayout()
  }, [measureReadableLayout, descriptor.viewportKey])

  useLayoutEffect(() => {
    if (viewportBodyHeightPx === null) {
      return
    }
    if (initializedViewportKeyRef.current === descriptor.viewportKey) {
      return
    }
    const viewport = viewportRef.current
    const layout = measureReadableLayout()
    if (!viewport || !layout) {
      return
    }
    viewport.scrollTop = layout.initialScrollTopPx
    initializedViewportKeyRef.current = descriptor.viewportKey
    syncReturnToEvidenceVisibility()
  }, [
    descriptor.viewportKey,
    measureReadableLayout,
    syncReturnToEvidenceVisibility,
    viewportBodyHeightPx,
  ])

  useEffect(() => {
    const viewport = viewportRef.current
    if (!viewport) {
      return
    }

    const markUserScroll = () => {
      userOwnedScrollRef.current = true
    }
    const handleScroll = () => {
      syncReturnToEvidenceVisibility()
    }
    viewport.addEventListener('wheel', markUserScroll, { passive: true })
    viewport.addEventListener('touchmove', markUserScroll, { passive: true })
    viewport.addEventListener('scroll', handleScroll, { passive: true })

    const resizeObserver = new ResizeObserver(() => {
      measureReadableLayout()
      syncReturnToEvidenceVisibility()
    })
    resizeObserver.observe(viewport)

    syncReturnToEvidenceVisibility()

    return () => {
      viewport.removeEventListener('wheel', markUserScroll)
      viewport.removeEventListener('touchmove', markUserScroll)
      viewport.removeEventListener('scroll', handleScroll)
      resizeObserver.disconnect()
    }
  }, [descriptor.viewportKey, measureReadableLayout, syncReturnToEvidenceVisibility])

  const handleReturnToEvidence = useCallback(() => {
    const root = rootRef.current
    const viewport = viewportRef.current
    if (!root || !viewport) {
      return
    }
    const evidenceSentence = findSourceSentenceWithinRoot(root, {
      slotId: descriptor.slotId,
      documentId: descriptor.documentId,
      sentenceId: descriptor.evidenceSentenceId,
    })
    const bodyElement = root.querySelector<HTMLElement>('[data-source-canonical-body="true"]')
    if (!evidenceSentence || !bodyElement) {
      return
    }
    scrollViewportToReadableEvidenceAnchor(viewport, evidenceSentence, bodyElement)
    syncReturnToEvidenceVisibility()
  }, [descriptor, syncReturnToEvidenceVisibility])

  const sectionSlice = document.blocks.slice(
    descriptor.sectionStartBlockIndex,
    descriptor.sectionEndBlockIndexExclusive,
  )
  const sectionHeading = descriptor.sectionHeadingSourceBlockId
    ? document.blocks.find(
        (block) => block.sourceBlockId === descriptor.sectionHeadingSourceBlockId,
      )?.displayText
    : 'Opening content'
  const canOmitDuplicateSectionHeading =
    sectionSlice.length > 1 &&
    sectionSlice[0]?.sourceBlockId === descriptor.sectionHeadingSourceBlockId
  const showSectionChromeTitle = canOmitDuplicateSectionHeading && Boolean(sectionHeading)

  return (
    <section
      ref={rootRef}
      data-source-evidence-viewport="true"
      data-viewport-key={descriptor.viewportKey}
      className={cn(
        'min-w-0 overflow-hidden rounded border bg-background',
        resultReviewContainerBorderClassName,
      )}
    >
      {showSectionChromeTitle || showReturnToEvidence ? (
        <header
          {...sourceEvidenceViewportChromeAttributes}
          className={cn(
            'flex items-center gap-2 border-b px-3 py-1',
            resultReviewInternalSeparatorBorderClassName,
          )}
        >
          {showSectionChromeTitle ? (
            <p className="min-w-0 flex-1 truncate text-xs font-medium text-muted-foreground">
              {sectionHeading}
            </p>
          ) : (
            <span className="min-w-0 flex-1" />
          )}
          {showReturnToEvidence ? (
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              data-source-evidence-return-to-anchor="true"
              data-source-evidence-viewport-header-action="true"
              className="shrink-0 text-muted-foreground"
              aria-label="回到原句"
              title="回到原句"
              onClick={handleReturnToEvidence}
            >
              <Crosshair aria-hidden="true" />
            </Button>
          ) : null}
        </header>
      ) : null}
      <div className="min-w-0">
        <ScrollArea
          {...sourceEvidenceViewportScrollAttributes}
          {...sourceEvidenceViewportReadableSizingAttributes}
          className={sourceEvidenceViewportScrollAreaClassName}
          style={viewportBodyHeightPx === null ? undefined : { height: viewportBodyHeightPx }}
          viewportRef={viewportRef}
          viewportClassName="[&>div]:!block [&>div]:!w-full [&>div]:!min-w-0"
        >
          <SourceSectionReader
            document={document}
            slotId={descriptor.slotId}
            viewportKey={descriptor.viewportKey}
            sectionStartBlockIndex={descriptor.sectionStartBlockIndex}
            sectionEndBlockIndexExclusive={descriptor.sectionEndBlockIndexExclusive}
            primaryEvidenceSentenceId={descriptor.evidenceSentenceId}
            omitLeadingSectionHeadingSourceBlockId={
              canOmitDuplicateSectionHeading ? descriptor.sectionHeadingSourceBlockId : null
            }
            compactViewportPresentation
            sourceAnnotations={sourceAnnotations}
            activeSourceAnnotationId={activeSourceAnnotationId}
            interactionHandlers={interactionHandlers}
          />
        </ScrollArea>
      </div>
    </section>
  )
}

export type SourceEvidenceViewportWorkspaceProps = SourceEvidenceViewportPresentationProps & {
  document: DocumentView
  descriptors: readonly SourceEvidenceViewportDescriptor[]
  sourceContentRef?: RefObject<HTMLDivElement | null>
} & Partial<Pick<SourceDocumentInteractionProps,
  | 'savingAnnotationId'
  | 'onSourceAnnotationActivate'
  | 'onClearActiveSourceAnnotation'
  | 'onClearFocusedSentence'
  | 'onClearFocusedBlock'
  | 'onCreateHighlight'
  | 'onDeleteHighlight'
  | 'onCreateComment'
  | 'onUpdateComment'
  | 'onDeleteComment'
  | 'onCreateEdit'
  | 'onUpdateEdit'
  | 'onDeleteEdit'
>>

export function SourceEvidenceViewportWorkspace({
  document,
  descriptors,
  sourceContentRef,
  sourceAnnotations = emptySourceAnnotations,
  activeSourceAnnotationId = null,
  savingAnnotationId = null,
  onSourceAnnotationActivate,
  onClearActiveSourceAnnotation,
  onClearFocusedSentence,
  onClearFocusedBlock,
  onCreateHighlight,
  onDeleteHighlight,
  onCreateComment,
  onUpdateComment,
  onDeleteComment,
  onCreateEdit,
  onUpdateEdit,
  onDeleteEdit,
}: SourceEvidenceViewportWorkspaceProps) {
  const workspaceRootRef = useRef<HTMLElement | null>(null)
  const slotId = descriptors[0]?.slotId ?? 'source'
  const resolveSentenceAnchor = useCallback(
    (identity: { sentenceId: string; slotId?: string; docId?: string }) => {
      if (
        (identity.slotId && identity.slotId !== slotId) ||
        (identity.docId && identity.docId !== document.docId)
      ) {
        return null
      }
      return resolveSourceSentenceAnchor(slotId, document, identity.sentenceId)
    },
    [document, slotId],
  )

  useEffect(() => {
    if (!activeSourceAnnotationId || !onClearActiveSourceAnnotation) {
      return
    }
    const root = workspaceRootRef.current
    const annotation = sourceAnnotations.get(activeSourceAnnotationId)
    if (!root || !annotation) {
      return
    }
    const mountedViewports = [...root.querySelectorAll<HTMLElement>(
      '[data-source-evidence-viewport="true"]',
    )]
    const expectedKeys = new Set(descriptors.map((descriptor) => descriptor.viewportKey))
    if (
      mountedViewports.length !== descriptors.length ||
      mountedViewports.some((viewport) => !expectedKeys.has(viewport.dataset.viewportKey ?? ''))
    ) {
      return
    }
    const visible = findSourceSentenceWithinRoot(root, {
      slotId: annotation.anchor.slotId,
      documentId: annotation.anchor.docId,
      sentenceId: annotation.anchor.sentenceId,
    })
    if (!visible) {
      onClearActiveSourceAnnotation()
    }
  }, [
    activeSourceAnnotationId,
    descriptors,
    onClearActiveSourceAnnotation,
    sourceAnnotations,
  ])

  return (
    <SourceDocumentInteraction
      className="min-h-0 min-w-0"
      interactionRootRef={workspaceRootRef}
      selectionBoundarySelector="[data-source-evidence-viewport='true']"
      sourceAnnotations={sourceAnnotations}
      savingAnnotationId={savingAnnotationId}
      resolveSentenceAnchor={resolveSentenceAnchor}
      activeSourceAnnotationId={activeSourceAnnotationId}
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
    >
      {(interactionHandlers) => (
        <div
          ref={sourceContentRef}
          data-result-review-source-content="true"
          className="grid min-h-0 min-w-0 gap-2"
        >
          {descriptors.map((descriptor) => (
            <SourceEvidenceViewport
              key={descriptor.viewportKey}
              document={document}
              descriptor={descriptor}
              sourceAnnotations={sourceAnnotations}
              activeSourceAnnotationId={activeSourceAnnotationId}
              interactionHandlers={interactionHandlers}
            />
          ))}
        </div>
      )}
    </SourceDocumentInteraction>
  )
}
