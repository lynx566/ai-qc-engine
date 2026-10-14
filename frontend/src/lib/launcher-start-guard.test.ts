import { describe, expect, it, vi } from 'vitest'
import { toast } from 'sonner'

import { createEmptySlotFiles } from '@/lib/launcher-state'
import {
  LAUNCHER_START_HINT_AUTO_DISMISS_MS,
  LAUNCHER_UPLOAD_REQUIRED_MESSAGE,
  resolveLauncherStartAttempt,
  showLauncherUploadRequiredHint,
} from '@/lib/launcher-start-guard'

vi.mock('sonner', () => ({
  toast: {
    message: vi.fn(),
  },
}))
import type { TaskCatalogEntry } from '@/types/document-consistency-qc'

const singleSlotTask: TaskCatalogEntry = {
  taskId: 'internal_dsur_qc',
  displayName: 'DSUR 核查',
  description: '单文档核查',
  slots: [
    {
      slotId: 'source',
      expectedDocumentType: 'dsur',
      uploadLabel: '上传 DSUR 文档',
      helpText: '请上传 DSUR 文件',
    },
  ],
}

function makeFile(name: string): File {
  return new File(['content'], name, {
    type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  })
}

describe('launcher start guard', () => {
  it('shows upload hint when required slots are missing', () => {
    const slotFiles = createEmptySlotFiles(singleSlotTask)

    expect(resolveLauncherStartAttempt(singleSlotTask, slotFiles, 'idle')).toBe(
      'show_upload_required_hint',
    )
    expect(LAUNCHER_UPLOAD_REQUIRED_MESSAGE).toBe('请先上传文件')
  })

  it('blocks while submitting', () => {
    const slotFiles = createEmptySlotFiles(singleSlotTask)
    slotFiles.set('source', makeFile('a.docx'))

    expect(resolveLauncherStartAttempt(singleSlotTask, slotFiles, 'submitting')).toBe(
      'blocked_submitting',
    )
  })

  it('starts when all required slots have files', () => {
    const slotFiles = createEmptySlotFiles(singleSlotTask)
    slotFiles.set('source', makeFile('a.docx'))

    expect(resolveLauncherStartAttempt(singleSlotTask, slotFiles, 'idle')).toBe('start')
  })

  it('shows a toast hint with auto-dismiss duration', () => {
    showLauncherUploadRequiredHint()

    expect(toast.message).toHaveBeenCalledWith(LAUNCHER_UPLOAD_REQUIRED_MESSAGE, {
      duration: LAUNCHER_START_HINT_AUTO_DISMISS_MS,
    })
  })
})
