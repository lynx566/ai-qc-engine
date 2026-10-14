import { DocumentConsistencyQcApiError } from '@/api/document-consistency-qc-error'
import type {
  DocumentConsistencyQcResult,
  FindingLabel,
  InternalResultEvidenceRef,
  InternalResultFinding,
  InternalResultScopeResult,
  ScopeExecutionStatus,
} from '@/types/document-consistency-qc'

type ApiInternalResultEvidenceRef = {
  block_id: string
  sentence_id: string
  slot_id: string
  doc_id: string
  sentence_alias: string
}

type ApiInternalResultFinding = {
  finding_id: string
  label: string
  conclusion: string
  comparison_mode_id: string
  evidence_refs: ApiInternalResultEvidenceRef[]
}

type ApiInternalResultScopeResult = {
  slot_id: string
  doc_id: string
  scope_id: string
  heading_path: string[]
  outline_heading_block_id: string
  semantic_module_id: string
  execution_status: string
  has_successful_check: boolean
}

type ApiDocumentConsistencyQcResult = {
  flow_id: string
  flow_run_id: string
  capability_id: string
  flow_status: string
  comparison_run_status: string | null
  finalization_status: 'completed' | 'completed_with_fallback'
  fallback_comparison_modes: string[]
  findings: ApiInternalResultFinding[]
  scope_results: ApiInternalResultScopeResult[]
}

const FINDING_LABELS = new Set<FindingLabel>(['fail', 'need_review'])
const EXECUTION_STATUSES = new Set<ScopeExecutionStatus>([
  'complete',
  'partial',
  'failed',
  'not_checked',
])

function adaptEvidenceRef(raw: ApiInternalResultEvidenceRef): InternalResultEvidenceRef {
  return {
    blockId: raw.block_id,
    sentenceId: raw.sentence_id,
    slotId: raw.slot_id,
    docId: raw.doc_id,
    sentenceAlias: raw.sentence_alias,
  }
}

function adaptFinding(raw: ApiInternalResultFinding): InternalResultFinding {
  if (!FINDING_LABELS.has(raw.label as FindingLabel)) {
    throw new DocumentConsistencyQcApiError(`unsupported finding label: ${raw.label}`)
  }
  return {
    findingId: raw.finding_id,
    label: raw.label as FindingLabel,
    conclusion: raw.conclusion,
    comparisonModeId: raw.comparison_mode_id,
    evidenceRefs: raw.evidence_refs.map(adaptEvidenceRef),
  }
}

function adaptScopeResult(raw: ApiInternalResultScopeResult): InternalResultScopeResult {
  if (!EXECUTION_STATUSES.has(raw.execution_status as ScopeExecutionStatus)) {
    throw new DocumentConsistencyQcApiError(
      `unsupported scope execution status: ${raw.execution_status}`,
    )
  }
  return {
    slotId: raw.slot_id,
    docId: raw.doc_id,
    scopeId: raw.scope_id,
    headingPath: [...raw.heading_path],
    outlineHeadingBlockId: raw.outline_heading_block_id,
    semanticModuleId: raw.semantic_module_id,
    executionStatus: raw.execution_status as ScopeExecutionStatus,
    hasSuccessfulCheck: raw.has_successful_check,
  }
}

export function adaptDocumentConsistencyQcResult(
  payload: ApiDocumentConsistencyQcResult,
): DocumentConsistencyQcResult {
  return {
    flowId: payload.flow_id,
    flowRunId: payload.flow_run_id,
    capabilityId: payload.capability_id,
    flowStatus: payload.flow_status,
    comparisonRunStatus: payload.comparison_run_status,
    finalizationStatus: payload.finalization_status,
    fallbackComparisonModes: [...payload.fallback_comparison_modes],
    findings: payload.findings.map(adaptFinding),
    scopeResults: payload.scope_results.map(adaptScopeResult),
  }
}
