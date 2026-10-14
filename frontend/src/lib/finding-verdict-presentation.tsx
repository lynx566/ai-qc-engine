import type { ReactNode } from 'react'
import { CircleX, TriangleAlert, type LucideIcon } from 'lucide-react'

import { cn } from '@/lib/utils'
import type { FindingLabel } from '@/types/document-consistency-qc'

export const FINDING_VERDICT_STROKE_WIDTH = 1.65

export const FINDING_VERDICT_ICON_SIZE_PX = 16

/** Matches `text-sm` title cap height so the icon does not overpower Han glyphs. */
export const FINDING_VERDICT_TITLE_ICON_SIZE_PX = 14

export const FINDING_VERDICT_TITLE_GAP_PX = 4

export const FINDING_VERDICT_TITLE_HANG_INDENT_PX =
  FINDING_VERDICT_TITLE_ICON_SIZE_PX + FINDING_VERDICT_TITLE_GAP_PX

const FINDING_VERDICT_TITLE_ICON_OFFSET_PX = FINDING_VERDICT_TITLE_ICON_SIZE_PX / 2

export const FINDING_VERDICT_LEGEND_ITEMS: ReadonlyArray<{
  label: FindingLabel
  text: string
}> = [
  { label: 'fail', text: '发现错误' },
  { label: 'need_review', text: '可能有误' },
]

export function findingVerdictAccessibleLabel(label: FindingLabel): string {
  return FINDING_VERDICT_LEGEND_ITEMS.find((item) => item.label === label)?.text ?? label
}

export function findingVerdictColorClassName(label: FindingLabel): string {
  switch (label) {
    case 'fail':
      return 'text-red-600'
    case 'need_review':
      return 'text-amber-600'
  }
}

function findingVerdictIconComponent(label: FindingLabel): LucideIcon {
  switch (label) {
    case 'fail':
      return CircleX
    case 'need_review':
      return TriangleAlert
  }
}

type FindingVerdictIconProps = {
  label: FindingLabel
  className?: string
  size?: number
}

export function FindingVerdictIcon({
  label,
  className,
  size = FINDING_VERDICT_ICON_SIZE_PX,
}: FindingVerdictIconProps) {
  const Icon = findingVerdictIconComponent(label)

  return (
    <span
      data-finding-verdict={label}
      className={cn('inline-flex shrink-0 items-center justify-center', className)}
    >
      <Icon
        aria-hidden="true"
        size={size}
        strokeWidth={FINDING_VERDICT_STROKE_WIDTH}
        className={findingVerdictColorClassName(label)}
      />
    </span>
  )
}

type FindingVerdictTitleProps = {
  label: FindingLabel
  className?: string
  children: ReactNode
}

export function FindingVerdictTitle({ label, className, children }: FindingVerdictTitleProps) {
  return (
    <p
      data-finding-verdict-title="true"
      className={cn('relative text-[14px] font-normal leading-snug text-[#262626]', className)}
      style={{ textIndent: FINDING_VERDICT_TITLE_HANG_INDENT_PX }}
    >
      <FindingVerdictIcon
        label={label}
        size={FINDING_VERDICT_TITLE_ICON_SIZE_PX}
        className={`absolute left-0 top-[calc(0.5lh-${FINDING_VERDICT_TITLE_ICON_OFFSET_PX}px)]`}
      />
      {children}
    </p>
  )
}

export function FindingVerdictLegendContent() {
  return (
    <div className="space-y-1">
      {FINDING_VERDICT_LEGEND_ITEMS.map((item) => (
        <div key={item.label} className="flex items-center gap-1.5">
          <FindingVerdictIcon label={item.label} />
          <p>{item.text}</p>
        </div>
      ))}
    </div>
  )
}
