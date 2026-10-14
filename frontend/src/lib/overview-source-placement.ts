export type OverviewFindingAnchor = {
  findingId: string
  centerScreenY: number
}

export type OverviewSourcePlacement = {
  mode: 'finding-anchor' | 'top'
  topPx: number
}

/** Overview follows a measured Finding center; it has no independent review axis. */
export function computeOverviewSourcePlacement(input: {
  selectedFindingCenterScreenY: number
  sourceViewportTopScreenY: number
  sourceViewportHeight: number
  sourceStackHeight: number
}): OverviewSourcePlacement {
  const { selectedFindingCenterScreenY, sourceViewportTopScreenY, sourceViewportHeight, sourceStackHeight } = input
  if (!Object.values(input).every(Number.isFinite) || sourceViewportHeight <= 0 || sourceStackHeight <= 0) {
    return { mode: 'top', topPx: 0 }
  }
  const anchorLocalY = selectedFindingCenterScreenY - sourceViewportTopScreenY
  const candidateTop = anchorLocalY - sourceStackHeight / 2
  if (candidateTop >= 0 && candidateTop + sourceStackHeight <= sourceViewportHeight) {
    return { mode: 'finding-anchor', topPx: candidateTop }
  }
  return { mode: 'top', topPx: 0 }
}
