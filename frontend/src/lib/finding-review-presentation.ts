import {
  resultFindingSelectedSurfaceClassName,
  resultReviewContainerBorderClassName,
  resultReviewContainerBorderHoverClassName,
} from '@/lib/result-review-visual-tokens'
import type { FindingLabel, InternalResultFinding } from '@/types/document-consistency-qc'
import type {
  FindingReviewDecision,
  FindingReviewEntry,
  FindingReviewStatePayload,
} from '@/types/finding-review'

export type FindingPresentation = {
  finding: InternalResultFinding
  decision: FindingReviewDecision
  marked: boolean
  note?: string
}

export function resolveFindingDecision(
  reviewState: FindingReviewStatePayload | null,
  findingId: string,
): FindingReviewDecision {
  return reviewState?.entriesByFindingId.get(findingId)?.decision ?? 'pending'
}

export function resolveFindingMarked(
  reviewState: FindingReviewStatePayload | null,
  findingId: string,
): boolean {
  return reviewState?.entriesByFindingId.get(findingId)?.marked ?? false
}

export function resolveFindingNote(
  reviewState: FindingReviewStatePayload | null,
  findingId: string,
): string | undefined {
  return reviewState?.entriesByFindingId.get(findingId)?.note
}

export function buildFindingPresentation(
  finding: InternalResultFinding,
  reviewState: FindingReviewStatePayload | null,
): FindingPresentation {
  return {
    finding,
    decision: resolveFindingDecision(reviewState, finding.findingId),
    marked: resolveFindingMarked(reviewState, finding.findingId),
    note: resolveFindingNote(reviewState, finding.findingId),
  }
}

export function mergeFindingReviewEntry(
  current: FindingReviewStatePayload,
  entry: FindingReviewEntry,
): FindingReviewStatePayload {
  const entriesByFindingId = new Map(current.entriesByFindingId)
  entriesByFindingId.set(entry.findingId, entry)
  return {
    flowRunId: current.flowRunId,
    entriesByFindingId,
  }
}

export function applyFindingReviewPayload(
  current: FindingReviewStatePayload | null,
  payload: FindingReviewStatePayload,
): FindingReviewStatePayload {
  const entriesByFindingId = new Map(current?.entriesByFindingId ?? [])

  for (const findingId of [...entriesByFindingId.keys()]) {
    if (!payload.entriesByFindingId.has(findingId)) {
      entriesByFindingId.delete(findingId)
    }
  }

  for (const [findingId, entry] of payload.entriesByFindingId) {
    entriesByFindingId.set(findingId, { ...entry })
  }

  return {
    flowRunId: payload.flowRunId,
    entriesByFindingId,
  }
}

export function nextDecisionOnConfirmClick(
  current: FindingReviewDecision,
): FindingReviewDecision {
  return current === 'confirmed' ? 'pending' : 'confirmed'
}

export function nextDecisionOnIgnoreClick(
  current: FindingReviewDecision,
): FindingReviewDecision {
  return current === 'ignored' ? 'pending' : 'ignored'
}

export function nextMarkedOnMarkClick(current: boolean): boolean {
  return !current
}

/** Queue card severity tone (pending label severity, gray when confirmed). */
export type FindingReviewQueueLeftEdge = 'fail' | 'need_review' | 'confirmed'

export function resolveFindingReviewQueueLeftEdge(
  decision: FindingReviewDecision,
  label: FindingLabel,
): FindingReviewQueueLeftEdge | null {
  if (decision === 'ignored') {
    return null
  }
  if (decision === 'confirmed') {
    return 'confirmed'
  }
  if (label === 'need_review') {
    return 'need_review'
  }
  return 'fail'
}

/** Lighter than source evidence highlight — shared muted blue hierarchy. */
export const findingReviewQueueSelectedSurfaceClassName =
  resultFindingSelectedSurfaceClassName

/** Focus ring for the queue card selection control. */
export const FINDING_REVIEW_QUEUE_SELECTED_CHROME_COLOR = '#2b5ae8'

const FINDING_REVIEW_QUEUE_CARD_NEUTRAL_BORDER_CLASS = [
  resultReviewContainerBorderClassName,
  resultReviewContainerBorderHoverClassName,
].join(' ')

/** Vertical inset so the severity mark clears rounded card corners. */
export const FINDING_REVIEW_QUEUE_LEFT_EDGE_VERTICAL_INSET_CLASS = 'top-[8px] bottom-[8px]'

