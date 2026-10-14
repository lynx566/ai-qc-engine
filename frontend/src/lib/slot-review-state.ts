import { hasUnappliedSlotDraft } from '@/lib/launcher-state'
import type {
  CandidateScopeFlowState,
  CandidateScopeSlotState,
  SlotReviewState,
} from '@/types/candidate-scope'

export function createInitialSlotReviews(
  flowState: CandidateScopeFlowState,
): Record<string, SlotReviewState> {
  const reviews: Record<string, SlotReviewState> = {}
  for (const slot of flowState.slots) {
    const current = new Set(slot.currentAnchorBlockIds)
    reviews[slot.slotId] = {
      currentSelected: current,
      draftSelected: new Set(current),
      isEditing: false,
    }
  }
  return reviews
}

export function getActiveSlotState(
  flowState: CandidateScopeFlowState,
  activeSlotId: string,
): CandidateScopeSlotState | undefined {
  return flowState.slots.find((slot) => slot.slotId === activeSlotId)
}

export function resolveInitialActiveSlotId(flowState: CandidateScopeFlowState): string {
  const firstSlot = flowState.slots[0]
  if (!firstSlot) {
    throw new Error('candidate scope flow state has no slots')
  }
  return firstSlot.slotId
}

export function anySlotBlocksNext(
  slotReviews: Record<string, SlotReviewState>,
): boolean {
  for (const review of Object.values(slotReviews)) {
    if (review.isEditing) {
      return true
    }
    if (hasUnappliedSlotDraft(review.currentSelected, review.draftSelected)) {
      return true
    }
  }
  return false
}

export function buildAppliedSelectionsBySlotId(
  slotReviews: Record<string, SlotReviewState>,
): Map<string, Set<string>> {
  const applied = new Map<string, Set<string>>()
  for (const [slotId, review] of Object.entries(slotReviews)) {
    applied.set(slotId, new Set(review.currentSelected))
  }
  return applied
}
