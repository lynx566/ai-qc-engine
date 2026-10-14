import { describe, expect, it } from 'vitest'

import {
  deriveReviewWorkspaceSelection,
  evidenceLocationKey,
  focusEvidence,
  initialReviewWorkspaceStoredSelection,
  reconcileReviewWorkspaceSelection,
  selectFinding,
} from '@/lib/result-review-selection'
import type {
  InternalResultEvidenceRef,
  InternalResultFinding,
} from '@/types/document-consistency-qc'

const evidenceA: InternalResultEvidenceRef = {
  slotId: 'source',
  docId: 'doc_a',
  blockId: 'C0010',
  sentenceId: 'C0010:S001',
  sentenceAlias: 'T0001',
}

const evidenceB: InternalResultEvidenceRef = {
  slotId: 'source',
  docId: 'doc_a',
  blockId: 'C0020',
  sentenceId: 'C0020:S003',
  sentenceAlias: 'T0002',
}

const evidenceC: InternalResultEvidenceRef = {
  slotId: 'source',
  docId: 'doc_a',
  blockId: 'C0030',
  sentenceId: 'C0030:S002',
  sentenceAlias: 'T0003',
}

const findings: InternalResultFinding[] = [
  {
    findingId: 'F1',
    label: 'fail',
    conclusion: 'First finding',
    comparisonModeId: 'scope_local',
    evidenceRefs: [evidenceA, evidenceB],
  },
  {
    findingId: 'F2',
    label: 'need_review',
    conclusion: 'Second finding',
    comparisonModeId: 'scope_local',
    evidenceRefs: [evidenceC],
  },
  {
    findingId: 'F3',
    label: 'need_review',
    conclusion: 'Finding without evidence',
    comparisonModeId: 'scope_local',
    evidenceRefs: [],
  },
]

describe('evidenceLocationKey', () => {
  it('uses only the canonical locator fields in a collision-safe tuple', () => {
    expect(evidenceLocationKey(evidenceA)).toBe(
      '["source","doc_a","C0010","C0010:S001"]',
    )
    expect(evidenceLocationKey({ ...evidenceA, sentenceAlias: 'T9999' })).toBe(
      evidenceLocationKey(evidenceA),
    )
  })

  it.each([
    ['slotId', { ...evidenceA, slotId: 'comparison' }],
    ['docId', { ...evidenceA, docId: 'doc_b' }],
    ['blockId', { ...evidenceA, blockId: 'C0011' }],
    ['sentenceId', { ...evidenceA, sentenceId: 'C0010:S002' }],
  ])('distinguishes a different %s', (_field, candidate) => {
    expect(evidenceLocationKey(candidate)).not.toBe(evidenceLocationKey(evidenceA))
  })
})

