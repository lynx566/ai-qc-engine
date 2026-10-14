import { useState, type MouseEvent, type ReactNode } from 'react'

import {
  FindingReviewConfirmGlyph,
  FindingReviewFlagGlyph,
  FindingReviewIgnoreGlyph,
  FindingReviewNoteGlyph,
} from '@/components/review/finding-review-queue-action-glyphs'
import {
  buildFindingReviewNoteSavePatch,
  clearFindingReviewNotePatch,
} from '@/adapters/finding-review'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import { useResultEditorCommit } from '@/components/review/result-save-context'
import {
  FINDING_QUEUE_NOTE_PREVIEW_LINE_CLAMP,
  FINDING_REVIEW_QUEUE_NOTE_PREVIEW_TYPOGRAPHY_CLASS,
  findingReviewQueueActionButtonClassName,
  findingReviewQueueActionFocusVisibleClassName,
  findingReviewQueueConclusionClassName,
  findingReviewQueueNotePreviewContentClassName,
  nextDecisionOnConfirmClick,
  nextDecisionOnIgnoreClick,
  nextMarkedOnMarkClick,
  type FindingPresentation,
  type FindingReviewQueueActionGlyphTone,
} from '@/lib/finding-review-presentation'
import {
  resultReviewContainerBorderClassName,
  resultReviewInternalSeparatorBorderClassName,
} from '@/lib/result-review-visual-tokens'
import type { FindingReviewPatch } from '@/types/finding-review'
import { cn } from '@/lib/utils'

export type FindingReviewPatchHandler = (
  findingId: string,
  patch: FindingReviewPatch,
) => Promise<void>

function CompactFindingNoteEditor({
  presentation,
  saving,
  onPatchFindingReview,
  onClose,
}: {
  presentation: FindingPresentation
  saving: boolean
  onPatchFindingReview: FindingReviewPatchHandler
  onClose: () => void
}) {
  const [draft, setDraft] = useState(presentation.note ?? '')
  const findingId = presentation.finding.findingId

  const save = () => {
    return onPatchFindingReview(findingId, buildFindingReviewNoteSavePatch(draft)).then(onClose)
  }

  useResultEditorCommit(() => {
    if (!saving && draft !== (presentation.note ?? '')) return save()
  })

  const remove = () => {
    void onPatchFindingReview(findingId, clearFindingReviewNotePatch()).then(onClose)
      .catch(() => toast.error('保存失败，请重试。'))
  }

  return (
    <div
      className={cn(
        'space-y-2 rounded-md border border-dashed bg-background/80 p-2',
        resultReviewContainerBorderClassName,
      )}
      data-finding-note-editor="true"
      data-finding-queue-tier="note"
      onClick={(event) => event.stopPropagation()}
    >
      <label className="block text-xs font-medium text-muted-foreground">
        笔记
        <textarea
          className="mt-1.5 min-h-16 w-full rounded-md border bg-background px-2.5 py-2 text-sm text-foreground"
          value={draft}
          disabled={saving}
          onChange={(event) => setDraft(event.target.value)}
        />
      </label>
      <div className="flex flex-wrap justify-end gap-1">
        {presentation.note ? (
          <Button
            type="button"
            size="xs"
            variant="ghost"
            disabled={saving}
            className="text-destructive hover:text-destructive"
            onClick={remove}
          >
            删除
          </Button>
        ) : null}
        <Button type="button" size="xs" variant="outline" disabled={saving} onClick={onClose}>
          取消
        </Button>
        <Button type="button" size="xs" disabled={saving} onClick={() => {
          void save().catch(() => toast.error('保存失败，请重试。'))
        }}>
          保存
        </Button>
      </div>
    </div>
  )
}

function ReviewActionButton({
  saving,
  ariaLabel,
  ariaPressed,
  glyphTone = 'neutral',
  onClick,
  children,
}: {
  saving: boolean
  ariaLabel: string
  ariaPressed: boolean
  glyphTone?: FindingReviewQueueActionGlyphTone
  onClick: (event: MouseEvent<HTMLButtonElement>) => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      className={cn(
        'inline-flex size-7 items-center justify-center rounded-md transition-colors',
        findingReviewQueueActionButtonClassName(glyphTone),
        findingReviewQueueActionFocusVisibleClassName(),
      )}
      data-finding-review-action-glyph-tone={glyphTone}
      data-finding-review-action-pressed={ariaPressed ? 'true' : 'false'}
      disabled={saving}
      aria-label={ariaLabel}
      aria-pressed={ariaPressed}
      onClick={onClick}
    >
      {children}
    </button>
  )
}

export type FindingReviewCardProps = {
  presentation: FindingPresentation
  saving: boolean
  onPatchFindingReview: FindingReviewPatchHandler
  onSelectFinding: (findingId: string) => void
}

/** Editor state belongs to one Finding; stable identity preserves an in-progress draft. */
export function FindingReviewCard(props: FindingReviewCardProps) {
  return <FindingReviewCardContent key={props.presentation.finding.findingId} {...props} />
}

