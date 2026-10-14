import { describe, expect, it } from 'vitest'

import {
  captureSourceAnnotationCreate,
  captureSourceAnnotationMutation,
  createSourceAnnotationMutationSession,
  mergeSourceAnnotation,
  releaseCapturedSourceAnnotationCreate,
  releaseCapturedSourceAnnotationMutation,
  removeSourceAnnotationFromMap,
  shouldReconcileCapturedSourceAnnotationCreate,
  shouldReconcileCapturedSourceAnnotationMutation,
  shouldReconcileSourceAnnotationMutation,
} from '@/lib/source-annotation-mutation-reconciliation'
import type { SourceAnnotation } from '@/types/source-annotation'

function annotation(
  annotationId: string,
  kind: SourceAnnotation['kind'],
  content = annotationId,
  docId = 'doc-a',
): SourceAnnotation {
  return {
    annotationId,
    kind,
    content,
    anchor: {
      slotId: 'source',
      docId,
      blockId: 'B1',
      sentenceId: 'B1:S1',
    },
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
  }
}

describe('source annotation mutation reconciliation', () => {
  it('serializes update/delete mutations for the same annotation id', () => {
    const session = createSourceAnnotationMutationSession()
    expect(session.tryBeginAnnotationMutation('ann-1')).toBe(true)
    expect(session.tryBeginAnnotationMutation('ann-1')).toBe(false)
    session.endAnnotationMutation('ann-1')
    expect(session.tryBeginAnnotationMutation('ann-1')).toBe(true)
  })

  it('allows independent annotation ids to mutate in parallel', () => {
    const session = createSourceAnnotationMutationSession()
    expect(session.tryBeginAnnotationMutation('ann-1')).toBe(true)
    expect(session.tryBeginAnnotationMutation('ann-2')).toBe(true)
  })

  it('ignores stale responses after flow change, epoch change, or newer request id', () => {
    expect(
      shouldReconcileSourceAnnotationMutation('run-b', 'run-a', 1, 1, 2, 1),
    ).toBe(false)
    expect(
      shouldReconcileSourceAnnotationMutation('run-a', 'run-a', 1, 2, 1, 1),
    ).toBe(false)
    expect(
      shouldReconcileSourceAnnotationMutation('run-a', 'run-a', 1, 1, 3, 1),
    ).toBe(false)
    expect(
      shouldReconcileSourceAnnotationMutation('run-a', 'run-a', 2, 2, 1, 1),
    ).toBe(true)
  })

  it('gives independent creates unique identity without latest-wins reconciliation', () => {
    const session = createSourceAnnotationMutationSession()
    const latestBusyRequestByKey = new Map<string, number>()
    const first = captureSourceAnnotationCreate({
      session,
      latestBusyRequestByKey,
      operationKey: 'create:comment',
      epoch: 1,
      flowRunId: 'run-a',
    })
    const second = captureSourceAnnotationCreate({
      session,
      latestBusyRequestByKey,
      operationKey: 'create:comment',
      epoch: 1,
      flowRunId: 'run-a',
    })

    expect(first.requestId).not.toBe(second.requestId)
    expect(shouldReconcileCapturedSourceAnnotationCreate('run-a', 1, first)).toBe(true)
    expect(shouldReconcileCapturedSourceAnnotationCreate('run-a', 1, second)).toBe(true)
    expect(releaseCapturedSourceAnnotationCreate(first)).toBe(false)
    expect(releaseCapturedSourceAnnotationCreate(second)).toBe(true)
  })

  it('rejects create reconciliation after its captured flow epoch changes', () => {
    const captured = captureSourceAnnotationCreate({
      session: createSourceAnnotationMutationSession(),
      latestBusyRequestByKey: new Map(),
      operationKey: 'create:edit',
      epoch: 1,
      flowRunId: 'run-a',
    })

    expect(shouldReconcileCapturedSourceAnnotationCreate('run-b', 1, captured)).toBe(false)
    expect(shouldReconcileCapturedSourceAnnotationCreate('run-a', 2, captured)).toBe(false)
  })

  it('keeps a captured A→B→A request from ending the later session', () => {
    let activeFlowRunId = 'run-a'
    let activeEpoch = 1
    let session = createSourceAnnotationMutationSession()
    let latestByAnnotationId = new Map<string, number>()

    const stale = captureSourceAnnotationMutation({
      session,
      latestByAnnotationId,
      epoch: activeEpoch,
      flowRunId: activeFlowRunId,
      annotationId: 'ann-1',
    })
    expect(stale).not.toBeNull()

    activeFlowRunId = 'run-b'
    activeEpoch += 1
    session = createSourceAnnotationMutationSession()
    latestByAnnotationId = new Map()

    activeFlowRunId = 'run-a'
    activeEpoch += 1
    session = createSourceAnnotationMutationSession()
    latestByAnnotationId = new Map()

    const next = captureSourceAnnotationMutation({
      session,
      latestByAnnotationId,
      epoch: activeEpoch,
      flowRunId: activeFlowRunId,
      annotationId: 'ann-1',
    })
    expect(next).not.toBeNull()
    expect(next?.requestId).toBe(1)
    expect(stale?.requestId).toBe(1)

    expect(
      shouldReconcileCapturedSourceAnnotationMutation(
        activeFlowRunId,
        activeEpoch,
        stale!,
        'ann-1',
      ),
    ).toBe(false)
    expect(
      shouldReconcileCapturedSourceAnnotationMutation(
        activeFlowRunId,
        activeEpoch,
        next!,
        'ann-1',
      ),
    ).toBe(true)

    expect(releaseCapturedSourceAnnotationMutation(stale!, 'ann-1')).toBe(true)
    expect(session.tryBeginAnnotationMutation('ann-1')).toBe(false)
    expect(releaseCapturedSourceAnnotationMutation(next!, 'ann-1')).toBe(true)
    expect(session.tryBeginAnnotationMutation('ann-1')).toBe(true)
  })

  it('merges one annotation without replacing the rest of the map', () => {
    const current = new Map([
      ['ann-a', annotation('ann-a', 'comment', 'old-a')],
      ['ann-b', annotation('ann-b', 'edit', 'b')],
    ])
    const next = mergeSourceAnnotation(current, annotation('ann-a', 'comment', 'new-a'))

    expect(next.get('ann-a')?.content).toBe('new-a')
    expect(next.get('ann-b')?.content).toBe('b')
    expect(current.get('ann-a')?.content).toBe('old-a')
  })

  it('removes only the deleted annotation from the current map', () => {
    const current = new Map([
      ['ann-a', annotation('ann-a', 'comment', 'updated-a')],
      ['ann-b', annotation('ann-b', 'comment', 'b')],
    ])
    const staleDeleteSnapshot = new Map([
      ['ann-a', annotation('ann-a', 'comment', 'old-a')],
    ])

    const next = removeSourceAnnotationFromMap(current, 'ann-b')
    expect(next.has('ann-b')).toBe(false)
    expect(next.get('ann-a')?.content).toBe('updated-a')
    expect(staleDeleteSnapshot.get('ann-a')?.content).toBe('old-a')
  })

})
