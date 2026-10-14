import { PanelLeftClose } from 'lucide-react'

import { ResultOutlineSidebar } from '@/components/review/result-outline-sidebar'
import { Button } from '@/components/ui/button'
import type { DocumentOutlineEntry } from '@/lib/document-outline'
import type { InternalResultScopeResult } from '@/types/document-consistency-qc'
import type { FindingReviewStatePayload } from '@/types/finding-review'

type ResultDocumentNavigatorProps = {
  outlineEntries: DocumentOutlineEntry[]
  scopeResultsByOutlineBlockId: Map<string, InternalResultScopeResult[]>
  reviewState: FindingReviewStatePayload | null
  activeOutlineBlockId: string | null
  onSelectHeading: (entry: DocumentOutlineEntry) => void
  onCollapse?: () => void
}

export function ResultDocumentNavigator({
  outlineEntries,
  scopeResultsByOutlineBlockId,
  reviewState,
  activeOutlineBlockId,
  onSelectHeading,
  onCollapse,
}: ResultDocumentNavigatorProps) {
  return (
    <div data-result-document-navigator className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="flex shrink-0 items-center justify-between gap-2 px-4 pt-2 pb-0.5">
        <p className="text-[15px] font-semibold leading-tight text-[#262626]">文档目录</p>
        {onCollapse ? (
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="收起文档目录"
            data-result-document-navigator-collapse="true"
            onClick={onCollapse}
          >
            <PanelLeftClose className="size-4" aria-hidden="true" />
          </Button>
        ) : null}
      </div>
      <ResultOutlineSidebar
        outlineEntries={outlineEntries}
        scopeResultsByOutlineBlockId={scopeResultsByOutlineBlockId}
        reviewState={reviewState}
        activeOutlineBlockId={activeOutlineBlockId}
        onSelectHeading={onSelectHeading}
      />
    </div>
  )
}
