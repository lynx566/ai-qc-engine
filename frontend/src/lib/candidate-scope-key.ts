import type { CandidateHeadingKey } from '@/types/candidate-scope'

export function candidateHeadingKey(key: CandidateHeadingKey): string {
  return `${key.docId}:${key.filterJobId}:${key.anchorBlockId}`
}

export function parseCandidateHeadingKey(token: string): CandidateHeadingKey | null {
  const parts = token.split(':')
  if (parts.length < 3) {
    return null
  }
  const docId = parts[0]!
  const filterJobId = parts[1]!
  const anchorBlockId = parts.slice(2).join(':')
  return { docId, filterJobId, anchorBlockId }
}