describe('review workspace selection transitions', () => {
  it('preserves a selected Finding and valid focus when refreshed data still contains them', () => {
    const stored = {
      selectedFindingId: 'F1',
      focusedEvidenceLocationKey: evidenceLocationKey(evidenceB),
    }

    expect(reconcileReviewWorkspaceSelection(stored, findings)).toEqual(stored)
  })

  it('clears selection and focus when refreshed data no longer contains the selected Finding', () => {
    expect(reconcileReviewWorkspaceSelection({
      selectedFindingId: 'F1',
      focusedEvidenceLocationKey: evidenceLocationKey(evidenceA),
    }, findings.slice(1))).toEqual(initialReviewWorkspaceStoredSelection)
  })

  it('selects the canonical finding and derives every evidence location in DTO order', () => {
    const stored = selectFinding(initialReviewWorkspaceStoredSelection, findings, 'F1')
    const derived = deriveReviewWorkspaceSelection(findings, stored)

    expect(stored).toEqual({
      selectedFindingId: 'F1',
      focusedEvidenceLocationKey: null,
    })
    expect(derived.selectedFinding).toBe(findings[0])
    expect(derived.selectedEvidenceLocations).toEqual([evidenceA, evidenceB])
    expect(derived.focusedEvidenceLocation).toBeNull()
    expect(derived.focusedSentence).toBeNull()
  })

  it('focuses one evidence location without removing the other selected locations', () => {
    const selected = selectFinding(initialReviewWorkspaceStoredSelection, findings, 'F1')
    const focused = focusEvidence(selected, [evidenceA, evidenceB], evidenceA)
    const derived = deriveReviewWorkspaceSelection(findings, focused)

    expect(focused.selectedFindingId).toBe('F1')
    expect(focused.focusedEvidenceLocationKey).toBe(evidenceLocationKey(evidenceA))
    expect(derived.selectedEvidenceLocations).toEqual([evidenceA, evidenceB])
  })

  it('changes only the focus key when another selected evidence location is focused', () => {
    const selected = selectFinding(initialReviewWorkspaceStoredSelection, findings, 'F1')
    const focusedA = focusEvidence(selected, [evidenceA, evidenceB], evidenceA)
    const focusedB = focusEvidence(focusedA, [evidenceA, evidenceB], evidenceB)

    expect(focusedB).toEqual({
      selectedFindingId: 'F1',
      focusedEvidenceLocationKey: evidenceLocationKey(evidenceB),
    })
  })

  it('switches the evidence set and clears focus that is stale for the new finding', () => {
    const selected = selectFinding(initialReviewWorkspaceStoredSelection, findings, 'F1')
    const focused = focusEvidence(selected, [evidenceA, evidenceB], evidenceA)
    const switched = selectFinding(focused, findings, 'F2')
    const derived = deriveReviewWorkspaceSelection(findings, switched)

    expect(switched).toEqual({
      selectedFindingId: 'F2',
      focusedEvidenceLocationKey: null,
    })
    expect(derived.selectedEvidenceLocations).toEqual([evidenceC])
  })

  it('preserves an existing focus when the newly selected finding contains that location', () => {
    const sharedFinding: InternalResultFinding = {
      ...findings[1]!,
      findingId: 'F4',
      evidenceRefs: [evidenceA, evidenceC],
    }
    const selected = selectFinding(initialReviewWorkspaceStoredSelection, findings, 'F1')
    const focused = focusEvidence(selected, [evidenceA, evidenceB], evidenceA)

    expect(selectFinding(focused, [...findings, sharedFinding], 'F4')).toEqual({
      selectedFindingId: 'F4',
      focusedEvidenceLocationKey: evidenceLocationKey(evidenceA),
    })
  })

  it('normalizes an invalid finding to empty selection and null focus', () => {
    const stored = selectFinding(
      {
        selectedFindingId: 'F1',
        focusedEvidenceLocationKey: evidenceLocationKey(evidenceA),
      },
      findings,
      'missing',
    )
    const derived = deriveReviewWorkspaceSelection(findings, stored)

    expect(stored).toEqual(initialReviewWorkspaceStoredSelection)
    expect(derived.selectedFinding).toBeNull()
    expect(derived.selectedEvidenceLocations).toEqual([])
    expect(derived.focusedEvidenceLocation).toBeNull()
    expect(derived.focusedSentence).toBeNull()
  })

  it('keeps a zero-evidence finding selected without creating focus', () => {
    const stored = selectFinding(initialReviewWorkspaceStoredSelection, findings, 'F3')
    const derived = deriveReviewWorkspaceSelection(findings, stored)

    expect(stored.selectedFindingId).toBe('F3')
    expect(derived.selectedEvidenceLocations).toEqual([])
    expect(derived.focusedEvidenceLocation).toBeNull()
  })

  it('derives reader sentence focus only from the focused canonical location', () => {
    const focused = {
      selectedFindingId: 'F1',
      focusedEvidenceLocationKey: evidenceLocationKey(evidenceB),
    }

    expect(deriveReviewWorkspaceSelection(findings, focused).focusedSentence).toEqual({
      docId: 'doc_a',
      sentenceId: 'C0020:S003',
    })
    expect(
      deriveReviewWorkspaceSelection(findings, {
        ...focused,
        focusedEvidenceLocationKey: '["source","doc_a","C9999","missing"]',
      }).focusedSentence,
    ).toBeNull()
  })
})