/** Half of the indicator sits outside the card; this edge aligns with the left border. */
export const FINDING_REVIEW_QUEUE_LEFT_EDGE_OUTWARD_HALF_WIDTH_PX = 4

export const FINDING_REVIEW_QUEUE_LEFT_EDGE_WIDTH_CLASS = 'w-[8px]'

export const FINDING_REVIEW_QUEUE_LEFT_EDGE_POSITION_CLASS = '-left-1'

/**
 * Trapezoid mirrored across the card left border (50% of the 8px-wide box).
 * The straight edge on the border runs top-to-bottom; top/bottom caps open outward.
 */
export const FINDING_REVIEW_QUEUE_LEFT_EDGE_CLIP_PATH =
  'polygon(50% 0, 0 5px, 0 calc(100% - 5px), 50% 100%)'

/** Subtle right-side shadow so the index bar reads above the card surface. */
export const FINDING_REVIEW_QUEUE_LEFT_EDGE_DROP_SHADOW_FILTER =
  'drop-shadow(1px 0 2px rgba(0,0,0,0.12))'

/** Uniform card border; severity is a clipped fill bar on the left. */
export function findingReviewQueueSeverityBorderClassName(
  _edge: FindingReviewQueueLeftEdge | null = null,
): string {
  return FINDING_REVIEW_QUEUE_CARD_NEUTRAL_BORDER_CLASS
}

export function findingReviewQueueLeftEdgeIndicatorClassName(
  edge: FindingReviewQueueLeftEdge,
): string {
  if (edge === 'fail') {
    return 'bg-red-500'
  }
  if (edge === 'need_review') {
    return 'bg-amber-400'
  }
  return 'bg-slate-400'
}

export function findingReviewQueueCardClassName(
  selected: boolean,
  edge: FindingReviewQueueLeftEdge | null = null,
): string {
  if (selected) {
    return [findingReviewQueueSelectedSurfaceClassName, findingReviewQueueSeverityBorderClassName(edge)].join(' ')
  }
  return ['bg-background', findingReviewQueueSeverityBorderClassName(edge)].join(' ')
}

export function findingReviewQueueSelectFocusRingClassName(): string {
  return 'focus-visible:ring-[#2b5ae8]'
}

/** Shell classes shared by every queue card. */
export function findingReviewQueueCardShellClassName(
  selected: boolean,
  edge: FindingReviewQueueLeftEdge | null = null,
): string {
  return ['relative overflow-visible', findingReviewQueueCardClassName(selected, edge)].join(' ')
}

export type FindingReviewQueueActionGlyphTone = 'neutral' | 'flagged' | 'note'

const QUEUE_ACTION_BUTTON_SURFACE_CLASS =
  'border border-transparent bg-transparent hover:bg-slate-200 active:bg-slate-200'

export function findingReviewQueueNeutralActionButtonClassName(): string {
  return [
    QUEUE_ACTION_BUTTON_SURFACE_CLASS,
    'text-slate-500 hover:text-slate-700 active:text-slate-800',
  ].join(' ')
}

export function findingReviewQueueFlaggedActionButtonClassName(): string {
  return [
    QUEUE_ACTION_BUTTON_SURFACE_CLASS,
    'text-amber-500 hover:text-amber-600 active:text-amber-700',
  ].join(' ')
}

export function findingReviewQueueNoteActionButtonClassName(): string {
  return [
    QUEUE_ACTION_BUTTON_SURFACE_CLASS,
    'text-sky-500 hover:text-sky-600 active:text-sky-700',
  ].join(' ')
}

export function findingReviewQueueActionButtonClassName(
  glyphTone: FindingReviewQueueActionGlyphTone,
): string {
  if (glyphTone === 'flagged') {
    return findingReviewQueueFlaggedActionButtonClassName()
  }
  if (glyphTone === 'note') {
    return findingReviewQueueNoteActionButtonClassName()
  }
  return findingReviewQueueNeutralActionButtonClassName()
}

export function findingReviewQueueFlagGlyphClassName(marked: boolean): string {
  const base = 'size-3.5 shrink-0 stroke-current'
  return marked ? `${base} fill-current` : `${base} fill-none`
}

