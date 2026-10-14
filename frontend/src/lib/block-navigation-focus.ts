import { cn } from '@/lib/utils'

export type BlockNavigationFocusState = {
  focusedBlockId: string | null
}

export const initialBlockNavigationFocusState: BlockNavigationFocusState = {
  focusedBlockId: null,
}

export const blockNavigationFocusBaseClassName = 'rounded-sm transition-colors duration-300'

export const blockNavigationFocusVisibleClassName = 'bg-zinc-200/60'

export const outlineNavigationActiveClassName = cn(
  blockNavigationFocusBaseClassName,
  blockNavigationFocusVisibleClassName,
)

export const sidebarNavigationActiveClassName =
  'border-l-[3px] border-l-[#2563EB] rounded-none pl-2 text-[#2563EB] font-semibold'

export function blockNavigationFocusClassName(isFocused: boolean): string {
  return cn(
    blockNavigationFocusBaseClassName,
    isFocused && blockNavigationFocusVisibleClassName,
  )
}

export function applyBlockNavigationFocus(blockId: string): BlockNavigationFocusState {
  return {
    focusedBlockId: blockId,
  }
}

export function clearBlockNavigationFocusState(): BlockNavigationFocusState {
  return initialBlockNavigationFocusState
}
