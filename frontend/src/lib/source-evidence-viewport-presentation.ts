/** Rendered body lines shown above and below the evidence in the default viewport window. */
export const SOURCE_EVIDENCE_CONTEXT_LINES_ABOVE = 2
export const SOURCE_EVIDENCE_CONTEXT_LINES_BELOW = 2

export const sourceEvidenceViewportScrollAreaClassName =
  'min-h-0 w-full min-w-0 shrink-0'

export const sourceEvidenceViewportChromeAttributes = {
  'data-source-evidence-viewport-chrome': 'true',
} as const

export const sourceEvidenceViewportScrollAttributes = {
  'data-source-evidence-viewport-scroll': 'true',
} as const

export const sourceEvidenceViewportReadableSizingAttributes = {
  'data-source-evidence-viewport-readable-sizing': 'true',
} as const

export function computeTargetViewportBodyHeightPx(
  evidenceRenderedHeightPx: number,
  canonicalBodyLineHeightPx: number,
): number {
  const contextLineCount =
    SOURCE_EVIDENCE_CONTEXT_LINES_ABOVE + SOURCE_EVIDENCE_CONTEXT_LINES_BELOW
  const safeEvidenceHeight = Number.isFinite(evidenceRenderedHeightPx)
    ? Math.max(0, evidenceRenderedHeightPx)
    : 0
  const safeLineHeight = Number.isFinite(canonicalBodyLineHeightPx) &&
    canonicalBodyLineHeightPx > 0
    ? canonicalBodyLineHeightPx
    : safeEvidenceHeight || 1
  return safeEvidenceHeight + contextLineCount * safeLineHeight
}

export function computeInitialEvidenceScrollTopPx(input: {
  evidenceOffsetTopPx: number
  scrollContentHeightPx: number
  viewportBodyHeightPx: number
  canonicalBodyLineHeightPx: number
}): number {
  const contextAbovePx =
    SOURCE_EVIDENCE_CONTEXT_LINES_ABOVE * input.canonicalBodyLineHeightPx
  const desiredScrollTop = input.evidenceOffsetTopPx - contextAbovePx
  const maxScrollTop = Math.max(
    0,
    input.scrollContentHeightPx - input.viewportBodyHeightPx,
  )
  return Math.min(maxScrollTop, Math.max(0, desiredScrollTop))
}

export function measureEvidenceOffsetTopInScrollContent(
  scrollViewport: HTMLElement,
  evidenceElement: HTMLElement,
): number {
  const viewportRect = scrollViewport.getBoundingClientRect()
  const evidenceRect = evidenceElement.getBoundingClientRect()
  return evidenceRect.top - viewportRect.top + scrollViewport.scrollTop
}

/** Resolve canonical source body line-height from layout (no hard-coded px constants). */
export function measureCanonicalBodyLineHeightPx(bodyElement: HTMLElement): number {
  const computed = getComputedStyle(bodyElement)
  const fontSizePx = Number.parseFloat(computed.fontSize)
  const lineHeight = computed.lineHeight
  if (lineHeight === 'normal') {
    const probe = document.createElement('span')
    probe.textContent = 'A'
    probe.style.visibility = 'hidden'
    probe.style.position = 'absolute'
    probe.style.whiteSpace = 'nowrap'
    bodyElement.appendChild(probe)
    const measured = probe.getBoundingClientRect().height
    probe.remove()
    return measured > 0 ? measured : fontSizePx
  }
  const parsed = Number.parseFloat(lineHeight)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fontSizePx
}

export function measureViewportReadableLayout(
  scrollViewport: HTMLElement,
  evidenceElement: HTMLElement,
  bodyElement: HTMLElement,
): {
  canonicalBodyLineHeightPx: number
  evidenceRenderedHeightPx: number
  evidenceOffsetTopPx: number
  scrollContentHeightPx: number
  viewportBodyHeightPx: number
  initialScrollTopPx: number
} {
  const canonicalBodyLineHeightPx = measureCanonicalBodyLineHeightPx(bodyElement)
  const evidenceRenderedHeightPx = evidenceElement.getBoundingClientRect().height
  const viewportBodyHeightPx = computeTargetViewportBodyHeightPx(
    evidenceRenderedHeightPx,
    canonicalBodyLineHeightPx,
  )
  const evidenceOffsetTopPx = measureEvidenceOffsetTopInScrollContent(
    scrollViewport,
    evidenceElement,
  )
  const scrollContentHeightPx = scrollViewport.scrollHeight
  const initialScrollTopPx = computeInitialEvidenceScrollTopPx({
    evidenceOffsetTopPx,
    scrollContentHeightPx,
    viewportBodyHeightPx,
    canonicalBodyLineHeightPx,
  })
  return {
    canonicalBodyLineHeightPx,
    evidenceRenderedHeightPx,
    evidenceOffsetTopPx,
    scrollContentHeightPx,
    viewportBodyHeightPx,
    initialScrollTopPx,
  }
}

/** Scroll one viewport instance back to the readable evidence anchor contract. */
export function scrollViewportToReadableEvidenceAnchor(
  scrollViewport: HTMLElement,
  evidenceElement: HTMLElement,
  bodyElement: HTMLElement,
): number {
  const layout = measureViewportReadableLayout(
    scrollViewport,
    evidenceElement,
    bodyElement,
  )
  scrollViewport.scrollTop = layout.initialScrollTopPx
  return layout.initialScrollTopPx
}
