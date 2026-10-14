import { composeDocumentBlockId } from '@/adapters/extract-document'
import {
  buildCandidateHeadingTree,
  flattenCandidateHeadingTree,
} from '@/lib/candidate-scope-heading-tree'
import {
  canonicalizeDraftSelection,
  isCandidateHeadingSelected,
} from '@/lib/candidate-scope-selection'
import type { CandidateHeading } from '@/types/candidate-scope'
import { cn } from '@/lib/utils'

type CandidateScopeViewPanelProps = {
  docId: string
  headings: CandidateHeading[]
  selectedAnchors: Set<string>
  onScrollToBlock: (blockId: string) => void
  focusedBlockId: string | null
}

const rowTextIndentPx = 20

function viewRowClassName(isCandidate: boolean): string {
  return cn(
    'chapter-row box-border flex min-h-[30px] w-full cursor-pointer items-start border-0 px-[10px] py-1 text-left text-[13px] leading-snug transition-[background-color,color]',
    'outline-none! focus:outline-none! focus-visible:outline-none! focus:ring-0 focus-visible:ring-0 active:ring-0',
    isCandidate
      ? 'is-selected rounded-[4px] !bg-[#e8f3ff] font-medium text-[#1f2329]! hover:!bg-[#e8f3ff] hover:text-[#1f2329]!'
      : 'rounded-[4px] bg-transparent font-normal text-[#8c8c8c] hover:bg-[#f7f8fa] hover:text-[#8c8c8c]!',
  )
}

export function CandidateScopeViewPanel({
  docId,
  headings,
  selectedAnchors,
  onScrollToBlock,
}: CandidateScopeViewPanelProps) {
  const headingsByAnchor = new Map(
    headings.map((heading) => [heading.anchorBlockId, heading]),
  )
  const canonicalSelected = canonicalizeDraftSelection(selectedAnchors, headingsByAnchor)
  const tree = buildCandidateHeadingTree(headings)
  const rows = flattenCandidateHeadingTree(tree)

  return (
    <ul className="flex flex-col gap-1">
      {rows.map(({ node, depth }) => {
        const heading = node.heading
        const scrollTargetBlockId = composeDocumentBlockId(docId, heading.anchorBlockId)
        const isCandidate = isCandidateHeadingSelected(
          heading,
          canonicalSelected,
          headingsByAnchor,
        )
        return (
          <li key={heading.anchorBlockId}>
            <button
              type="button"
              data-candidate-selected={isCandidate ? 'true' : undefined}
              className={viewRowClassName(isCandidate)}
              onClick={(event) => {
                onScrollToBlock(scrollTargetBlockId)
                event.currentTarget.blur()
              }}
            >
              <span
                className="min-w-0 flex-1 break-words whitespace-normal"
                style={
                  depth > 0
                    ? { paddingLeft: `${depth * rowTextIndentPx}px` }
                    : undefined
                }
              >
                {heading.title}
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
