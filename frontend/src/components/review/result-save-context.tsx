import { createContext, useContext, useLayoutEffect, useRef } from 'react'
import type { ResultSaveCoordinator } from '@/lib/result-save-coordinator'

export const ResultSaveContext = createContext<ResultSaveCoordinator | null>(null)

/** Register only a commit callback; each editor retains its draft and save owner. */
export function useResultEditorCommit(commit: () => void | Promise<void>): void {
  const coordinator = useContext(ResultSaveContext)
  const latest = useRef(commit)
  useLayoutEffect(() => { latest.current = commit })
  useLayoutEffect(() => coordinator?.registerEditor(() => latest.current()), [coordinator])
}
