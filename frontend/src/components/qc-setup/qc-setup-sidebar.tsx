import { useMemo, useState } from 'react'

import { buildCandidateChapterSections } from '@/adapters/candidate-scope-view'
import { CandidateScopeEditPanel } from '@/components/review/candidate-scope-edit-panel'
import { CandidateScopeViewPanel } from '@/components/review/candidate-scope-view-panel'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  CANDIDATE_CHAPTER_HELPER_TEXT,
  getQcFlowPresentation,
  QC_SETUP_PROCEED_LABEL,
  QC_SETUP_PROCEED_PENDING_LABEL,
  QC_SETUP_PROCEED_WAITING_HINT,
  QC_FUNCTION_ID,
} from '@/lib/launcher-presentation'
import type {
  CandidateChapterSection,
  CandidateScopeContentDomainGroup,
  CandidateHeading,
  CandidateScopeSlotState,
} from '@/types/candidate-scope'
import type { QcExecutionStatus } from '@/types/qc-setup'
import { cn } from '@/lib/utils'

type QcSetupSidebarProps = {
  flowId: string
  slotState: CandidateScopeSlotState
  contentDomainGroups: CandidateScopeContentDomainGroup[]
  currentSelected: Set<string>
  draftSelected: Set<string>
  isEditing: boolean
  onStartEdit: () => void
  onApply: () => void
  onCancelEdit: () => void
  onToggleHeading: (heading: CandidateHeading, checked: boolean) => void
  onScrollToBlock: (blockId: string) => void
  focusedBlockId: string | null
  nextStatus: QcExecutionStatus
  nextError: string | null
  onNext: () => void
  isNextDisabled: boolean
  canResume: boolean
}

const sidebarMainActionClassName =
  'inline-flex items-center justify-center rounded-[6px] border border-[#1e56e3] bg-[#1e56e3] font-medium text-white transition-[background-color,border-color] hover:border-[#1545bf] hover:bg-[#1545bf] disabled:pointer-events-none disabled:opacity-50'

const contentDomainPillClassName =
  'inline-flex h-6 shrink-0 items-center rounded-[4px] border px-2 text-[12px] font-medium transition-colors outline-none! focus:outline-none! focus-visible:outline-none!'

function contentDomainPillClassNameFor(isActive: boolean): string {
  return cn(
    contentDomainPillClassName,
    isActive
      ? 'border-[#91caff] bg-[#f0f5ff] text-[#2b5ae8]'
      : 'border-transparent bg-transparent text-[#64748B] hover:bg-[#f5f6f7] hover:text-[#475569]',
  )
}

function CandidateChapterEditFooter({
  onApply,
  onCancelEdit,
}: {
  onApply: () => void
  onCancelEdit: () => void
}) {
  return (
    <div
      data-candidate-chapter-edit-footer
      className="sticky bottom-0 z-10 -mx-3 mt-3 shrink-0 border-t border-[#E8ECF1] bg-[#F8FAFC] px-3 pt-3"
    >
      <div className="flex items-center justify-end gap-2">
        <Button
          type="button"
          variant="ghost"
          className="h-8 px-3 text-[12px] font-medium text-[#595959] hover:bg-[#F5F6F7] hover:text-[#262626]"
          onClick={onCancelEdit}
        >
          取消
        </Button>
        <button
          type="button"
          data-sidebar-main-action
          className={cn('h-8 px-3 text-[12px]', sidebarMainActionClassName)}
          onClick={onApply}
        >
          应用调整
        </button>
      </div>
    </div>
  )
}

function CandidateChapterHeader({
  sections,
  activeSection,
  isEditing,
  canResume,
  nextStatus,
  onSelectContentDomain,
  onStartEdit,
}: {
  sections: CandidateChapterSection[]
  activeSection: CandidateChapterSection | undefined
  isEditing: boolean
  canResume: boolean
  nextStatus: QcExecutionStatus
  onSelectContentDomain: (contentDomainId: string) => void
  onStartEdit: () => void
}) {
  return (
    <div className="shrink-0 space-y-2">
      <div className="space-y-1">
        <h4 className="text-[13px] font-medium text-[#334155]">候选章节</h4>
        <p className="text-[12px] leading-relaxed text-[#64748B]">
          {CANDIDATE_CHAPTER_HELPER_TEXT}
        </p>
      </div>
      <div className="flex items-center justify-between gap-2">
        <div
          className="flex min-w-0 flex-wrap items-center gap-1.5"
          role="tablist"
          aria-label="内容域"
        >
          {sections.map((section) => {
            const isActive = section.contentDomainId === activeSection?.contentDomainId
            return (
              <button
                key={section.contentDomainId}
                type="button"
                role="tab"
                aria-selected={isActive}
                data-content-domain-id={section.contentDomainId}
                className={contentDomainPillClassNameFor(isActive)}
                onClick={() => onSelectContentDomain(section.contentDomainId)}
              >
                {section.domainLabel}
              </button>
            )
          })}
        </div>
        {!isEditing ? (
          <Button
            type="button"
            variant="ghost"
            className="h-auto shrink-0 px-1.5 py-0.5 text-[12px] font-medium text-[#2563EB] hover:bg-[#EFF6FF] hover:text-[#1D4ED8]"
            onClick={onStartEdit}
            disabled={!canResume || nextStatus === 'completed'}
          >
            调整
          </Button>
        ) : null}
      </div>
    </div>
  )
}

