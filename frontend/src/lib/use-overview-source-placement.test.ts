// @vitest-environment happy-dom
import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useOverviewSourcePlacement } from './use-overview-source-placement'
import type { OverviewFindingAnchor } from './overview-source-placement'

let host: HTMLDivElement
let root: ReturnType<typeof createRoot>
let stackHeight: number
let viewportHeight: number
let viewportTop: number
let observers: Array<ResizeObserverCallback>
function Probe({ findingId, anchor, presentationKey = 'flow:doc', enabled = true }: {
  findingId: string; anchor: OverviewFindingAnchor | null; presentationKey?: string; enabled?: boolean
}) {
  const { viewportRef, contentRef, placement } = useOverviewSourcePlacement({ enabled, findingId, anchor, presentationKey })
  return createElement('div', { ref: viewportRef, 'data-status': (placement as { status?: string }).status },
    createElement('div', { ref: contentRef }))
}
function render(findingId: string, anchor: OverviewFindingAnchor | null, presentationKey = 'flow:doc', enabled = true) {
  act(() => root.render(createElement(Probe, { findingId, anchor, presentationKey, enabled })))
}
function status() { return host.firstElementChild!.getAttribute('data-status') }
function remeasure() { act(() => observers.forEach(callback => callback([], {} as ResizeObserver))) }
beforeEach(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  stackHeight = 200; viewportHeight = 700; viewportTop = 100; observers = []
  vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockImplementation(() => viewportHeight)
  vi.spyOn(HTMLElement.prototype, 'scrollHeight', 'get').mockImplementation(() => stackHeight)
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(() => ({ top: viewportTop, width: 500, height: viewportHeight } as DOMRect))
  vi.stubGlobal('ResizeObserver', class { constructor(callback: ResizeObserverCallback) { observers.push(callback) } observe() {} disconnect() {} })
  host = document.createElement('div'); document.body.append(host); root = createRoot(host)
})
afterEach(() => { act(() => root.unmount()); host.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals() })
describe('Overview placement readiness', () => {
  it('preserves same-selection outer scroll when pairing is disabled and reenabled', () => {
    const anchor = { findingId: 'A', centerScreenY: 400 }
    render('A', anchor)
    const viewport = host.firstElementChild as HTMLElement
    render('A', anchor, 'flow:doc', false)
    viewport.scrollTop = 80
    render('A', anchor)
    expect(host.firstElementChild).toBe(viewport)
    expect(viewport.scrollTop).toBe(80)
    expect(status()).toBe('ready')
  })
  it.each([
    { findingId: 'B', presentationKey: 'flow:doc' },
    { findingId: 'A', presentationKey: 'other-flow:doc' },
  ])('resets outer scroll for a changed selection/workspace after pairing resumes: $findingId/$presentationKey', ({ findingId, presentationKey }) => {
    render('A', { findingId: 'A', centerScreenY: 400 })
    const viewport = host.firstElementChild as HTMLElement
    render(findingId, null, presentationKey, false)
    viewport.scrollTop = 80
    render(findingId, { findingId, centerScreenY: 500 }, presentationKey)
    expect(viewport.scrollTop).toBe(0)
    expect(status()).toBe('ready')
  })
  it('rejects a stale Finding anchor and stays pending until the current one arrives', () => {
    render('A', { findingId: 'A', centerScreenY: 400 })
    expect(status()).toBe('ready')
    render('B', { findingId: 'A', centerScreenY: 400 })
    expect(status()).toBe('pending')
    remeasure(); expect(status()).toBe('pending')
    render('B', { findingId: 'B', centerScreenY: 500 })
    expect(status()).toBe('ready')
  })
  it.each([0, NaN, Infinity])('does not decide formal top with invalid viewport height %s', height => {
    viewportHeight = height
    render('A', { findingId: 'A', centerScreenY: 400 })
    expect(status()).toBe('pending')
    viewportHeight = 700; remeasure()
    expect(status()).toBe('ready')
  })
  it('waits for a finite viewport origin instead of revealing an invalid top fallback', () => {
    viewportTop = NaN
    render('A', { findingId: 'A', centerScreenY: 400 })
    expect(status()).toBe('pending')
  })
  it('keeps missing anchor pending across natural geometry measurements', () => {
    render('A', null); remeasure()
    expect(status()).toBe('pending')
  })
})
