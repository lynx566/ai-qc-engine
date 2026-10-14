// @vitest-environment happy-dom

import { describe, expect, it } from 'vitest'

import {
  isEvidenceMeaningfullyVisibleInScrollViewport,
  shouldShowReturnToEvidenceAnchor,
} from '@/lib/source-evidence-viewport-evidence-visibility'

function scrollViewportWithEvidence(contentTop: number, evidenceHeight: number) {
  const viewport = document.createElement('div')
  Object.defineProperty(viewport, 'clientHeight', {
    configurable: true,
    get: () => 200,
  })
  viewport.style.height = '200px'
  viewport.style.overflow = 'auto'

  const content = document.createElement('div')
  content.style.height = '1200px'
  const spacer = document.createElement('div')
  spacer.style.height = `${contentTop}px`
  const evidence = document.createElement('span')
  evidence.style.display = 'block'
  evidence.style.height = `${evidenceHeight}px`
  Object.defineProperty(evidence, 'offsetHeight', {
    configurable: true,
    get: () => evidenceHeight,
  })
  content.append(spacer, evidence)
  viewport.append(content)

  return { viewport, evidence }
}

describe('source evidence viewport evidence visibility', () => {
  it('hides return action while evidence is meaningfully visible in the scroll viewport', () => {
    const { viewport, evidence } = scrollViewportWithEvidence(140, 40)
    viewport.scrollTop = 0

    expect(isEvidenceMeaningfullyVisibleInScrollViewport(viewport, evidence)).toBe(true)
    expect(shouldShowReturnToEvidenceAnchor(viewport, evidence)).toBe(false)
  })

  it('evaluates visibility per scroll viewport instance (duplicate evidence is independent)', () => {
    const first = scrollViewportWithEvidence(140, 40)
    const second = scrollViewportWithEvidence(140, 40)
    first.viewport.scrollTop = 400
    second.viewport.scrollTop = 0

    expect(shouldShowReturnToEvidenceAnchor(first.viewport, first.evidence)).toBe(true)
    expect(shouldShowReturnToEvidenceAnchor(second.viewport, second.evidence)).toBe(false)
  })

  it('shows return action when evidence has scrolled outside the local viewport', () => {
    const { viewport, evidence } = scrollViewportWithEvidence(140, 40)
    viewport.scrollTop = 400

    expect(shouldShowReturnToEvidenceAnchor(viewport, evidence)).toBe(true)
  })
})
