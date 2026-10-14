import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { toast } from 'sonner'
import { useResultEditorCommit } from '@/components/review/result-save-context'
import { isValidEditDraft } from '@/lib/source-edit'
import { cn } from '@/lib/utils'

type SourceEditPopoverProps = {
  mode: 'create' | 'edit'
  top: number
  left: number
  initialReplacementText?: string
  saving?: boolean
  deleting?: boolean
  onCancel: () => void
  onSave: (replacementText: string) => void | Promise<void>
  onDelete?: () => void
}

export function SourceEditPopover({
  mode,
  top,
  left,
  initialReplacementText = '',
  saving = false,
  deleting = false,
  onCancel,
  onSave,
  onDelete,
}: SourceEditPopoverProps) {
  const [replacementText, setReplacementText] = useState(initialReplacementText)
  const busy = saving || deleting
  const canSave = isValidEditDraft(replacementText)
  const saveLabel = '保存'
  useResultEditorCommit(() => {
    if (busy || replacementText === initialReplacementText) return
    if (!canSave) throw new Error('修订内容尚无法保存。')
    return onSave(replacementText)
  })

  return (
    <div
      className="pointer-events-none fixed z-50"
      style={{ top, left }}
    >
      <div
        data-source-edit-popover="true"
        className="pointer-events-auto w-72 rounded-md border border-border bg-background p-3 shadow-lg"
      >
        <label className="mb-1 block text-xs text-muted-foreground">修订为</label>
        <input
          type="text"
          value={replacementText}
          disabled={busy}
          onChange={(event) => setReplacementText(event.target.value)}
          className={cn(
            'w-full rounded-md border border-input bg-background px-3 py-2 text-sm',
            'text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            'disabled:cursor-not-allowed disabled:opacity-60',
          )}
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
              void Promise.resolve(onSave(replacementText)).catch(() => toast.error('保存失败，请重试。'))
            }}
          >
            {saveLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}
