/** Minimum visible evidence height before hiding the return-to-anchor control. */
export const SOURCE_EVIDENCE_VISIBILITY_MIN_VISIBLE_PX = 12

/**
 * Evidence offset from the top of the scroll viewport's content box (stable as scrollTop changes).
 */
export function getEvidenceContentOffsetTopPx(
  scrollViewport: HTMLElement,
  evidenceElement: HTMLElement,
): number {
  let offset = 0
  let element: HTMLElement | null = evidenceElement
  while (element && element !== scrollViewport) {
    offset += element.offsetTop
    element = element.parentElement
  }
  if (element === scrollViewport) {
    return offset
  }

  const viewportRect = scrollViewport.getBoundingClientRect()
  const evidenceRect = evidenceElement.getBoundingClientRect()
  return evidenceRect.top - viewportRect.top + scrollViewport.scrollTop
}

export type EvidenceScrollViewportVisibility = {
  visibleHeightPx: number
  evidenceHeightPx: number
}

function resolveScrollViewportVisibleHeightPx(scrollViewport: HTMLElement): number {
  if (scrollViewport.clientHeight > 0) {
    return scrollViewport.clientHeight
  }
  const viewportRect = scrollViewport.getBoundingClientRect()
  return viewportRect.height > 0 ? viewportRect.height : 0
}

export function measureEvidenceScrollViewportVisibility(
  scrollViewport: HTMLElement,
  evidenceElement: HTMLElement,
): EvidenceScrollViewportVisibility {
  const evidenceHeightPx =
    evidenceElement.offsetHeight || evidenceElement.getBoundingClientRect().height
  const clientHeight = resolveScrollViewportVisibleHeightPx(scrollViewport)
  const contentTop = getEvidenceContentOffsetTopPx(scrollViewport, evidenceElement)
  const topInView = contentTop - scrollViewport.scrollTop
  const bottomInView = topInView + evidenceHeightPx
  const overlapTop = Math.max(topInView, 0)
  const overlapBottom = Math.min(bottomInView, clientHeight)
  const visibleHeightPx = Math.max(0, overlapBottom - overlapTop)
  return { visibleHeightPx, evidenceHeightPx }
}

/**
 * Viewport-local: true when the evidence instance is meaningfully visible inside
 * this scroll viewport (not window / workspace / other instances).
 */
export function isEvidenceMeaningfullyVisibleInScrollViewport(
  scrollViewport: HTMLElement,
  evidenceElement: HTMLElement,
  minVisiblePx = SOURCE_EVIDENCE_VISIBILITY_MIN_VISIBLE_PX,
): boolean {
  const clientHeight = resolveScrollViewportVisibleHeightPx(scrollViewport)
  const { visibleHeightPx, evidenceHeightPx } = measureEvidenceScrollViewportVisibility(
    scrollViewport,
    evidenceElement,
  )
  if (clientHeight <= 0 || evidenceHeightPx <= 0) {
    return true
  }
  const requiredVisible = Math.min(
    evidenceHeightPx,
    Math.max(minVisiblePx, evidenceHeightPx * 0.35),
  )
  return visibleHeightPx >= requiredVisible - 1
}

export function shouldShowReturnToEvidenceAnchor(
  scrollViewport: HTMLElement,
  evidenceElement: HTMLElement,
): boolean {
  return !isEvidenceMeaningfullyVisibleInScrollViewport(scrollViewport, evidenceElement)
}
