import type { CandidateHeading } from '@/types/candidate-scope'

export function isHeadingPathAncestor(
  ancestor: CandidateHeading,
  descendant: CandidateHeading,
): boolean {
  if (descendant.level <= ancestor.level) {
    return false
  }
  if (descendant.headingPath.length <= ancestor.headingPath.length) {
    return false
  }
  return ancestor.headingPath.every(
    (segment, index) => descendant.headingPath[index] === segment,
  )
}

export function canonicalizeDraftSelection(
  selectedAnchorIds: Set<string>,
  headingsByAnchor: Map<string, CandidateHeading>,
): Set<string> {
  const selectedHeadings = [...selectedAnchorIds]
    .map((anchor) => headingsByAnchor.get(anchor))
    .filter((item): item is CandidateHeading => item !== undefined)

  const drop = new Set<string>()
  for (const ancestor of selectedHeadings) {
    for (const descendant of selectedHeadings) {
      if (ancestor.anchorBlockId === descendant.anchorBlockId) {
        continue
      }
      if (isHeadingPathAncestor(ancestor, descendant)) {
        drop.add(descendant.anchorBlockId)
      }
    }
  }

  const canonical = new Set(selectedAnchorIds)
  for (const anchor of drop) {
    canonical.delete(anchor)
  }
  return canonical
}

export function selectionKeyForJob(
  headings: CandidateHeading[],
  filterJobId: string,
): Set<string> {
  return new Set(
    headings
      .filter((heading) => heading.filterJobId === filterJobId)
      .map((heading) => heading.anchorBlockId),
  )
}

export function isInheritedCandidateSelection(
  heading: CandidateHeading,
  selectedAnchors: Set<string>,
  headingsByAnchor: Map<string, CandidateHeading>,
): boolean {
  for (const anchor of selectedAnchors) {
    if (anchor === heading.anchorBlockId) {
      continue
    }
    const candidate = headingsByAnchor.get(anchor)
    if (!candidate) {
      continue
    }
    if (isHeadingPathAncestor(candidate, heading)) {
      return true
    }
  }
  return false
}

export function isCandidateHeadingSelected(
  heading: CandidateHeading,
  selectedAnchors: Set<string>,
  headingsByAnchor: Map<string, CandidateHeading>,
): boolean {
  const canonical = canonicalizeDraftSelection(selectedAnchors, headingsByAnchor)
  return (
    canonical.has(heading.anchorBlockId) ||
    isInheritedCandidateSelection(heading, canonical, headingsByAnchor)
  )
}
