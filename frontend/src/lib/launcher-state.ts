import type { TaskCatalogEntry } from '@/types/document-consistency-qc'
import type { LauncherSubmitStatus } from '@/types/document-consistency-qc'
import type { TaskRunState } from '@/types/task-run'

export function taskQcSetupRoutePath(taskRunId: string): string {
  return `/task-runs/${taskRunId}/qc-setup`
}

export function taskResultRoutePath(taskRunId: string): string {
  return `/task-runs/${taskRunId}/result`
}

/** Default TaskRun workspace route from Product state (not lifecycle semantics). */
export function resolveTaskRunDefaultRoutePath(
  taskRunId: string,
  state: TaskRunState,
): string {
  if (state.requiresUserAction === true) {
    return taskQcSetupRoutePath(taskRunId)
  }
  if (state.resultAvailable) {
    return taskResultRoutePath(taskRunId)
  }
  return taskQcSetupRoutePath(taskRunId)
}

export function createEmptySlotFiles(
  task: TaskCatalogEntry | null,
): Map<string, File | null> {
  const files = new Map<string, File | null>()
  if (!task) {
    return files
  }
  for (const slot of task.slots) {
    files.set(slot.slotId, null)
  }
  return files
}

export function allRequiredSlotsHaveFiles(
  task: TaskCatalogEntry | null,
  slotFiles: ReadonlyMap<string, File | null>,
): boolean {
  if (!task) {
    return false
  }
  return task.slots.every((slot) => {
    const file = slotFiles.get(slot.slotId)
    return file instanceof File
  })
}

export function canStartLauncher(
  task: TaskCatalogEntry | null,
  slotFiles: ReadonlyMap<string, File | null>,
  submitStatus: LauncherSubmitStatus,
): boolean {
  if (submitStatus === 'submitting') {
    return false
  }
  return allRequiredSlotsHaveFiles(task, slotFiles)
}

export function toSlotFileUploadMap(
  slotFiles: ReadonlyMap<string, File | null>,
): Map<string, File> {
  const uploads = new Map<string, File>()
  for (const [slotId, file] of slotFiles) {
    if (file instanceof File) {
      uploads.set(slotId, file)
    }
  }
  return uploads
}

export function hasUnappliedSlotDraft(
  currentSelected: Set<string>,
  draftSelected: Set<string>,
): boolean {
  if (currentSelected.size !== draftSelected.size) {
    return true
  }
  for (const anchor of currentSelected) {
    if (!draftSelected.has(anchor)) {
      return true
    }
  }
  return false
}
