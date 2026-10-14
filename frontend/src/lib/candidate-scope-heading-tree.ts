import type { CandidateHeading } from '@/types/candidate-scope'

export type CandidateHeadingNode = {
  heading: CandidateHeading
  children: CandidateHeadingNode[]
}

export function compareCandidateHeadingDocumentOrder(
  left: CandidateHeading,
  right: CandidateHeading,
): number {
  return left.docOrderIndex - right.docOrderIndex
}

export function buildCandidateHeadingTree(
  headings: CandidateHeading[],
): CandidateHeadingNode[] {
  const sorted = [...headings].sort(compareCandidateHeadingDocumentOrder)
  const roots: CandidateHeadingNode[] = []
  const stack: CandidateHeadingNode[] = []

  for (const heading of sorted) {
    const node: CandidateHeadingNode = { heading, children: [] }

    while (
      stack.length > 0 &&
      stack[stack.length - 1]!.heading.level >= heading.level
    ) {
      stack.pop()
    }

    if (stack.length === 0) {
      roots.push(node)
    } else {
      stack[stack.length - 1]!.children.push(node)
    }

    stack.push(node)
  }

  return roots
}

export function flattenCandidateHeadingTree(
  nodes: CandidateHeadingNode[],
): Array<{ node: CandidateHeadingNode; depth: number }> {
  const flattened: Array<{ node: CandidateHeadingNode; depth: number }> = []

  const visit = (items: CandidateHeadingNode[], depth: number) => {
    for (const node of items) {
      flattened.push({ node, depth })
      visit(node.children, depth + 1)
    }
  }

  visit(nodes, 0)
  return flattened
}
