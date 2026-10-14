import type { CandidateHeading } from '@/types/candidate-scope'

export function groupSelectedByJob(
  headings: CandidateHeading[],
  selectedAnchors: Set<string>,
): Map<string, Set<string>> {
  const grouped = new Map<string, Set<string>>()
  for (const heading of headings) {
    if (!selectedAnchors.has(heading.anchorBlockId)) {
      continue
    }
    const existing = grouped.get(heading.filterJobId) ?? new Set<string>()
    existing.add(heading.anchorBlockId)
    grouped.set(heading.filterJobId, existing)
  }
  return grouped
}