function FindingReviewCardContent({
  presentation,
  saving,
  onPatchFindingReview,
  onSelectFinding,
}: FindingReviewCardProps) {
  const [noteEditorOpen, setNoteEditorOpen] = useState(false)
  const { finding } = presentation
  const confirmActive = presentation.decision === 'confirmed'
  const ignoreActive = presentation.decision === 'ignored'
  const hasNote = Boolean(presentation.note)

  const stopAndPatch = (
    event: MouseEvent<HTMLButtonElement>,
    patch: FindingReviewPatch,
  ) => {
    event.stopPropagation()
    void onPatchFindingReview(finding.findingId, patch).catch(() => toast.error('保存失败，请重试。'))
  }

  const handleSelect = () => {
    onSelectFinding(finding.findingId)
  }

  return (
    <div
      className="relative z-10 flex min-w-0 flex-col gap-1.5 pointer-events-none"
      data-finding-review-card="true"
    >
      <div
        data-finding-queue-tier="primary"
        className="pointer-events-auto min-w-0"
        onClick={handleSelect}
      >
        <p
          data-finding-verdict-title="true"
          className={cn(
            'font-normal text-[#262626]',
            findingReviewQueueConclusionClassName(presentation.decision),
          )}
        >
          {finding.conclusion}
        </p>
      </div>

      {noteEditorOpen ? (
        <div className="pointer-events-auto">
          <CompactFindingNoteEditor
            presentation={presentation}
            saving={saving}
            onPatchFindingReview={onPatchFindingReview}
            onClose={() => setNoteEditorOpen(false)}
          />
        </div>
      ) : hasNote ? (
        <div
          data-finding-note-preview="true"
          data-finding-queue-tier="note"
          className={cn(
            'pointer-events-auto flex w-full min-w-0 items-baseline gap-x-1.5 border-l py-0 pl-2 pr-0.5 text-left',
            resultReviewInternalSeparatorBorderClassName,
          )}
          onClick={handleSelect}
        >
          <span
            className={cn(
              'shrink-0 text-muted-foreground',
              FINDING_REVIEW_QUEUE_NOTE_PREVIEW_TYPOGRAPHY_CLASS,
            )}
            data-finding-note-preview-label="true"
          >
            笔记
          </span>
          <span
            className={cn(
              'min-w-0 flex-1 whitespace-pre-wrap line-clamp-3',
              FINDING_REVIEW_QUEUE_NOTE_PREVIEW_TYPOGRAPHY_CLASS,
              findingReviewQueueNotePreviewContentClassName(presentation.decision),
            )}
            data-finding-note-preview-content="true"
            data-finding-note-preview-lines={FINDING_QUEUE_NOTE_PREVIEW_LINE_CLAMP}
          >
            {presentation.note}
          </span>
        </div>
      ) : null}

      {noteEditorOpen ? null : (
        <div
          className="pointer-events-auto flex h-7 items-center justify-end gap-2"
          data-finding-queue-item-footer="true"
          data-finding-queue-tier="footer"
          onClick={handleSelect}
        >
          <div
            className="pointer-events-auto flex shrink-0 items-center gap-0.5"
            data-finding-review-actions="true"
            onClick={(event) => event.stopPropagation()}
          >
            <ReviewActionButton
              saving={saving}
              ariaLabel={confirmActive ? '取消确认' : '确认'}
              ariaPressed={confirmActive}
              onClick={(event) => stopAndPatch(event, {
                decision: nextDecisionOnConfirmClick(presentation.decision),
              })}
            >
              <FindingReviewConfirmGlyph />
            </ReviewActionButton>
            <ReviewActionButton
              saving={saving}
              ariaLabel={ignoreActive ? '取消忽略' : '忽略'}
              ariaPressed={ignoreActive}
              onClick={(event) => stopAndPatch(event, {
                decision: nextDecisionOnIgnoreClick(presentation.decision),
              })}
            >
              <FindingReviewIgnoreGlyph />
            </ReviewActionButton>
            <ReviewActionButton
              saving={saving}
              ariaLabel={presentation.marked ? '取消标记' : '标记提醒'}
              ariaPressed={presentation.marked}
              glyphTone={presentation.marked ? 'flagged' : 'neutral'}
              onClick={(event) => stopAndPatch(event, {
                marked: nextMarkedOnMarkClick(presentation.marked),
              })}
            >
              <FindingReviewFlagGlyph marked={presentation.marked} />
            </ReviewActionButton>
            <ReviewActionButton
              saving={saving}
              ariaLabel={hasNote ? '编辑笔记' : '添加笔记'}
              ariaPressed={hasNote}
              glyphTone={hasNote ? 'note' : 'neutral'}
              onClick={(event) => {
                event.stopPropagation()
                setNoteEditorOpen(true)
              }}
            >
              <FindingReviewNoteGlyph hasNote={hasNote} />
            </ReviewActionButton>
          </div>
        </div>
      )}
    </div>
  )
}
