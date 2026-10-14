import {
  applyFindingQueueSelectionScroll,
  computeFindingQueueSelectionScrollTop,
  measureSelectedItemTopInScrollContent,
} from './finding-queue-selection-scroll'

/** One selection navigation, never a subscription to ordinary Queue scrolling. */
export function startFindingQueueSelectionNavigation(
  viewport: HTMLElement,
  selectedItem: HTMLElement,
  onSettled: (centerScreenY: number) => void,
): () => void {
  const target = computeFindingQueueSelectionScrollTop(
    viewport.clientHeight, viewport.scrollHeight,
    measureSelectedItemTopInScrollContent(viewport, selectedItem),
    selectedItem.getBoundingClientRect().height,
  )
  let active = true
  let frame = 0
  let previousScrollTop = viewport.scrollTop
  let stableFrames = 0
  const cancel = () => {
    active = false
    cancelAnimationFrame(frame)
    viewport.removeEventListener('scrollend', finish)
    for (const event of ['wheel', 'touchmove', 'pointerdown', 'keydown']) viewport.removeEventListener(event, cancel)
  }
  const finish = () => {
    if (!active) return
    cancel()
    const rect = selectedItem.getBoundingClientRect()
    if (rect.height > 0) onSettled(rect.top + rect.height / 2)
  }
  const sample = () => {
    if (!active) return
    const current = viewport.scrollTop
    stableFrames = Math.abs(current - previousScrollTop) < 0.1 ? stableFrames + 1 : 0
    previousScrollTop = current
    // Do not mistake idle frames before smooth scrolling starts for completion.
    // scrollend also supports a navigation stopped short of the requested target.
    if (Math.abs(current - target) <= 1 && stableFrames >= 3) finish()
    else frame = requestAnimationFrame(sample)
  }
  viewport.addEventListener('scrollend', finish)
  for (const event of ['wheel', 'touchmove', 'pointerdown', 'keydown']) viewport.addEventListener(event, cancel, { passive: true })
  applyFindingQueueSelectionScroll(viewport, target)
  if (active) frame = requestAnimationFrame(sample)
  return cancel
}
