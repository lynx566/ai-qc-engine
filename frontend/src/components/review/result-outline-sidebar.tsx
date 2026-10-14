import { ScrollArea } from '@/components/ui/scroll-area'
import { outlineNavigationActiveClassName } from '@/lib/block-navigation-focus'
import type { DocumentOutlineEntry } from '@/lib/document-outline'
import type { InternalResultScopeResult } from '@/types/document-consistency-qc'
import type { FindingReviewStatePayload } from '@/types/finding-review'
import { cn } from '@/lib/utils'

type ResultOutlineSidebarProps = {
  outlineEntries: DocumentOutlineEntry[]
  scopeResultsByOutlineBlockId: Map<string, InternalResultScopeResult[]>
  reviewState: FindingReviewStatePayload | null
  activeOutlineBlockId: string | null
  onSelectHeading: (entry: DocumentOutlineEntry) => void
}

export function ResultOutlineSidebar({
  outlineEntries,
  activeOutlineBlockId,
  onSelectHeading,
}: ResultOutlineSidebarProps) {
  return (
    <ScrollArea className="min-h-0 flex-1 bg-white" viewportClassName="bg-white">
      <div className="space-y-1 px-2 py-3">
        {outlineEntries.map((entry) => {
          const isActive = entry.blockId === activeOutlineBlockId

          return (
            <button
              key={entry.blockId}
              type="button"
              className={cn(
                'flex w-full flex-col gap-0 rounded-md px-2 py-1 text-left transition-colors',
                isActive ? outlineNavigationActiveClassName : 'hover:bg-muted/70',
              )}
              style={{ paddingLeft: `${(entry.headingLevel - 1) * 12 + 8}px` }}
              onClick={() => {
                onSelectHeading(entry)
              }}
            >
              <span className="text-[14px] font-normal text-[#262626] leading-[1.4]">
                {entry.title}
              </span>
            </button>
          )
        })}
      </div>
    </ScrollArea>
  )
}
