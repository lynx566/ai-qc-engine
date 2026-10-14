// @vitest-environment happy-dom

import { describe, expect, it, vi } from 'vitest'

import {
  computeInitialEvidenceScrollTopPx,
  computeTargetViewportBodyHeightPx,
  measureViewportReadableLayout,
  scrollViewportToReadableEvidenceAnchor,
  SOURCE_EVIDENCE_CONTEXT_LINES_ABOVE,
  SOURCE_EVIDENCE_CONTEXT_LINES_BELOW,
  sourceEvidenceViewportScrollAreaClassName,
} from '@/lib/source-evidence-viewport-presentation'

describe('source evidence viewport readable sizing', () => {
  const lineHeight = 20

  it('sizes viewport body as evidence height plus four rendered context lines', () => {
    expect(computeTargetViewportBodyHeightPx(1 * lineHeight, lineHeight)).toBe(5 * lineHeight)
    expect(computeTargetViewportBodyHeightPx(3 * lineHeight, lineHeight)).toBe(7 * lineHeight)
    expect(computeTargetViewportBodyHeightPx(8 * lineHeight, lineHeight)).toBe(12 * lineHeight)
    expect(SOURCE_EVIDENCE_CONTEXT_LINES_ABOVE).toBe(2)
    expect(SOURCE_EVIDENCE_CONTEXT_LINES_BELOW).toBe(2)
  })

  it('does not depend on paragraph or section length (formula inputs only)', () => {
    const shortParagraphEvidence = 24
    const longParagraphEvidence = 24
    expect(computeTargetViewportBodyHeightPx(shortParagraphEvidence, lineHeight))
      .toBe(computeTargetViewportBodyHeightPx(longParagraphEvidence, lineHeight))
  })

  it('expands viewport body only when evidence rendered height grows', () => {
    const shortEvidence = computeTargetViewportBodyHeightPx(20, lineHeight)
    const longEvidence = computeTargetViewportBodyHeightPx(160, lineHeight)
    expect(longEvidence - shortEvidence).toBe(140)
  })

  it('positions evidence two rendered lines below the viewport top when possible', () => {
    const viewportBodyHeight = 5 * lineHeight
    const evidenceOffsetTop = 10 * lineHeight
    const scrollContentHeight = 30 * lineHeight
    expect(computeInitialEvidenceScrollTopPx({
      evidenceOffsetTopPx: evidenceOffsetTop,
      scrollContentHeightPx: scrollContentHeight,
      viewportBodyHeightPx: viewportBodyHeight,
      canonicalBodyLineHeightPx: lineHeight,
    })).toBe(evidenceOffsetTop - 2 * lineHeight)
  })

  it('clamps to section start when there is not enough content above evidence', () => {
    expect(computeInitialEvidenceScrollTopPx({
      evidenceOffsetTopPx: lineHeight,
      scrollContentHeightPx: 20 * lineHeight,
      viewportBodyHeightPx: 5 * lineHeight,
      canonicalBodyLineHeightPx: lineHeight,
    })).toBe(0)
  })

  it('clamps to section end when there is not enough content below evidence', () => {
    const viewportBodyHeight = 5 * lineHeight
    const scrollContentHeight = 6 * lineHeight
    const evidenceOffsetTop = 4 * lineHeight
    const maxScrollTop = scrollContentHeight - viewportBodyHeight
    expect(computeInitialEvidenceScrollTopPx({
      evidenceOffsetTopPx: evidenceOffsetTop,
      scrollContentHeightPx: scrollContentHeight,
      viewportBodyHeightPx: viewportBodyHeight,
      canonicalBodyLineHeightPx: lineHeight,
    })).toBe(maxScrollTop)
  })

  it('scrollViewportToReadableEvidenceAnchor reuses evidenceOffsetTop minus two line-heights', () => {
    const lineHeight = 20
    const scrollViewport = {
      scrollTop: 0,
      scrollHeight: 30 * lineHeight,
      clientHeight: 5 * lineHeight,
      getBoundingClientRect: () => ({
        top: 0,
        bottom: 5 * lineHeight,
        height: 5 * lineHeight,
        left: 0,
        right: 100,
        width: 100,
        x: 0,
        y: 0,
        toJSON: () => ({}),
      }),
    } as HTMLElement
    const evidenceOffsetTop = 10 * lineHeight
    const evidenceElement = {
      offsetHeight: lineHeight,
      getBoundingClientRect: () => ({
        top: evidenceOffsetTop,
        bottom: evidenceOffsetTop + lineHeight,
        height: lineHeight,
        left: 0,
        right: 100,
        width: 100,
        x: 0,
        y: evidenceOffsetTop,
        toJSON: () => ({}),
      }),
    } as HTMLElement
    const bodyElement = {
      getBoundingClientRect: () => ({ height: 0, top: 0, bottom: 0, left: 0, right: 0, width: 0, x: 0, y: 0, toJSON: () => ({}) }),
    } as HTMLElement

    vi.spyOn(window, 'getComputedStyle').mockReturnValue({
      lineHeight: `${lineHeight}px`,
      fontSize: '14px',
    } as CSSStyleDeclaration)

    const layout = measureViewportReadableLayout(scrollViewport, evidenceElement, bodyElement)
    const nextScrollTop = scrollViewportToReadableEvidenceAnchor(
      scrollViewport,
      evidenceElement,
      bodyElement,
    )
    expect(nextScrollTop).toBe(layout.initialScrollTopPx)
    expect(nextScrollTop).toBe(evidenceOffsetTop - 2 * lineHeight)
    expect(scrollViewport.scrollTop).toBe(nextScrollTop)
  })

  it('uses a dynamic-height scroll shell without fixed tailwind height tokens', () => {
    expect(sourceEvidenceViewportScrollAreaClassName).not.toContain('h-36')
    expect(sourceEvidenceViewportScrollAreaClassName).not.toContain('h-72')
    expect(sourceEvidenceViewportScrollAreaClassName).toContain('min-h-0')
    expect(sourceEvidenceViewportScrollAreaClassName).toContain('min-w-0')
  })
})
