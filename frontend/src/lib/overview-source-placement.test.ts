import { describe, expect, it } from 'vitest'
import { computeOverviewSourcePlacement } from './overview-source-placement'

describe('Overview source follows the settled Finding screen center', () => {
  it.each([
    [400, 100, 700, 200, 'finding-anchor', 200],
    [220, 100, 700, 160, 'finding-anchor', 40],
    [150, 100, 700, 160, 'top', 0],
    [760, 100, 700, 160, 'top', 0],
    [400, 100, 700, 800, 'top', 0],
    [400, 100, 700, 600, 'finding-anchor', 0],
    [400.5, 100, 700, 201, 'finding-anchor', 200],
    [NaN, 100, 700, 200, 'top', 0],
    [400, 100, 0, 200, 'top', 0],
  ] as const)('screen=%s viewportTop=%s height=%s stack=%s', (center, top, height, stack, mode, wantTop) => {
    const placement = computeOverviewSourcePlacement({
      selectedFindingCenterScreenY: center, sourceViewportTopScreenY: top,
      sourceViewportHeight: height, sourceStackHeight: stack,
    })
    expect(placement).toEqual({ mode, topPx: wantTop })
    if (mode === 'finding-anchor') expect(top + placement.topPx + stack / 2).toBe(center)
  })
})
