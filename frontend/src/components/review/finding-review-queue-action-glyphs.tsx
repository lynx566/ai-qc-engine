import { Check, EyeClosed, Flag, Pencil } from 'lucide-react'

import {
  FINDING_REVIEW_CONFIRM_CHECK_SIZE_PX,
  FINDING_REVIEW_CONFIRM_CHECK_STROKE_WIDTH,
  findingReviewQueueFlagGlyphClassName,
  findingReviewQueueNoteGlyphClassName,
} from '@/lib/finding-review-presentation'

export function FindingReviewConfirmGlyph() {
  return (
    <Check
      data-finding-review-action-glyph="confirm"
      className="size-4 shrink-0"
      size={FINDING_REVIEW_CONFIRM_CHECK_SIZE_PX}
      strokeWidth={FINDING_REVIEW_CONFIRM_CHECK_STROKE_WIDTH}
      aria-hidden="true"
    />
  )
}

export function FindingReviewIgnoreGlyph() {
  return (
    <EyeClosed
      data-finding-review-action-glyph="ignore"
      className="size-4 shrink-0"
      strokeWidth={2.25}
      aria-hidden="true"
    />
  )
}

export function FindingReviewFlagGlyph({ marked = false }: { marked?: boolean }) {
  return (
    <Flag
      data-finding-review-action-glyph="flag"
      data-finding-queue-flag-glyph={marked ? 'marked' : 'neutral'}
      className={findingReviewQueueFlagGlyphClassName(marked)}
      aria-hidden="true"
    />
  )
}

export function FindingReviewNoteGlyph({ hasNote = false }: { hasNote?: boolean }) {
  return (
    <Pencil
      data-finding-review-action-glyph="note"
      data-finding-queue-note-glyph={hasNote ? 'has-note' : 'neutral'}
      className={findingReviewQueueNoteGlyphClassName(hasNote)}
      aria-hidden="true"
    />
  )
}
