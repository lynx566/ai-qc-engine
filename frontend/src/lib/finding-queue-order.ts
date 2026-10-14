import type { FindingLabel, InternalResultFinding } from '@/types/document-consistency-qc'

const QUEUE_LABEL_RANK: Record<FindingLabel, number> = {
  fail: 0,
  need_review: 1,
}

/** Presentation order for the Result Finding Queue (fail before need_review). */
export function deriveQueueFindings(
  findings: readonly InternalResultFinding[],
): InternalResultFinding[] {
  const indexed = findings.map((finding, index) => ({ finding, index }))
  indexed.sort((left, right) => {
    const rankDelta =
      QUEUE_LABEL_RANK[left.finding.label] - QUEUE_LABEL_RANK[right.finding.label]
    if (rankDelta !== 0) {
      return rankDelta
    }
    return left.index - right.index
  })
  return indexed.map((entry) => entry.finding)
}

export function resolveQueueFindingIndex(
  queueFindings: readonly InternalResultFinding[],
  findingId: string | null,
): number {
  if (findingId === null) {
    return -1
  }
  return queueFindings.findIndex((finding) => finding.findingId === findingId)
}

export function resolveDefaultQueueFindingId(
  queueFindings: readonly InternalResultFinding[],
): string | null {
  return queueFindings[0]?.findingId ?? null
}

/** Adjacent queue item without wrapping at list boundaries. */
export function resolveAdjacentQueueFindingId(
  queueFindings: readonly InternalResultFinding[],
  findingId: string | null,
  direction: 'next' | 'previous',
): string | null {
  const currentIndex = resolveQueueFindingIndex(queueFindings, findingId)
  if (currentIndex < 0) {
    return null
  }
  const nextIndex = direction === 'next' ? currentIndex + 1 : currentIndex - 1
  if (nextIndex < 0 || nextIndex >= queueFindings.length) {
    return null
  }
  return queueFindings[nextIndex]?.findingId ?? null
}
