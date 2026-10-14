import { useCallback, useState } from 'react'

import {
  applyBlockNavigationFocus,
  clearBlockNavigationFocusState,
  initialBlockNavigationFocusState,
  type BlockNavigationFocusState,
} from '@/lib/block-navigation-focus'

export function useBlockNavigationFocus() {
  const [state, setState] = useState<BlockNavigationFocusState>(
    initialBlockNavigationFocusState,
  )

  const clearBlockFocus = useCallback(() => {
    setState(clearBlockNavigationFocusState())
  }, [])

  const focusBlock = useCallback((blockId: string) => {
    setState(applyBlockNavigationFocus(blockId))
  }, [])

  return {
    focusedBlockId: state.focusedBlockId,
    focusBlock,
    clearBlockFocus,
  }
}
