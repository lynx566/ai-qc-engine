import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'

import { fetchTaskRun } from '@/api/task-run'
import { DocumentConsistencyQcApiError } from '@/api/document-consistency-qc-error'
import { TaskQcSetupShell } from '@/components/qc-setup/task-qc-setup-shell'
import { resolveDocumentConsistencyQcFlowRun } from '@/lib/task-run-flow-contribution'
import { getTaskDocumentTypeLabel } from '@/lib/launcher-presentation'
import {
  resolveNoChildTaskRunMessage,
  TASK_FETCH_FAILED_USER_MESSAGE,
  TASK_LOADING_USER_MESSAGE,
  TASK_MISSING_ID_USER_MESSAGE,
  TASK_PRESENTATION_ERROR_USER_MESSAGE,
} from '@/lib/task-run-product-state'
import type { TaskRunReadModel, TaskRunState } from '@/types/task-run'

type TaskRunLoadState =
  | { ownerTaskRunId: string; status: 'loading' }
  | { ownerTaskRunId: string; status: 'error'; message: string }
  | {
      ownerTaskRunId: string
      status: 'ready'
      taskId: string
      taskDisplayName: string
      flowRunId: string
      taskState: TaskRunState
    }

class TaskRunPresentationError extends Error {}

function resolveReadyTaskRun(
  ownerTaskRunId: string,
  taskRun: TaskRunReadModel,
): Extract<TaskRunLoadState, { status: 'ready' }> {
  const taskDisplayName = taskRun.displayName.trim()
  if (!taskDisplayName) {
    throw new TaskRunPresentationError('task display name missing')
  }
  return {
    ownerTaskRunId,
    status: 'ready',
    taskId: taskRun.taskId,
    taskDisplayName,
    flowRunId: resolveDocumentConsistencyQcFlowRun(taskRun.flowRuns),
    taskState: taskRun.state,
  }
}

export function QcSetupPage() {
  const { taskRunId } = useParams<{ taskRunId: string }>()
  const refreshGenerationRef = useRef(0)
  const [loadState, setLoadState] = useState<TaskRunLoadState>({
    ownerTaskRunId: taskRunId ?? '',
    status: 'loading',
  })

  useEffect(() => {
    if (!taskRunId) {
      return
    }

    let cancelled = false

    void fetchTaskRun(taskRunId)
      .then((taskRun) => {
        if (cancelled) {
          return
        }
        try {
          if (taskRun.flowRuns.length === 0) {
            setLoadState({
              ownerTaskRunId: taskRunId,
              status: 'error',
              message: resolveNoChildTaskRunMessage(taskRun.state),
            })
            return
          }
          setLoadState(resolveReadyTaskRun(taskRunId, taskRun))
        } catch {
          setLoadState({
            ownerTaskRunId: taskRunId,
            status: 'error',
            message: TASK_PRESENTATION_ERROR_USER_MESSAGE,
          })
        }
      })
      .catch((error) => {
        if (cancelled) {
          return
        }
        const message =
          error instanceof DocumentConsistencyQcApiError
            ? error.message
            : TASK_FETCH_FAILED_USER_MESSAGE
        setLoadState({ ownerTaskRunId: taskRunId, status: 'error', message })
      })

    return () => {
      cancelled = true
    }
  }, [taskRunId])

  useLayoutEffect(() => {
    return () => {
      refreshGenerationRef.current += 1
    }
  }, [taskRunId])

  const refreshTaskRunState = useCallback(async (): Promise<TaskRunState | null> => {
    if (!taskRunId) {
      throw new Error('missing task run id')
    }
    const refreshGeneration = ++refreshGenerationRef.current
    const taskRun = await fetchTaskRun(taskRunId)
    if (refreshGeneration !== refreshGenerationRef.current) {
      return null
    }
    const readyState = resolveReadyTaskRun(taskRunId, taskRun)
    setLoadState(readyState)
    return readyState.taskState
  }, [taskRunId])

  if (!taskRunId) {
    return (
      <div className="flex h-svh items-center justify-center p-6 text-sm text-destructive">
        {TASK_MISSING_ID_USER_MESSAGE}
      </div>
    )
  }

  const ownedLoadState =
    loadState.ownerTaskRunId === taskRunId ? loadState : null

  if (ownedLoadState?.status === 'error') {
    return (
      <div className="flex h-svh items-center justify-center p-6 text-sm text-destructive">
        {ownedLoadState.message}
      </div>
    )
  }

  if (ownedLoadState?.status !== 'ready') {
    return (
      <div className="flex h-svh items-center justify-center p-6 text-sm text-muted-foreground">
        {TASK_LOADING_USER_MESSAGE}
      </div>
    )
  }

  return (
    <TaskQcSetupShell
      taskRunId={taskRunId}
      taskId={ownedLoadState.taskId}
      taskDisplayName={getTaskDocumentTypeLabel(
        ownedLoadState.taskId,
        ownedLoadState.taskDisplayName,
      )}
      flowRunId={ownedLoadState.flowRunId}
      taskState={ownedLoadState.taskState}
      refreshTaskRunState={refreshTaskRunState}
    />
  )
}
