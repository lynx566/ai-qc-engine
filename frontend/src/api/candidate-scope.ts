import { throwDocumentConsistencyQcResponseError } from '@/api/document-consistency-qc-error'
import { adaptCandidateScopeState } from '@/adapters/candidate-scope-view'
import { groupSelectedByJob } from '@/lib/candidate-scope-operations'
import type {
  CandidateScopeFlowState,
  CandidateScopeNextRequest,
  CandidateScopeNextResponse,
  CandidateScopeSlotState,
} from '@/types/candidate-scope'

const API_BASE = '/api/candidate-scope'

export async function fetchCandidateScopeState(
  flowRunId: string,
): Promise<CandidateScopeFlowState> {
  const params = new URLSearchParams({
    flow_run_id: flowRunId,
  })
  const response = await fetch(`${API_BASE}/state?${params.toString()}`)
  if (!response.ok) {
    await throwDocumentConsistencyQcResponseError(response, '候选范围加载失败')
  }
  const payload = await response.json()
  return adaptCandidateScopeState(payload)
}

type ApiNextResponse = {
  status: 'ready'
  flow_id: string
  flow_run_id: string
  flow_status: string
  paused_at_candidate_scope: boolean
  paused_slot_ids: string[]
  completed: boolean
}

function buildSlotCandidateScope(
  slotState: CandidateScopeSlotState,
  selectedAnchors: Set<string>,
) {
  const grouped = groupSelectedByJob(slotState.headings, selectedAnchors)
  const filterJobIds = [...new Set(slotState.headings.map((heading) => heading.filterJobId))].sort()
  return filterJobIds.map((filterJobId) => ({
    filterJobId,
    anchorBlockIds: [...(grouped.get(filterJobId) ?? new Set<string>())].sort(),
  }))
}

export function buildCandidateScopeNextRequest(
  flowState: CandidateScopeFlowState,
  appliedSelectionsBySlotId: ReadonlyMap<string, Set<string>>,
): CandidateScopeNextRequest {
  return {
    flowRunId: flowState.flowRunId,
    slotDecisions: flowState.slots.map((slot) => ({
      slotId: slot.slotId,
      candidateScope: buildSlotCandidateScope(
        slot,
        appliedSelectionsBySlotId.get(slot.slotId) ?? new Set(),
      ),
    })),
  }
}

export function serializeCandidateScopeNextRequest(
  request: CandidateScopeNextRequest,
): Record<string, unknown> {
  return {
    flow_run_id: request.flowRunId,
    slot_decisions: request.slotDecisions.map((decision) => ({
      slot_id: decision.slotId,
      candidate_scope: decision.candidateScope.map((item) => ({
        filter_job_id: item.filterJobId,
        anchor_block_ids: [...item.anchorBlockIds],
      })),
    })),
  }
}

export async function submitCandidateScopeNext(
  request: CandidateScopeNextRequest,
): Promise<CandidateScopeNextResponse> {
  const response = await fetch(`${API_BASE}/next`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(serializeCandidateScopeNextRequest(request)),
  })

  if (!response.ok) {
    await throwDocumentConsistencyQcResponseError(response, '候选范围提交失败')
  }

  const payload = (await response.json()) as ApiNextResponse
  return {
    status: 'ready',
    flowId: payload.flow_id,
    flowRunId: payload.flow_run_id,
    flowStatus: payload.flow_status,
    pausedAtCandidateScope: payload.paused_at_candidate_scope,
    pausedSlotIds: [...payload.paused_slot_ids],
    completed: payload.completed,
  }
}
