import type { SourceAnnotation } from '@/types/source-annotation'

export type SourceAnnotationMutationSession = {
  nextRequestId: () => number
  tryBeginAnnotationMutation: (annotationId: string) => boolean
  endAnnotationMutation: (annotationId: string) => void
}

export function createSourceAnnotationMutationSession(): SourceAnnotationMutationSession {
  let requestCounter = 0
  const pendingAnnotationIds = new Set<string>()

  return {
    nextRequestId() {
      requestCounter += 1
      return requestCounter
    },
    tryBeginAnnotationMutation(annotationId) {
      if (pendingAnnotationIds.has(annotationId)) {
        return false
      }
      pendingAnnotationIds.add(annotationId)
      return true
    },
    endAnnotationMutation(annotationId) {
      pendingAnnotationIds.delete(annotationId)
    },
  }
}

export type CapturedSourceAnnotationMutation = {
  session: SourceAnnotationMutationSession
  latestByAnnotationId: Map<string, number>
  epoch: number
  flowRunId: string
  requestId: number
}

export type CapturedSourceAnnotationCreate = {
  latestBusyRequestByKey: Map<string, number>
  operationKey: string
  epoch: number
  flowRunId: string
  requestId: number
}

export function captureSourceAnnotationCreate(input: {
  session: SourceAnnotationMutationSession
  latestBusyRequestByKey: Map<string, number>
  operationKey: string
  epoch: number
  flowRunId: string
}): CapturedSourceAnnotationCreate {
  const requestId = input.session.nextRequestId()
  input.latestBusyRequestByKey.set(input.operationKey, requestId)
  return {
    latestBusyRequestByKey: input.latestBusyRequestByKey,
    operationKey: input.operationKey,
    epoch: input.epoch,
    flowRunId: input.flowRunId,
    requestId,
  }
}

export function shouldReconcileSourceAnnotationFlow(
  activeFlowRunId: string,
  requestedFlowRunId: string,
  activeEpoch: number,
  requestedEpoch: number,
): boolean {
  return activeFlowRunId === requestedFlowRunId && activeEpoch === requestedEpoch
}

export function shouldReconcileCapturedSourceAnnotationCreate(
  activeFlowRunId: string,
  activeEpoch: number,
  captured: CapturedSourceAnnotationCreate,
): boolean {
  return shouldReconcileSourceAnnotationFlow(
    activeFlowRunId,
    captured.flowRunId,
    activeEpoch,
    captured.epoch,
  )
}

export function releaseCapturedSourceAnnotationCreate(
  captured: CapturedSourceAnnotationCreate,
): boolean {
  if (
    captured.latestBusyRequestByKey.get(captured.operationKey) !== captured.requestId
  ) {
    return false
  }
  captured.latestBusyRequestByKey.delete(captured.operationKey)
  return true
}

export function shouldReconcileSourceAnnotationMutation(
  activeFlowRunId: string,
  requestedFlowRunId: string,
  requestId: number,
  latestRequestId: number,
  activeEpoch: number,
  requestedEpoch: number,
): boolean {
  return (
    shouldReconcileSourceAnnotationFlow(
      activeFlowRunId,
      requestedFlowRunId,
      activeEpoch,
      requestedEpoch,
    ) && requestId === latestRequestId
  )
}

export function captureSourceAnnotationMutation(input: {
  session: SourceAnnotationMutationSession
  latestByAnnotationId: Map<string, number>
  epoch: number
  flowRunId: string
  annotationId: string
}): CapturedSourceAnnotationMutation | null {
  const requestId = input.session.nextRequestId()
  if (!input.session.tryBeginAnnotationMutation(input.annotationId)) {
    return null
  }
  input.latestByAnnotationId.set(input.annotationId, requestId)
  return {
    session: input.session,
    latestByAnnotationId: input.latestByAnnotationId,
    epoch: input.epoch,
    flowRunId: input.flowRunId,
    requestId,
  }
}

export function shouldReconcileCapturedSourceAnnotationMutation(
  activeFlowRunId: string,
  activeEpoch: number,
  captured: CapturedSourceAnnotationMutation,
  annotationId: string,
): boolean {
  return shouldReconcileSourceAnnotationMutation(
    activeFlowRunId,
    captured.flowRunId,
    captured.requestId,
    captured.latestByAnnotationId.get(annotationId) ?? 0,
    activeEpoch,
    captured.epoch,
  )
}

export function releaseCapturedSourceAnnotationMutation(
  captured: CapturedSourceAnnotationMutation,
  annotationId: string,
): boolean {
  captured.session.endAnnotationMutation(annotationId)
  return captured.latestByAnnotationId.get(annotationId) === captured.requestId
}

export function mergeSourceAnnotation(
  current: Map<string, SourceAnnotation>,
  annotation: SourceAnnotation,
): Map<string, SourceAnnotation> {
  const next = new Map(current)
  next.set(annotation.annotationId, annotation)
  return next
}

export function removeSourceAnnotationFromMap(
  current: Map<string, SourceAnnotation>,
  annotationId: string,
): Map<string, SourceAnnotation> {
  if (!current.has(annotationId)) {
    return current
  }
  const next = new Map(current)
  next.delete(annotationId)
  return next
}
