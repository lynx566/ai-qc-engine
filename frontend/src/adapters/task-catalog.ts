import type { TaskCatalog, TaskCatalogEntry, TaskSlotCatalog } from '@/types/document-consistency-qc'

type ApiTaskSlotCatalog = {
  slot_id: string
  expected_document_type: string | null
  upload_label: string
  help_text: string
}

type ApiTaskCatalogEntry = {
  task_id: string
  display_name: string
  description: string
  slots: ApiTaskSlotCatalog[]
}

type ApiTaskCatalogResponse = {
  tasks: ApiTaskCatalogEntry[]
}

function adaptTaskSlot(raw: ApiTaskSlotCatalog): TaskSlotCatalog {
  return {
    slotId: raw.slot_id,
    expectedDocumentType: raw.expected_document_type,
    uploadLabel: raw.upload_label,
    helpText: raw.help_text,
  }
}

function adaptTaskEntry(raw: ApiTaskCatalogEntry): TaskCatalogEntry {
  return {
    taskId: raw.task_id,
    displayName: raw.display_name,
    description: raw.description,
    slots: raw.slots.map(adaptTaskSlot),
  }
}

export function adaptTaskCatalog(payload: ApiTaskCatalogResponse): TaskCatalog {
  return {
    tasks: payload.tasks.map(adaptTaskEntry),
  }
}
