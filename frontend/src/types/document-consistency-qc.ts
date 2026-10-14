export type TaskSlotCatalog = {
  slotId: string
  expectedDocumentType: string | null
  uploadLabel: string
  helpText: string
}

export type TaskCatalogEntry = {
  taskId: string
  displayName: string
  description: string
  slots: TaskSlotCatalog[]
}

export type TaskCatalog = {
  tasks: TaskCatalogEntry[]
}

export type LauncherSubmitStatus = 'idle' | 'submitting' | 'error'

export type FindingLabel = 'fail' | 'need_review'

export type ScopeExecutionStatus = 'complete' | 'partial' | 'failed' | 'not_checked'

export type InternalResultEvidenceRef = {
  blockId: string
  sentenceId: string
  slotId: string
  docId: string
  sentenceAlias: string
}

export type InternalResultFinding = {
  findingId: string
  label: FindingLabel
  conclusion: string
  comparisonModeId: string
  evidenceRefs: InternalResultEvidenceRef[]
}

export type InternalResultScopeResult = {
  slotId: string
  docId: string
  scopeId: string
  headingPath: string[]
  outlineHeadingBlockId: string
  semanticModuleId: string
  executionStatus: ScopeExecutionStatus
  hasSuccessfulCheck: boolean
}

export type DocumentConsistencyQcResult = {
  flowId: string
  flowRunId: string
  capabilityId: string
  flowStatus: string
  comparisonRunStatus: string | null
  finalizationStatus: 'completed' | 'completed_with_fallback'
  fallbackComparisonModes: string[]
  findings: InternalResultFinding[]
  scopeResults: InternalResultScopeResult[]
}
