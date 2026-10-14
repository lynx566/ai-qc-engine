import { describe, expect, it } from 'vitest'

import {
  adaptFindingReviewState,
  buildFindingReviewNoteSavePatch,
  clearFindingReviewNotePatch,
  serializeFindingReviewPatch,
} from '@/adapters/finding-review'
import {
  applyFindingReviewPayload,
  buildFindingPresentation,
  findingReviewConfirmedActionClassName,
  findingReviewIgnoredActionClassName,
  findingReviewMarkedActionClassName,
  findingReviewNoteActionClassName,
  findingReviewQueueActionClassName,
  findingReviewQueueActionFocusVisibleClassName,
  findingReviewQueueActionInactiveClassName,
  findingReviewQueueActionInactiveUsesHoverBackground,
  findingReviewQueueActionActiveClassName,
  findingReviewQueueActionUsesSemanticColor,
  findingReviewQueueActionVisualClassName,
  findingReviewQueueCardClassName,
  findingReviewQueueCardShellClassName,
  FINDING_REVIEW_QUEUE_CONCLUSION_TYPOGRAPHY_CLASS,
  findingReviewQueueConclusionClassName,
  findingReviewQueueActionButtonClassName,
  findingReviewQueueFlagGlyphClassName,
  findingReviewQueueFlaggedActionButtonClassName,
  findingReviewQueueNeutralActionButtonClassName,
  findingReviewQueueLeftEdgeIndicatorClassName,
  FINDING_REVIEW_QUEUE_LEFT_EDGE_CLIP_PATH,
  FINDING_REVIEW_QUEUE_LEFT_EDGE_DROP_SHADOW_FILTER,
  FINDING_REVIEW_QUEUE_LEFT_EDGE_VERTICAL_INSET_CLASS,
  findingReviewQueueSeverityBorderClassName,
  findingReviewQueueNoteActionButtonClassName,
  findingReviewQueueNoteGlyphClassName,
  findingReviewQueueNotePreviewContentClassName,
  resolveFindingReviewQueueLeftEdge,
  nextDecisionOnConfirmClick,
  nextDecisionOnIgnoreClick,
  nextMarkedOnMarkClick,
  resolveFindingDecision,
  resolveFindingMarked,
} from '@/lib/finding-review-presentation'
import type { InternalResultFinding } from '@/types/document-consistency-qc'

const failFinding: InternalResultFinding = {
  findingId: 'L001',
  label: 'fail',
  conclusion: 'issue',
  comparisonModeId: 'scope_local',
  evidenceRefs: [],
}

describe('finding review adapter', () => {
  it('adapts empty review payload', () => {
    const payload = adaptFindingReviewState({
      flow_run_id: 'document_consistency_qc_test',
      findings: {},
    })
    expect(payload.flowRunId).toBe('document_consistency_qc_test')
    expect(payload.entriesByFindingId.size).toBe(0)
  })

  it('adapts decision and marked fields', () => {
    const payload = adaptFindingReviewState({
      flow_run_id: 'document_consistency_qc_test',
      findings: {
        L001: {
          finding_id: 'L001',
          decision: 'confirmed',
          marked: true,
          updated_at: '2026-09-13T00:00:00Z',
        },
      },
    })
    const entry = payload.entriesByFindingId.get('L001')
    expect(entry?.decision).toBe('confirmed')
    expect(entry?.marked).toBe(true)
  })

  it('maps legacy review_state and resolved on read', () => {
    const payload = adaptFindingReviewState({
      flow_run_id: 'document_consistency_qc_test',
      findings: {
        L001: {
          finding_id: 'L001',
          review_state: 'reviewed',
          updated_at: '2026-09-13T00:00:00Z',
        },
        L002: {
          finding_id: 'L002',
          review_state: 'flagged',
          note: 'keep',
          updated_at: '2026-09-13T00:00:00Z',
        },
        L003: {
          finding_id: 'L003',
          resolved: true,
          marked: false,
          updated_at: '2026-09-13T00:00:00Z',
        },
      },
    })
    expect(payload.entriesByFindingId.get('L001')?.decision).toBe('confirmed')
    expect(payload.entriesByFindingId.get('L002')?.decision).toBe('pending')
    expect(payload.entriesByFindingId.get('L002')?.marked).toBe(true)
    expect(payload.entriesByFindingId.get('L003')?.decision).toBe('confirmed')
  })

  it('serializes patch fields', () => {
    expect(serializeFindingReviewPatch({ decision: 'ignored' })).toEqual({ decision: 'ignored' })
    expect(serializeFindingReviewPatch({ marked: true })).toEqual({ marked: true })
    expect(serializeFindingReviewPatch(clearFindingReviewNotePatch())).toEqual({ note: '' })
    expect(serializeFindingReviewPatch(buildFindingReviewNoteSavePatch(''))).toEqual({ note: '' })
  })
})

