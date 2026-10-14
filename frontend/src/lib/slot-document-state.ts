import type { DocumentView } from '@/types/document-review'

export type SlotDocumentLoadStatus = 'loading' | 'ready' | 'error'

export type SlotDocumentState = {
  documentsBySlotId: Record<string, DocumentView>
  documentLoadStatusBySlotId: Record<string, SlotDocumentLoadStatus>
  documentErrorBySlotId: Record<string, string>
}

export function createInitialSlotDocumentState(): SlotDocumentState {
  return {
    documentsBySlotId: {},
    documentLoadStatusBySlotId: {},
    documentErrorBySlotId: {},
  }
}

export function getActiveDocumentLoadStatus(
  state: SlotDocumentState,
  activeSlotId: string | null,
): SlotDocumentLoadStatus | null {
  if (!activeSlotId) {
    return null
  }
  return state.documentLoadStatusBySlotId[activeSlotId] ?? null
}

export function getActiveDocument(
  state: SlotDocumentState,
  activeSlotId: string | null,
): DocumentView | null {
  if (!activeSlotId) {
    return null
  }
  return state.documentsBySlotId[activeSlotId] ?? null
}
