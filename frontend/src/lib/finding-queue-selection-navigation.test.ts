// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { startFindingQueueSelectionNavigation } from './finding-queue-selection-navigation'

let frames: Map<number, FrameRequestCallback>
let serial: number
let cleanups: Array<() => void>
beforeEach(() => {
  frames = new Map(); serial = 0; cleanups = []
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => { frames.set(++serial, cb); return serial })
  vi.stubGlobal('cancelAnimationFrame', (id: number) => { frames.delete(id) })
})
afterEach(() => { cleanups.forEach(fn => fn()); vi.unstubAllGlobals() })
function frame() { const pending = [...frames.values()]; frames.clear(); pending.forEach(cb => cb(0)) }
function fixture(itemTop = 600) {
  const viewport = document.createElement('div')
  const item = document.createElement('li'); viewport.append(item)
  Object.defineProperties(viewport, { clientHeight: { value: 400 }, scrollHeight: { value: 1200 } })
  viewport.getBoundingClientRect = () => ({ top: 100, height: 400 } as DOMRect)
  item.getBoundingClientRect = () => ({ top: 100 + itemTop - viewport.scrollTop, height: 80 } as DOMRect)
  let requestedTop = 0
  viewport.scrollTo = options => { requestedTop = (options as ScrollToOptions).top ?? 0 }
  const centers: number[] = []
  cleanups.push(startFindingQueueSelectionNavigation(viewport, item, y => centers.push(y)))
  return { viewport, centers, target: () => requestedTop }
}
describe('selection-settled Finding geometry', () => {
  it('does not publish the pre-scroll rect, including idle frames before smooth scrolling starts', () => {
    const f = fixture(); frame(); frame(); frame(); frame()
    expect(f.target()).toBe(500)
    expect(f.centers).toEqual([])
    f.viewport.scrollTop = 200; frame()
    expect(f.centers).toEqual([])
    f.viewport.scrollTop = 500; frame(); frame(); frame(); frame()
    expect(f.centers).toEqual([240])
  })
  it('publishes the actual clamped first item center without substituting 35 percent', () => {
    const f = fixture(20); frame(); frame(); frame(); frame()
    expect(f.target()).toBe(0)
    expect(f.centers).toEqual([160])
  })
  it('uses actual final geometry on scrollend, then ignores manual scrolling', () => {
    const f = fixture()
    f.viewport.scrollTop = 480; f.viewport.dispatchEvent(new Event('scrollend'))
    expect(f.centers).toEqual([260])
    f.viewport.scrollTop = 100; f.viewport.dispatchEvent(new Event('scroll')); frame()
    f.viewport.dispatchEvent(new Event('scrollend'))
    expect(f.centers).toEqual([260])
  })
  it('cancels stale navigation snapshots', () => {
    const f = fixture(); cleanups[0]()
    f.viewport.scrollTop = 500; f.viewport.dispatchEvent(new Event('scrollend')); frame()
    expect(f.centers).toEqual([])
  })
  it('relinquishes an in-flight navigation when the user takes the Queue scroll', () => {
    const f = fixture(); f.viewport.dispatchEvent(new WheelEvent('wheel'))
    f.viewport.scrollTop = 500; f.viewport.dispatchEvent(new Event('scrollend')); frame()
    expect(f.centers).toEqual([])
  })
})