export function findingReviewQueueNoteGlyphClassName(hasNote: boolean): string {
  const base = 'size-3.5 shrink-0 stroke-current'
  return hasNote ? `${base} fill-current` : `${base} fill-none`
}

/** Queue-only conclusion typography (narrow sidebar, CJK-friendly justify). */
export const FINDING_REVIEW_QUEUE_CONCLUSION_TYPOGRAPHY_CLASS =
  'text-[15px] leading-[1.55] text-justify [text-justify:inter-character] break-normal'

export function findingReviewQueueConclusionClassName(
  _decision: FindingReviewDecision,
): string {
  return FINDING_REVIEW_QUEUE_CONCLUSION_TYPOGRAPHY_CLASS
}

export function findingReviewQueueNotePreviewContentClassName(
  _decision: FindingReviewDecision,
): string {
  return 'text-slate-600'
}

/** Shared neutral grammar for Queue icon-only review actions. */
export function findingReviewQueueActionInactiveClassName(): string {
  return [
    'border border-transparent bg-transparent text-slate-500',
    'hover:bg-slate-200 hover:text-slate-700',
    'active:bg-slate-200 active:text-slate-800',
  ].join(' ')
}

export function findingReviewQueueActionActiveClassName(): string {
  return [
    'border border-slate-200 bg-slate-100 text-slate-700',
    'hover:border-slate-200 hover:bg-slate-200 hover:text-slate-800',
  ].join(' ')
}

export function findingReviewQueueActionFocusVisibleClassName(): string {
  return 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/80 focus-visible:ring-offset-1'
}

export function findingReviewQueueActionClassName(active: boolean): string {
  return active
    ? findingReviewQueueActionActiveClassName()
    : findingReviewQueueActionInactiveClassName()
}

/** Queue confirm/ignore actions use a neutral container; aria-pressed only. */
export function findingReviewQueueActionVisualClassName(): string {
  return findingReviewQueueNeutralActionButtonClassName()
}

/** True when inactive grammar uses a non-transparent hover surface (regression guard). */
export function findingReviewQueueActionInactiveUsesHoverBackground(className: string): boolean {
  return /hover:bg-(?!transparent\b)/.test(className)
}

export function findingReviewQueueActionUsesSemanticColor(className: string): boolean {
  const semanticTokens = ['amber', 'sky', 'green', 'emerald', 'yellow', 'blue']
  return semanticTokens.some((token) => className.includes(token))
}

export function findingReviewConfirmedActionClassName(
  decision: FindingReviewDecision,
): string {
  return decision === 'confirmed' ? findingReviewQueueActionClassName(true) : ''
}

export function findingReviewIgnoredActionClassName(
  decision: FindingReviewDecision,
): string {
  return decision === 'ignored' ? findingReviewQueueActionClassName(true) : ''
}

export function findingReviewMarkedActionClassName(marked: boolean): string {
  return marked ? findingReviewQueueActionClassName(true) : ''
}

export function findingReviewNoteActionClassName(hasNote: boolean): string {
  return hasNote ? findingReviewQueueActionClassName(true) : ''
}

/** Max visible lines for inline note preview in the Finding Queue. */
export const FINDING_QUEUE_NOTE_PREVIEW_LINE_CLAMP = 3

/** Shared body size for queue note preview label and content. */
export const FINDING_REVIEW_QUEUE_NOTE_PREVIEW_TYPOGRAPHY_CLASS = 'text-xs leading-snug'

/** Plain checkmark for confirm actions (not circle-check). */
export const FINDING_REVIEW_CONFIRM_CHECK_SIZE_PX = 16
export const FINDING_REVIEW_CONFIRM_CHECK_STROKE_WIDTH = 2.5

/** @deprecated Use findingReviewConfirmedActionClassName */
export function findingReviewResolvedActionClassName(
  decision: FindingReviewDecision,
): string {
  return findingReviewConfirmedActionClassName(decision)
}

/** @deprecated Use nextDecisionOnConfirmClick */
export function nextResolvedOnResolveClick(
  current: FindingReviewDecision,
): FindingReviewDecision {
  return nextDecisionOnConfirmClick(current)
}

/** @deprecated Use resolveFindingDecision */
export function resolveFindingResolved(
  reviewState: FindingReviewStatePayload | null,
  findingId: string,
): boolean {
  return resolveFindingDecision(reviewState, findingId) === 'confirmed'
}
