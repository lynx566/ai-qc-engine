import type {
  FindingReviewDecision,
  FindingReviewEntry,
  FindingReviewPatch,
  FindingReviewStatePayload,
} from '@/types/finding-review'

type LegacyFindingReviewState = 'normal' | 'reviewed' | 'flagged'

type RawFindingReviewEntry = {
  finding_id: string
  decision?: FindingReviewDecision
  resolved?: boolean
  marked?: boolean
  review_state?: LegacyFindingReviewState
  note?: string
  updated_at: string
}

type RawFindingReviewPayload = {
  flow_run_id: string
  findings: Record<string, RawFindingReviewEntry>
}

function migrateLegacyReviewState(
  reviewState: LegacyFindingReviewState,
): Pick<FindingReviewEntry, 'decision' | 'marked'> {
  switch (reviewState) {
    case 'reviewed':
      return { decision: 'confirmed', marked: false }
    case 'flagged':
      return { decision: 'pending', marked: true }
    default:
      return { decision: 'pending', marked: false }
  }
}

function decisionFromResolved(resolved: boolean): FindingReviewDecision {
  return resolved ? 'confirmed' : 'pending'
}

function adaptFindingReviewEntry(raw: RawFindingReviewEntry): FindingReviewEntry {
  if (raw.review_state) {
    const legacy = migrateLegacyReviewState(raw.review_state)
    return {
      findingId: raw.finding_id,
      decision: legacy.decision,
      marked: legacy.marked,
      ...(raw.note ? { note: raw.note } : {}),
      updatedAt: raw.updated_at,
    }
  }

  const decision = raw.decision
    ?? decisionFromResolved(raw.resolved ?? false)

  return {
    findingId: raw.finding_id,
    decision,
    marked: raw.marked ?? false,
    ...(raw.note ? { note: raw.note } : {}),
    updatedAt: raw.updated_at,
  }
}

export function adaptFindingReviewState(raw: RawFindingReviewPayload): FindingReviewStatePayload {
  const entriesByFindingId = new Map<string, FindingReviewEntry>()
  for (const entry of Object.values(raw.findings ?? {})) {
    entriesByFindingId.set(entry.finding_id, adaptFindingReviewEntry(entry))
  }
  return {
    flowRunId: raw.flow_run_id,
    entriesByFindingId,
  }
}

export function clearFindingReviewNotePatch(): Pick<FindingReviewPatch, 'note'> {
  return { note: '' }
}

export function buildFindingReviewNoteSavePatch(note: string): Pick<FindingReviewPatch, 'note'> {
  const trimmed = note.trim()
  return { note: trimmed === '' ? '' : trimmed }
}

export function serializeFindingReviewPatch(
  patch: FindingReviewPatch,
): Record<string, boolean | string | null> {
  const body: Record<string, boolean | string | null> = {}
  if (patch.decision !== undefined) {
    body.decision = patch.decision
  }
  if (patch.marked !== undefined) {
    body.marked = patch.marked
  }
  if ('note' in patch) {
    body.note = patch.note ?? ''
  }
  return body
}
