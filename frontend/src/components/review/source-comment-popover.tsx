import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import { useResultEditorCommit } from '@/components/review/result-save-context'
import { isValidCommentDraft } from '@/lib/source-comment'
import { cn } from '@/lib/utils'

type SourceCommentPopoverProps = {
  mode: 'create' | 'edit'
  top: number
  left: number
  initialContent?: string
  saving?: boolean
  deleting?: boolean
  onCancel: () => void
  onSave: (content: string) => void | Promise<void>
  onDelete?: () => void
}

export function SourceCommentPopover({
  mode,
  top,
  left,
  initialContent = '',
  saving = false,
  deleting = false,
  onCancel,
  onSave,
  onDelete,
}: SourceCommentPopoverProps) {
  const [content, setContent] = useState(initialContent)
  const busy = saving || deleting
  const canSave = isValidCommentDraft(content)
  const saveLabel = '保存'
  useResultEditorCommit(() => {
    if (busy || content === initialContent) return
    if (!canSave) throw new Error('批注内容尚无法保存。')
    return onSave(content)
  })

  return (
    <div
      className="pointer-events-none fixed z-50"
      style={{ top, left }}
    >
      <div
        data-source-comment-popover="true"
        className="pointer-events-auto w-72 rounded-md border border-border bg-background p-3 shadow-lg"
      >
        <label className="mb-1 block text-xs text-muted-foreground">批注</label>
        <textarea
          value={content}
          disabled={busy}
          onChange={(event) => setContent(event.target.value)}
          className={cn(
            'min-h-24 w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm',
            'text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            'disabled:cursor-not-allowed disabled:opacity-60',
          )}
          placeholder=""
        />
        <div className="mt-3 flex flex-wrap justify-end gap-1">
          {mode === 'edit' && onDelete ? (
            <Button
              type="button"
              size="xs"
              variant="ghost"
              disabled={busy}
              className="text-destructive hover:text-destructive"
              onClick={onDelete}
            >
              删除
            </Button>
          ) : null}
          <Button type="button" size="xs" variant="outline" disabled={busy} onClick={onCancel}>
            取消
          </Button>
          <Button
            type="button"
            size="xs"
            disabled={busy || !canSave}
            onClick={() => {
              void Promise.resolve(onSave(content)).catch(() => toast.error('保存失败，请重试。'))
            }}
          >
            {saveLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}
