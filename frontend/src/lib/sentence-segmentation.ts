import type { SentenceView } from '@/types/document-review'

export type SentenceTextGapSegment = {
  kind: 'gap'
  text: string
}

export type SentenceTextSentenceSegment = {
  kind: 'sentence'
  sentenceId: string
  text: string
}

export type SentenceTextSegment = SentenceTextGapSegment | SentenceTextSentenceSegment

export type SentenceTextSegmentation =
  | { available: true; segments: SentenceTextSegment[] }
  | { available: false }

/**
 * Deterministic forward segmentation of block display text into ordered sentence
 * spans plus preserved gap text.
 *
 * Contract: each `sentence.rawText` is an ordered exact substring of the Extract
 * block `raw_text` (which equals `displayText` for paragraph blocks). Forward
 * `indexOf` with a monotonic cursor is structural matching — not fuzzy search.
 */
export function segmentSentenceText(
  displayText: string,
  sentences: readonly Pick<SentenceView, 'sentenceId' | 'rawText'>[],
): SentenceTextSegmentation {
  if (sentences.length === 0) {
    return { available: false }
  }

  let cursor = 0
  const segments: SentenceTextSegment[] = []

  for (const sentence of sentences) {
    const rawText = sentence.rawText
    if (rawText.length === 0) {
      return { available: false }
    }

    const index = displayText.indexOf(rawText, cursor)
    if (index < 0) {
      return { available: false }
    }

    if (index > cursor) {
      segments.push({ kind: 'gap', text: displayText.slice(cursor, index) })
    }

    segments.push({
      kind: 'sentence',
      sentenceId: sentence.sentenceId,
      text: rawText,
    })
    cursor = index + rawText.length
  }

  if (cursor < displayText.length) {
    segments.push({ kind: 'gap', text: displayText.slice(cursor) })
  }

  return { available: true, segments }
}

/**
 * Reconstruct visible text from a successful segmentation (for fidelity checks).
 */
export function renderSegmentedTextContent(segments: readonly SentenceTextSegment[]): string {
  return segments.map((segment) => segment.text).join('')
}
