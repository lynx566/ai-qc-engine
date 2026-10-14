import { useEffect, useRef, useState } from 'react'

import { adaptExtractBundleToDocumentView } from '@/adapters/extract-document'
import { fetchCandidateScopeDocument } from '@/api/candidate-scope-document'
import { DocumentConsistencyQcApiError } from '@/api/document-consistency-qc-error'
import {
  createInitialSlotDocumentState,
  type SlotDocumentState,
} from '@/lib/slot-document-state'

export type SlotDocumentLoadInput = {
  slotId: string
  docId: string
}

type RequestOwner = {
  loadIdentity: string
  generation: number
  token: symbol
}

type OwnedSlotDocumentState = {
  loadIdentity: string
  generation: number
  state: SlotDocumentState
}

function createLoadingSlotDocumentState(
  slots: readonly SlotDocumentLoadInput[],
): SlotDocumentState {
  return {
    documentsBySlotId: {},
    documentLoadStatusBySlotId: Object.fromEntries(
      slots.map((slot) => [slot.slotId, 'loading'] as const),
    ),
    documentErrorBySlotId: {},
  }
}

export function useSlotDocumentLoader(
  flowRunId: string,
  slots: readonly SlotDocumentLoadInput[],
): SlotDocumentState {
  const slotPlanJson = JSON.stringify(
    slots.map(({ slotId, docId }) => ({ slotId, docId })),
  )
  const loadIdentity = JSON.stringify([flowRunId, slotPlanJson])
  const requestOwnersRef = useRef(new Map<string, symbol>())
  const [ownedState, setOwnedState] = useState<OwnedSlotDocumentState>(() => ({
    loadIdentity,
    generation: 0,
    state:
      slots.length === 0
        ? createInitialSlotDocumentState()
        : createLoadingSlotDocumentState(slots),
  }))
  const loadingState = createLoadingSlotDocumentState(slots)
  let loadGeneration = ownedState.generation
  let stateForRender = ownedState.state

  if (ownedState.loadIdentity !== loadIdentity) {
    loadGeneration += 1
    stateForRender = loadingState
    setOwnedState({
      loadIdentity,
      generation: loadGeneration,
      state: loadingState,
    })
  }

  useEffect(() => {
    const slotPlan = JSON.parse(slotPlanJson) as SlotDocumentLoadInput[]
    const requestOwners = requestOwnersRef.current
    const owners = slotPlan.map((slot) => {
      const owner: RequestOwner = {
        loadIdentity,
        generation: loadGeneration,
        token: Symbol(slot.slotId),
      }
      requestOwners.set(slot.slotId, owner.token)
      return { owner, slot }
    })

    for (const { owner, slot } of owners) {
      void fetchCandidateScopeDocument(flowRunId, slot.slotId)
        .then((bundle) => {
          if (requestOwners.get(slot.slotId) !== owner.token) {
            return
          }

          const document = adaptExtractBundleToDocumentView(bundle)
          if (document.docId !== slot.docId) {
            throw new DocumentConsistencyQcApiError(
              `document doc_id ${document.docId} does not match slot doc_id ${slot.docId}`,
            )
          }

          setOwnedState((previous) => {
            if (
              requestOwners.get(slot.slotId) !== owner.token ||
              previous.generation !== owner.generation
            ) {
              return previous
            }
            return {
              loadIdentity: owner.loadIdentity,
              generation: owner.generation,
              state: {
                ...previous.state,
                documentsBySlotId: {
                  ...previous.state.documentsBySlotId,
                  [slot.slotId]: document,
                },
                documentLoadStatusBySlotId: {
                  ...previous.state.documentLoadStatusBySlotId,
                  [slot.slotId]: 'ready',
                },
              },
            }
          })
        })
        .catch((error) => {
          if (requestOwners.get(slot.slotId) !== owner.token) {
            return
          }

          const message =
            error instanceof DocumentConsistencyQcApiError ? error.message : '文档加载失败'
          setOwnedState((previous) => {
            if (
              requestOwners.get(slot.slotId) !== owner.token ||
              previous.generation !== owner.generation
            ) {
              return previous
            }
            return {
              loadIdentity: owner.loadIdentity,
              generation: owner.generation,
              state: {
                ...previous.state,
                documentLoadStatusBySlotId: {
                  ...previous.state.documentLoadStatusBySlotId,
                  [slot.slotId]: 'error',
                },
                documentErrorBySlotId: {
                  ...previous.state.documentErrorBySlotId,
                  [slot.slotId]: message,
                },
              },
            }
          })
        })
    }

    return () => {
      for (const { owner, slot } of owners) {
        if (requestOwners.get(slot.slotId) === owner.token) {
          requestOwners.delete(slot.slotId)
        }
      }
    }
  }, [flowRunId, loadGeneration, loadIdentity, slotPlanJson])

  return stateForRender
}
