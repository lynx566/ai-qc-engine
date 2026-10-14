import { cn } from '@/lib/utils'

type SourceMarkActionProps = {
  label: '标记' | '取消标记' | '删除标注'
  top: number
  left: number
  disabled?: boolean
  onClick: () => void
}

export function SourceMarkAction({
  label,
  top,
  left,
  disabled = false,
  onClick,
}: SourceMarkActionProps) {
  return (
    <div
      className="pointer-events-none fixed z-50"
      style={{ top, left }}
    >
      <button
        type="button"
        data-source-mark-action="true"
        disabled={disabled}
        onClick={onClick}
        className={cn(
          'pointer-events-auto rounded-md border border-border bg-background px-3 py-1.5 text-sm font-medium text-foreground shadow-md',
          'hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60',
        )}
      >
        {label}
      </button>
    </div>
  )
}
