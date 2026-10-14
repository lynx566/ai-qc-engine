import { toast } from 'sonner'

import { allRequiredSlotsHaveFiles } from '@/lib/launcher-state'
import type { LauncherSubmitStatus, TaskCatalogEntry } from '@/types/document-consistency-qc'

export const LAUNCHER_UPLOAD_REQUIRED_MESSAGE = '请先上传文件'

export const SLOT_UPLOAD_INVALID_FILE_MESSAGE = '目前仅支持中文 .docx 文件'

export const LAUNCHER_START_HINT_AUTO_DISMISS_MS = 2500

export function showLauncherUploadRequiredHint(): void {
  toast.message(LAUNCHER_UPLOAD_REQUIRED_MESSAGE, {
    duration: LAUNCHER_START_HINT_AUTO_DISMISS_MS,
  })
}

export function showSlotUploadInvalidFileHint(): void {
  toast.message(SLOT_UPLOAD_INVALID_FILE_MESSAGE, {
    duration: LAUNCHER_START_HINT_AUTO_DISMISS_MS,
  })
}

export type LauncherStartAttempt = 'show_upload_required_hint' | 'blocked_submitting' | 'start'

export function resolveLauncherStartAttempt(
  task: TaskCatalogEntry | null,
  slotFiles: ReadonlyMap<string, File | null>,
  submitStatus: LauncherSubmitStatus,
): LauncherStartAttempt {
  if (submitStatus === 'submitting') {
    return 'blocked_submitting'
  }
  if (!allRequiredSlotsHaveFiles(task, slotFiles)) {
    return 'show_upload_required_hint'
  }
  return 'start'
}
