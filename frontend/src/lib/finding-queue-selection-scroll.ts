/** Overview queue placement retains its existing viewport target. */
export const FINDING_QUEUE_SELECTION_ANCHOR_RATIO = 0.35

export function clampFindingQueueScrollTop(
  scrollTop: number,
  scrollHeight: number,
  clientHeight: number,
): number {
  const maxScrollTop = Math.max(0, scrollHeight - clientHeight)
  return Math.min(Math.max(0, scrollTop), maxScrollTop)
}

/** Scroll so selected Finding item center aligns to Review Anchor Y in the queue viewport. */
export function computeFindingQueueSelectionScrollTop(
  viewportClientHeight: number,
  scrollHeight: number,
  selectedItemTopInScrollContent: number,
  selectedItemHeightPx: number,
  anchorViewportRatio = FINDING_QUEUE_SELECTION_ANCHOR_RATIO,
): number {
  const reviewAnchorY = viewportClientHeight * anchorViewportRatio
  const targetScrollTop =
    selectedItemTopInScrollContent + selectedItemHeightPx / 2 - reviewAnchorY
  return clampFindingQueueScrollTop(targetScrollTop, scrollHeight, viewportClientHeight)
}

export function measureSelectedItemTopInScrollContent(
  viewport: HTMLElement,
  selectedItem: HTMLElement,
): number {
  const viewportRect = viewport.getBoundingClientRect()
  const itemRect = selectedItem.getBoundingClientRect()
  return viewport.scrollTop + (itemRect.top - viewportRect.top)
}

export function resolveFindingQueueScrollViewport(
  queueRoot: HTMLElement,
): HTMLElement | null {
  return queueRoot.closest('[data-slot="scroll-area-viewport"]')
}

export function applyFindingQueueSelectionScroll(
  viewport: HTMLElement,
  targetScrollTop: number,
  behavior: ScrollBehavior = 'smooth',
): void {
  if (typeof viewport.scrollTo === 'function') {
    viewport.scrollTo({ top: targetScrollTop, behavior })
    return
  }
  viewport.scrollTop = targetScrollTop
}

export function anchorSelectedFindingInQueueViewport(
  viewport: HTMLElement,
  selectedItem: HTMLElement,
  behavior: ScrollBehavior = 'smooth',
): void {
  const selectedItemTop = measureSelectedItemTopInScrollContent(viewport, selectedItem)
  const selectedItemHeight = selectedItem.getBoundingClientRect().height
  const targetScrollTop = computeFindingQueueSelectionScrollTop(
    viewport.clientHeight,
    viewport.scrollHeight,
    selectedItemTop,
    selectedItemHeight,
  )
  applyFindingQueueSelectionScroll(viewport, targetScrollTop, behavior)
}