describe('finding review presentation', () => {
  it('defaults missing entries to pending and unmarked', () => {
    expect(resolveFindingDecision(null, 'L001')).toBe('pending')
    expect(resolveFindingMarked(null, 'L001')).toBe(false)
  })

  it('implements confirm and ignore toggle semantics', () => {
    expect(nextDecisionOnConfirmClick('pending')).toBe('confirmed')
    expect(nextDecisionOnConfirmClick('confirmed')).toBe('pending')
    expect(nextDecisionOnIgnoreClick('pending')).toBe('ignored')
    expect(nextDecisionOnIgnoreClick('ignored')).toBe('pending')
  })

  it('implements marked toggle semantics independently', () => {
    expect(nextMarkedOnMarkClick(false)).toBe(true)
    expect(nextMarkedOnMarkClick(true)).toBe(false)
  })

  it('uses selection-only card treatment regardless of decision', () => {
    const defaultCard = findingReviewQueueCardClassName(false, null)
    expect(findingReviewQueueCardClassName(false, null)).toBe(defaultCard)
    expect(findingReviewQueueCardClassName(false, null)).toContain('bg-background')
    expect(findingReviewQueueCardClassName(false, 'fail')).toContain('border-[#C5CDD6]')
    expect(findingReviewQueueCardClassName(false, 'need_review')).toContain('border-[#C5CDD6]')
    expect(findingReviewQueueCardClassName(true, 'fail')).toContain('bg-[#F2F6FA]')
    expect(findingReviewQueueCardClassName(true, 'fail')).not.toContain('bg-[#E3EEF7]')
    expect(findingReviewQueueCardClassName(true, 'fail')).not.toContain('border-l-red-500')
    expect(findingReviewQueueCardClassName(true, 'fail')).not.toContain('border-[#2b5ae8]')
    expect(findingReviewQueueCardClassName(true, 'fail')).not.toContain('ring-')
    expect(findingReviewQueueCardClassName(true, 'fail')).not.toBe(defaultCard)
  })

  it('keeps conclusion and note preview typography independent of decision', () => {
    expect(findingReviewQueueConclusionClassName('ignored')).toBe(
      FINDING_REVIEW_QUEUE_CONCLUSION_TYPOGRAPHY_CLASS,
    )
    expect(findingReviewQueueConclusionClassName('pending')).toBe(
      FINDING_REVIEW_QUEUE_CONCLUSION_TYPOGRAPHY_CLASS,
    )
    expect(findingReviewQueueConclusionClassName('confirmed')).toBe(
      FINDING_REVIEW_QUEUE_CONCLUSION_TYPOGRAPHY_CLASS,
    )
    expect(FINDING_REVIEW_QUEUE_CONCLUSION_TYPOGRAPHY_CLASS).toContain('text-[15px]')
    expect(FINDING_REVIEW_QUEUE_CONCLUSION_TYPOGRAPHY_CLASS).toContain('leading-[1.55]')
    expect(FINDING_REVIEW_QUEUE_CONCLUSION_TYPOGRAPHY_CLASS).toContain('text-justify')
    expect(FINDING_REVIEW_QUEUE_CONCLUSION_TYPOGRAPHY_CLASS).toContain(
      '[text-justify:inter-character]',
    )
    expect(FINDING_REVIEW_QUEUE_CONCLUSION_TYPOGRAPHY_CLASS).toContain('break-normal')
    expect(FINDING_REVIEW_QUEUE_CONCLUSION_TYPOGRAPHY_CLASS).not.toContain('text-last-justify')
    expect(FINDING_REVIEW_QUEUE_CONCLUSION_TYPOGRAPHY_CLASS).not.toContain('break-all')
    expect(FINDING_REVIEW_QUEUE_CONCLUSION_TYPOGRAPHY_CLASS).not.toContain('anywhere')
    expect(findingReviewQueueNotePreviewContentClassName('ignored')).toBe(
      findingReviewQueueNotePreviewContentClassName('pending'),
    )
  })

  it('maps pending severity and review decisions to inset left-edge strokes', () => {
    expect(resolveFindingReviewQueueLeftEdge('pending', 'fail')).toBe('fail')
    expect(resolveFindingReviewQueueLeftEdge('pending', 'need_review')).toBe('need_review')
    expect(resolveFindingReviewQueueLeftEdge('confirmed', 'fail')).toBe('confirmed')
    expect(resolveFindingReviewQueueLeftEdge('ignored', 'fail')).toBeNull()

    expect(findingReviewQueueSeverityBorderClassName('fail')).toContain('border-[#C5CDD6]')
    expect(findingReviewQueueLeftEdgeIndicatorClassName('fail')).toContain('bg-red-500')
    expect(findingReviewQueueLeftEdgeIndicatorClassName('need_review')).toContain('bg-amber-400')
    expect(findingReviewQueueLeftEdgeIndicatorClassName('confirmed')).toContain('bg-slate-400')
    expect(FINDING_REVIEW_QUEUE_LEFT_EDGE_VERTICAL_INSET_CLASS).toContain('top-[8px]')
    expect(FINDING_REVIEW_QUEUE_LEFT_EDGE_CLIP_PATH).toContain('polygon')
    expect(FINDING_REVIEW_QUEUE_LEFT_EDGE_CLIP_PATH).toContain('50%')
    expect(FINDING_REVIEW_QUEUE_LEFT_EDGE_DROP_SHADOW_FILTER).toContain('drop-shadow')
    expect(FINDING_REVIEW_QUEUE_LEFT_EDGE_DROP_SHADOW_FILTER).toContain('1px 0 2px')
    expect(findingReviewQueueCardShellClassName(false, 'fail')).not.toContain('border-l-red-500')
    expect(findingReviewQueueCardShellClassName(false)).toContain('overflow-visible')
  })

  it('styles flagged and note auxiliary state on glyph stroke via button text color', () => {
    expect(findingReviewQueueFlagGlyphClassName(false)).toContain('fill-none')
    expect(findingReviewQueueFlagGlyphClassName(true)).toContain('fill-current')
    expect(findingReviewQueueNoteGlyphClassName(false)).toContain('fill-none')
    expect(findingReviewQueueNoteGlyphClassName(true)).toContain('fill-current')
    expect(findingReviewQueueFlaggedActionButtonClassName()).toContain('text-amber-500')
    expect(findingReviewQueueFlaggedActionButtonClassName()).toContain('hover:text-amber-600')
    expect(findingReviewQueueFlaggedActionButtonClassName()).not.toContain('bg-amber')
    expect(findingReviewQueueNoteActionButtonClassName()).toContain('text-sky-500')
    expect(findingReviewQueueNoteActionButtonClassName()).toContain('hover:text-sky-600')
    expect(findingReviewQueueNoteActionButtonClassName()).not.toContain('bg-sky')
    expect(findingReviewQueueCardShellClassName(false)).toContain('relative')
    expect(findingReviewQueueCardShellClassName(true, null)).toContain('bg-[#F2F6FA]')
  })

  it('keeps confirm and ignore queue actions on neutral button grammar', () => {
    const neutral = findingReviewQueueNeutralActionButtonClassName()
    expect(findingReviewQueueActionButtonClassName('neutral')).toBe(neutral)
    expect(findingReviewQueueActionVisualClassName()).toBe(neutral)
    expect(findingReviewQueueActionUsesSemanticColor(neutral)).toBe(false)
  })

  it('uses one neutral active grammar for detail-panel action helpers', () => {
    const active = findingReviewQueueActionClassName(true)
    const inactive = findingReviewQueueActionClassName(false)

    expect(findingReviewConfirmedActionClassName('confirmed')).toBe(active)
    expect(findingReviewIgnoredActionClassName('ignored')).toBe(active)
    expect(findingReviewMarkedActionClassName(true)).toBe(active)
    expect(findingReviewNoteActionClassName(true)).toBe(active)
    expect(findingReviewConfirmedActionClassName('pending')).toBe('')
    expect(findingReviewNoteActionClassName(false)).toBe('')

    expect(findingReviewQueueActionUsesSemanticColor(active)).toBe(false)
    expect(findingReviewQueueActionUsesSemanticColor(inactive)).toBe(false)
  })

  it('separates inactive hover from business active container treatment', () => {
    const inactive = findingReviewQueueActionInactiveClassName()
    const active = findingReviewQueueActionActiveClassName()
    const focus = findingReviewQueueActionFocusVisibleClassName()

    expect(findingReviewQueueActionInactiveUsesHoverBackground(inactive)).toBe(true)
    expect(inactive).toContain('hover:text-slate-700')
    expect(inactive).toContain('hover:bg-slate-200')
    expect(active).toContain('bg-slate-100')
    expect(active).toContain('border-slate-200')
    expect(inactive).not.toBe(active)
    expect(focus).toContain('focus-visible:ring')
    expect(focus).not.toContain('hover:')
  })

  it('builds presentation with independent decision and marked', () => {
    const presentation = buildFindingPresentation(failFinding, {
      flowRunId: 'document_consistency_qc_test',
      entriesByFindingId: new Map([
        [
          'L001',
          {
            findingId: 'L001',
            decision: 'confirmed',
            marked: true,
            updatedAt: '2026-09-13T00:00:00Z',
          },
        ],
      ]),
    })
    expect(presentation.decision).toBe('confirmed')
    expect(presentation.marked).toBe(true)
  })

  it('replaces entries from payload and removes sparse-deleted findings', () => {
    const current = {
      flowRunId: 'document_consistency_qc_test',
      entriesByFindingId: new Map([
        [
          'N1',
          {
            findingId: 'N1',
            decision: 'pending' as const,
            marked: true,
            note: 'old',
            updatedAt: '2026-09-13T00:00:00Z',
          },
        ],
        [
          'F1',
          {
            findingId: 'F1',
            decision: 'confirmed' as const,
            marked: false,
            updatedAt: '2026-09-13T00:00:00Z',
          },
        ],
      ]),
    }

    const next = applyFindingReviewPayload(current, {
      flowRunId: 'document_consistency_qc_test',
      entriesByFindingId: new Map([
        [
          'N1',
          {
            findingId: 'N1',
            decision: 'pending',
            marked: true,
            updatedAt: '2026-09-13T01:00:00Z',
          },
        ],
      ]),
    })

    expect(next.entriesByFindingId.get('N1')?.note).toBeUndefined()
    expect(next.entriesByFindingId.has('F1')).toBe(false)
  })
})
