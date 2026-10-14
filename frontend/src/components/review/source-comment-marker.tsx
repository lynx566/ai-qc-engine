import { MessageSquare } from 'lucide-react'

import { cn } from '@/lib/utils'

export const sourceCommentBadgeClassName =
  'mx-0.5 inline-flex shrink-0 items-center align-middle text-blue-600 hover:text-blue-700'

export const sourceCommentActiveBadgeClassName =
  'rounded-sm bg-blue-100 p-0.5'

export function resolveSourceCommentMarkerClassName(
  isActive: boolean,
  className?: string,
): string {
  return cn(
    sourceCommentBadgeClassName,
    isActive && sourceCommentActiveBadgeClassName,
    className,
  )
}

type SourceCommentMarkerProps = {
  annotationId: string
  isActive?: boolean
  className?: string
  onClick?: (annotationId: string, element: HTMLElement) => void
}

export function SourceCommentMarker({
  annotationId,
  isActive = false,
  className,
  onClick,
}: SourceCommentMarkerProps) {
  return (
    <button
      type="button"
      data-source-comment-icon="true"
      data-source-annotation-id={annotationId}
      data-source-comment-annotation-id={annotationId}
      data-source-ui="true"
      aria-label="查看批注"
      className={resolveSourceCommentMarkerClassName(isActive, className)}
      onPointerDown={(event) => {
        event.stopPropagation()
      }}
      onMouseDown={(event) => {
        event.stopPropagation()
      }}
      onMouseUp={(event) => {
        event.stopPropagation()
      }}
      onClick={(event) => {
        event.stopPropagation()
        event.preventDefault()
        onClick?.(annotationId, event.currentTarget)
      }}
    >
      <MessageSquare className="pointer-events-none h-3.5 w-3.5" strokeWidth={2} aria-hidden="true" />
    </button>
  )
}
