import { describe, expect, it } from 'vitest'

import {
  resultEvidenceHighlightSurfaceClassName,
  resultFindingSelectedSurfaceClassName,
} from '@/lib/result-review-visual-tokens'
import {
  findingEvidenceHighlightSurfaceClassName,
  findingTargetSentenceClassName,
  focusedFindingTargetSentenceClassName,
  isSentenceNavigationFocused,
  sentenceNavigationFocusClassName,
  sentenceNavigationFocusUpdate,
} from '@/lib/sentence-navigation-focus'

describe('sentenceNavigationFocusClassName', () => {
  it('uses a light blue whole-sentence background without extra focus accents', () => {
    expect(sentenceNavigationFocusClassName).toContain(resultEvidenceHighlightSurfaceClassName)
    expect(sentenceNavigationFocusClassName).toContain('box-decoration-clone')
    expect(sentenceNavigationFocusClassName).not.toContain('bg-zinc')
    expect(sentenceNavigationFocusClassName).not.toContain('ring')
    expect(sentenceNavigationFocusClassName).not.toContain('border')
    expect(sentenceNavigationFocusClassName).not.toContain('underline')
  })
})

describe('finding target sentence chrome', () => {
  it('uses the same muted blue family with evidence stronger than selected card', () => {
    expect(findingEvidenceHighlightSurfaceClassName).toBe(resultEvidenceHighlightSurfaceClassName)
    expect(findingTargetSentenceClassName).toContain(findingEvidenceHighlightSurfaceClassName)
    expect(findingTargetSentenceClassName).not.toContain('ring-')
    expect(findingTargetSentenceClassName).not.toContain('rounded')
    expect(sentenceNavigationFocusClassName).not.toContain('rounded')
    expect(focusedFindingTargetSentenceClassName).toContain(resultEvidenceHighlightSurfaceClassName)
    expect(focusedFindingTargetSentenceClassName).not.toContain(resultFindingSelectedSurfaceClassName)
    expect(focusedFindingTargetSentenceClassName).not.toContain('ring-')
    expect(findingTargetSentenceClassName).not.toContain('amber')
  })
})

describe('sentenceNavigationFocusUpdate', () => {
  it('sets focus on sentence navigation success', () => {
    expect(
      sentenceNavigationFocusUpdate('sentence', {
        docId: 'doc_test',
        blockId: 'doc_test:C0002',
        sentenceId: 'C0002:S001',
      }),
    ).toEqual({
      docId: 'doc_test',
      sentenceId: 'C0002:S001',
    })
  })

  it('clears focus on block fallback', () => {
    expect(
      sentenceNavigationFocusUpdate('block', {
        docId: 'doc_test',
        blockId: 'doc_test:T0001',
        sentenceId: 'T0001:S001',
      }),
    ).toBeNull()
  })
})

describe('isSentenceNavigationFocused', () => {
  it('matches docId and sentenceId together', () => {
    const focused = { docId: 'doc_test', sentenceId: 'C0002:S001' }
    expect(isSentenceNavigationFocused(focused, 'doc_test', 'C0002:S001')).toBe(true)
    expect(isSentenceNavigationFocused(focused, 'doc_other', 'C0002:S001')).toBe(false)
    expect(isSentenceNavigationFocused(focused, 'doc_test', 'C0002:S002')).toBe(false)
  })
})
