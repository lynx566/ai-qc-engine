type SourceSelectionToolbarProps = {
  top: number
  left: number
  editSaving?: boolean
  commentSaving?: boolean
  onEdit: () => void
  onComment: () => void
}

export function SourceSelectionToolbar({
  top,
  left,
  editSaving = false,
  commentSaving = false,
  onEdit,
  onComment,
}: SourceSelectionToolbarProps) {
  return (
    <div
      className="pointer-events-none fixed z-50"
      style={{ top, left }}
    >
      <div
        data-source-mark-action="true"
        className="pointer-events-auto flex overflow-hidden rounded-md border border-border bg-background shadow-md"
      >
        <button
          type="button"
          disabled={editSaving}
          onClick={onEdit}
          className="px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60 border-r border-border"
        >
          修订
        </button>
        <button
          type="button"
          disabled={commentSaving}
          onClick={onComment}
          className="px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
        >
          批注
        </button>
      </div>
    </div>
  )
}