function QcFunctionCard({
  functionId,
  functionLabel,
  isEditing,
  sections,
  activeSection,
  canResume,
  nextStatus,
  onSelectContentDomain,
  onStartEdit,
  onApply,
  onCancelEdit,
  editHeadings,
  draftSelected,
  onToggleHeading,
  slotState,
  onScrollToBlock,
  focusedBlockId,
}: {
  functionId: string
  functionLabel: string
  isEditing: boolean
  sections: CandidateChapterSection[]
  activeSection: CandidateChapterSection | undefined
  canResume: boolean
  nextStatus: QcExecutionStatus
  onSelectContentDomain: (contentDomainId: string) => void
  onStartEdit: () => void
  onApply: () => void
  onCancelEdit: () => void
  editHeadings: CandidateHeading[]
  draftSelected: Set<string>
  onToggleHeading: (heading: CandidateHeading, checked: boolean) => void
  slotState: CandidateScopeSlotState
  onScrollToBlock: (blockId: string) => void
  focusedBlockId: string | null
}) {
  return (
    <section
      data-function-card
      data-function-id={functionId}
      data-function-local-setting
      className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-md border border-[#E2E8F0] bg-[#F8FAFC] p-3"
    >
      <h3
        id="qc-function-title"
        className="mb-2 shrink-0 text-[14px] font-semibold leading-snug text-[#0F172A]"
      >
        {functionLabel}
      </h3>

      <CandidateChapterHeader
        sections={sections}
        activeSection={activeSection}
        isEditing={isEditing}
        canResume={canResume}
        nextStatus={nextStatus}
        onSelectContentDomain={onSelectContentDomain}
        onStartEdit={onStartEdit}
      />

      {isEditing ? (
        <>
          <div className="mt-3 flex min-h-0 flex-1 flex-col overflow-hidden">
            <CandidateScopeEditPanel
              headings={editHeadings}
              draftSelected={draftSelected}
              onToggle={onToggleHeading}
            />
          </div>
          <CandidateChapterEditFooter onApply={onApply} onCancelEdit={onCancelEdit} />
        </>
      ) : activeSection ? (
        <ScrollArea
          className="mt-3 min-h-0 flex-1 [&_[data-slot=scroll-area-scrollbar]]:w-2 [&_[data-slot=scroll-area-thumb]]:rounded-full [&_[data-slot=scroll-area-thumb]]:bg-[#E2E8F0]"
        >
          <div className="pr-2">
            <CandidateScopeViewPanel
              docId={slotState.docId}
              headings={activeSection.headings}
              selectedAnchors={new Set(activeSection.candidateAnchorBlockIds)}
              onScrollToBlock={onScrollToBlock}
              focusedBlockId={focusedBlockId}
            />
          </div>
        </ScrollArea>
      ) : null}
    </section>
  )
}

export function QcSetupSidebar({
  flowId,
  slotState,
  contentDomainGroups,
  currentSelected,
  draftSelected,
  isEditing,
  onStartEdit,
  onApply,
  onCancelEdit,
  onToggleHeading,
  onScrollToBlock,
  focusedBlockId,
  nextStatus,
  nextError,
  onNext,
  isNextDisabled,
  canResume,
}: QcSetupSidebarProps) {
  const flowPresentation = getQcFlowPresentation(flowId)
  const sections = useMemo(
    () => buildCandidateChapterSections(slotState, currentSelected, contentDomainGroups),
    [slotState, currentSelected, contentDomainGroups],
  )

  const [activeContentDomainId, setActiveContentDomainId] = useState<string | undefined>(
    undefined,
  )

  const activeSection =
    sections.find(
      (section) =>
        section.contentDomainId === (activeContentDomainId ?? sections[0]?.contentDomainId),
    ) ?? sections[0]

  const editHeadings = useMemo(
    () => activeSection?.headings ?? sections.flatMap((section) => section.headings),
    [activeSection, sections],
  )

  const isProceedPending = nextStatus === 'freezing'
  const nextLabel = isProceedPending ? QC_SETUP_PROCEED_PENDING_LABEL : QC_SETUP_PROCEED_LABEL

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex min-h-0 flex-1 flex-col px-5 pt-4 pb-4">
        <QcFunctionCard
          functionId={QC_FUNCTION_ID}
          functionLabel={flowPresentation.localizedName}
          isEditing={isEditing}
          sections={sections}
          activeSection={activeSection}
          canResume={canResume}
          nextStatus={nextStatus}
          onSelectContentDomain={setActiveContentDomainId}
          onStartEdit={onStartEdit}
          onApply={onApply}
          onCancelEdit={onCancelEdit}
          editHeadings={editHeadings}
          draftSelected={draftSelected}
          onToggleHeading={onToggleHeading}
          slotState={slotState}
          onScrollToBlock={onScrollToBlock}
          focusedBlockId={focusedBlockId}
        />
      </div>

      {canResume || nextError || isProceedPending ? (
        <div
          data-sidebar-task-footer
          className="sticky bottom-0 mt-auto bg-white px-5 pt-4 pb-5"
        >
          <div className="flex flex-col gap-2">
            {nextError ? (
              <p className="text-xs text-destructive">{nextError}</p>
            ) : null}
            {canResume ? (
              <>
                <button
                  type="button"
                  data-sidebar-main-action
                  className={cn('h-10 w-full text-[14px]', sidebarMainActionClassName)}
                  onClick={onNext}
                  disabled={isNextDisabled}
                >
                  {nextLabel}
                </button>
                {isProceedPending ? (
                  <p className="text-center text-xs text-muted-foreground">
                    {QC_SETUP_PROCEED_WAITING_HINT}
                  </p>
                ) : null}
              </>
            ) : null}
          </div>
        </div>
      ) : (
        <p className="sticky bottom-0 mt-auto bg-white px-5 pb-5 text-center text-[12px] text-[#64748B]">
          当前页面仅供历史查看
        </p>
      )}
    </div>
  )
}
