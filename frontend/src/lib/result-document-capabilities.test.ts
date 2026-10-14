import { describe, expect, it } from 'vitest'

import { deriveResultDocumentCapabilities } from '@/lib/result-document-capabilities'

describe('deriveResultDocumentCapabilities', () => {
  it.each([
    {
      renderer: 'canonical' as const,
      expected: { directory: true, annotationContext: true, annotationNavigator: true },
    },
    {
      renderer: 'evidence_viewports' as const,
      expected: { directory: false, annotationContext: true, annotationNavigator: false },
    },
  ])('derives $renderer toolbar capabilities', ({ renderer, expected }) => {
    expect(deriveResultDocumentCapabilities(renderer)).toEqual(expected)
  })
})
