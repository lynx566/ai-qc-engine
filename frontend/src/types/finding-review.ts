export type FindingReviewDecision = 'pending' | 'confirmed' | 'ignored'

export type FindingReviewEntry = {
  findingId: string
  decision: FindingReviewDecision
  marked: boolean
  note?: string
  updatedAt: string
}

export type FindingReviewStatePayload = {
  flowRunId: string
  entriesByFindingId: ReadonlyMap<string, FindingReviewEntry>
}

export type FindingReviewPatch = {
  decision?: FindingReviewDecision
  marked?: boolean
  note?: string | null
}
