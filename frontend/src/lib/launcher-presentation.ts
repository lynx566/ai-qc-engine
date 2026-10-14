import type { TaskCatalogEntry } from '@/types/document-consistency-qc'

export const LAUNCHER_PRODUCT_TITLE = '临床研发文档智能质控系统'
export const LAUNCHER_PRODUCT_VERSION = 'v0.1.0'

const TASK_ORDER = [
  'internal_dsur_qc',
  'internal_csr_qc',
  'internal_ib_qc',
  'dsur_updated_ib_qc',
] as const

/** Confirmed product tab labels (UI-only; catalog task_id unchanged). */
const TASK_TAB_LABEL_BY_TASK_ID: Record<string, string> = {
  internal_dsur_qc: '研发期间安全性更新报告（DSUR）',
  internal_csr_qc: '临床研究报告（CSR）',
  internal_ib_qc: '研究者手册（IB）',
  dsur_updated_ib_qc: 'DSUR↔IB',
}

/** Document/task type labels used in QC Setup / Result document identity. */
const TASK_DOCUMENT_TYPE_LABEL_BY_TASK_ID: Record<string, string> = {
  internal_dsur_qc: 'DSUR',
  internal_csr_qc: 'CSR',
  internal_ib_qc: 'IB',
  dsur_updated_ib_qc: 'DSUR ↔ IB',
}

const TASK_INFO_BY_TASK_ID: Record<string, string> = {
  dsur_updated_ib_qc: '文件间质控，适用于IB参考DSUR进行更新的情况',
}

const SLOT_UPLOAD_LABEL_BY_TASK_ID: Record<string, Record<string, string>> = {
  internal_dsur_qc: { source: '点击或拖拽上传DSUR' },
  internal_csr_qc: { source: '点击或拖拽上传CSR' },
  internal_ib_qc: { source: '点击或拖拽上传IB' },
  dsur_updated_ib_qc: {
    source_a: '点击或拖拽上传DSUR',
    source_b: '点击或拖拽上传IB',
  },
}

const PARTICIPANT_FILE_CONTEXT_LABEL_BY_CAPABILITY_ID: Record<
  string,
  Record<string, string>
> = {
  dsur_updated_ib: {
    source_a: 'DSUR',
    source_b: 'IB',
  },
}

export const QC_FUNCTION_SECTION_LABEL = '功能'

export const DOCUMENT_CONSISTENCY_QC_FLOW_ID = 'document_consistency_qc'

export type QcFlowPresentation = {
  displayName: string
  localizedName: string
}

const QC_FLOW_PRESENTATION_BY_FLOW_ID: Record<string, QcFlowPresentation> = {
  [DOCUMENT_CONSISTENCY_QC_FLOW_ID]: {
    displayName: 'Writing Accuracy & Consistency',
    localizedName: '撰写准确性与一致性核查',
  },
}

export function getQcFlowPresentation(flowId: string): QcFlowPresentation {
  const presentation = QC_FLOW_PRESENTATION_BY_FLOW_ID[flowId]
  if (presentation === undefined) {
    throw new Error(`unsupported QC flow identity: ${flowId}`)
  }
  return presentation
}

export const QC_FUNCTION_LABEL = getQcFlowPresentation(
  DOCUMENT_CONSISTENCY_QC_FLOW_ID,
).localizedName

export const QC_FUNCTION_ID = 'writing_accuracy_consistency'

export const CANDIDATE_CHAPTER_HELPER_TEXT =
  'AI将在候选章节中筛选相关内容并进行核查，您可以对候选章节进行调整。'

export const QC_SETUP_PROCEED_LABEL = '进行质控'

export const QC_SETUP_PROCEED_PENDING_LABEL = '正在质控...'

export const QC_SETUP_PROCEED_WAITING_HINT = '预计需要数分钟，请稍后查看结果'

export function getTaskTabLabel(taskId: string, fallbackDisplayName: string): string {
  return TASK_TAB_LABEL_BY_TASK_ID[taskId] ?? fallbackDisplayName
}

export function getTaskDocumentTypeLabel(
  taskId: string,
  fallbackDisplayName: string,
): string {
  return TASK_DOCUMENT_TYPE_LABEL_BY_TASK_ID[taskId] ?? fallbackDisplayName
}

/** Tab info tooltip — only DSUR↔IB had this in the confirmed product UX. */
export function getTaskTabTooltip(taskId: string): string | null {
  return TASK_INFO_BY_TASK_ID[taskId] ?? null
}

export function getSlotUploadLabel(
  taskId: string,
  slotId: string,
  fallbackUploadLabel: string,
): string {
  return SLOT_UPLOAD_LABEL_BY_TASK_ID[taskId]?.[slotId] ?? fallbackUploadLabel
}

export function sortCatalogByTaskOrder(catalog: TaskCatalogEntry[]): TaskCatalogEntry[] {
  const orderIndex = new Map<string, number>(
    TASK_ORDER.map((taskId, index) => [taskId, index]),
  )
  return [...catalog].sort((left, right) => {
    const leftIndex = orderIndex.get(left.taskId) ?? Number.MAX_SAFE_INTEGER
    const rightIndex = orderIndex.get(right.taskId) ?? Number.MAX_SAFE_INTEGER
    return leftIndex - rightIndex
  })
}

/** Flow participant slot label for QC Setup (not Product Task input identity). */
export function getFlowParticipantFileContextLabel(
  capabilityId: string,
  participantSlotId: string,
): string | null {
  return (
    PARTICIPANT_FILE_CONTEXT_LABEL_BY_CAPABILITY_ID[capabilityId]?.[participantSlotId] ??
    null
  )
}
