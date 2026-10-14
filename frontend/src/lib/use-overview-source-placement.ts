import { useLayoutEffect, useRef, useState } from 'react'
import { computeOverviewSourcePlacement, type OverviewFindingAnchor, type OverviewSourcePlacement } from './overview-source-placement'

export type OverviewSourcePlacementState =
  | { status: 'pending' }
  | ({ status: 'ready' } & OverviewSourcePlacement)

const pendingPlacement: OverviewSourcePlacementState = { status: 'pending' }
type PlacementMeasurement = {
  findingId: string | null
  presentationKey: string | undefined
  placement: OverviewSourcePlacementState
}

export function useOverviewSourcePlacement({
  enabled, findingId, anchor, presentationKey,
}: {
  enabled: boolean
  findingId: string | null
  anchor: OverviewFindingAnchor | null
  presentationKey?: string
}) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const scrollSelectionRef = useRef<{
    findingId: string | null
    presentationKey: string | undefined
  } | null>(null)
  const [measurement, setMeasurement] = useState<PlacementMeasurement | null>(null)
  useLayoutEffect(() => {
    if (!enabled || !viewportRef.current) return
    const previous = scrollSelectionRef.current
    // Pair visibility changes remeasure the same Source without taking its scroll.
    if (previous?.findingId === findingId && previous.presentationKey === presentationKey) return
    viewportRef.current.scrollTop = 0
    scrollSelectionRef.current = { findingId, presentationKey }
  }, [enabled, findingId, presentationKey])
  useLayoutEffect(() => {
    const viewport = viewportRef.current
    const content = contentRef.current
    if (!enabled || !viewport || !content) return
    // Measure the existing panel's inner content box and the natural stack.
    // Pending only hides presentation; these nodes stay mounted and measurable.
    const measure = () => {
      const rect = viewport.getBoundingClientRect()
      const style = getComputedStyle(viewport)
      const paddingTop = Number.parseFloat(style.paddingTop) || 0
      const paddingBottom = Number.parseFloat(style.paddingBottom) || 0
      const geometry = {
        selectedFindingCenterScreenY: anchor?.centerScreenY ?? NaN,
        sourceViewportTopScreenY: rect.top + viewport.clientTop + paddingTop,
        sourceViewportHeight: viewport.clientHeight - paddingTop - paddingBottom,
        sourceStackHeight: content.scrollHeight,
      }
      const ready = findingId !== null && anchor?.findingId === findingId &&
        Object.values(geometry).every(Number.isFinite) &&
        Number.isFinite(rect.width) && rect.width > 0 &&
        Number.isFinite(rect.height) && rect.height > 0 &&
        geometry.sourceViewportHeight > 0 && geometry.sourceStackHeight > 0
      const next: OverviewSourcePlacementState = ready
        ? { status: 'ready', ...computeOverviewSourcePlacement(geometry) }
        : pendingPlacement
      setMeasurement(previous => {
        if (previous?.findingId === findingId && previous.presentationKey === presentationKey) {
          const current = previous.placement
          if (current.status === 'pending' && next.status === 'pending') return previous
          if (current.status === 'ready' && next.status === 'ready' &&
              current.mode === next.mode && current.topPx === next.topPx) return previous
        }
        return { findingId, presentationKey, placement: next }
      })
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(viewport)
    observer.observe(content)
    return () => observer.disconnect()
  }, [enabled, anchor, findingId, presentationKey])

  // Reject the previous Finding/Result's measurement during render, before the
  // reset/measure layout effects: a new Source must never paint stale placement.
  const current = enabled && findingId !== null && anchor?.findingId === findingId &&
    Number.isFinite(anchor.centerScreenY) && measurement?.findingId === findingId &&
    measurement.presentationKey === presentationKey
  const placement = current ? measurement.placement : pendingPlacement
  return { viewportRef, contentRef, placement }
}
