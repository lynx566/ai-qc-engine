import {
  buildCandidateHeadingTree,
  flattenCandidateHeadingTree,
} from '@/lib/candidate-scope-heading-tree'
import {
  canonicalizeDraftSelection,
  isInheritedCandidateSelection,
} from '@/lib/candidate-scope-selection'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { CandidateHeading } from '@/types/candidate-scope'
import { cn } from '@/lib/utils'

type CandidateScopeEditPanelProps = {
  headings: CandidateHeading[]
  draftSelected: Set<string>
  onToggle: (heading: CandidateHeading, checked: boolean) => void
}

export function CandidateScopeEditPanel({
  headings,
  draftSelected,
  onToggle,
}: CandidateScopeEditPanelProps) {
  const headingsByAnchor = new Map(
    headings.map((heading) => [heading.anchorBlockId, heading]),
  )
  const canonicalDraft = canonicalizeDraftSelection(draftSelected, headingsByAnchor)
  const tree = buildCandidateHeadingTree(headings)
  const rows = flattenCandidateHeadingTree(tree)

  return (
    <div className="flex min-h-0 flex-1 flex-col py-3">
      <p className="mb-2 shrink-0 text-sm font-medium">选择候选章节</p>
      <ScrollArea className="min-h-0 flex-1">
        <ul className="space-y-1 pr-3">
          {rows.map(({ node, depth }) => {
            const heading = node.heading
            const checked = canonicalDraft.has(heading.anchorBlockId)
            const inherited = isInheritedCandidateSelection(
              heading,
              canonicalDraft,
              headingsByAnchor,
            )
            return (
              <li
                key={heading.anchorBlockId}
                className={cn('flex items-start gap-2')}
                style={{ paddingLeft: `${depth * 12}px` }}
              >
                <input
                  id={`candidate-${heading.anchorBlockId}`}
                  type="checkbox"
                  checked={checked}
                  disabled={inherited}
                  onChange={(event) => onToggle(heading, event.target.checked)}
                />
                <label
                  htmlFor={`candidate-${heading.anchorBlockId}`}
                  className={cn(
                    'text-sm leading-snug',
                    inherited && 'text-muted-foreground',
                  )}
                >
                  {heading.title}
                </label>
              </li>
            )
          })}
        </ul>
      </ScrollArea>
    </div>
  )
}
