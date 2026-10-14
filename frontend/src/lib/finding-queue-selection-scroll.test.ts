import { describe, expect, it } from 'vitest'

import {
  clampFindingQueueScrollTop,
  computeFindingQueueSelectionScrollTop,
} from '@/lib/finding-queue-selection-scroll'

describe('finding-queue selection scroll', () => {
  it('anchors selected finding center to the review anchor axis in the queue viewport', () => {
    const viewportHeight = 300
    const scrollHeight = 1200
    const itemTop = 450
    const itemHeight = 100

    expect(
      computeFindingQueueSelectionScrollTop(
        viewportHeight,
        scrollHeight,
        itemTop,
        itemHeight,
      ),
    ).toBe(395)
  })

  it('clamps to the top when the anchored position is negative', () => {
    expect(
      computeFindingQueueSelectionScrollTop(300, 900, 60, 40),
    ).toBe(0)
  })

  it('clamps to max scrollTop near the bottom of the queue', () => {
    const viewportHeight = 300
    const scrollHeight = 1000
    const maxScrollTop = scrollHeight - viewportHeight

    expect(
      computeFindingQueueSelectionScrollTop(viewportHeight, scrollHeight, 950, 80),
    ).toBe(maxScrollTop)
  })

  it('clamps scrollTop to the legal range', () => {
    expect(clampFindingQueueScrollTop(-20, 500, 200)).toBe(0)
    expect(clampFindingQueueScrollTop(900, 500, 200)).toBe(300)
    expect(clampFindingQueueScrollTop(120, 500, 200)).toBe(120)
  })
})
