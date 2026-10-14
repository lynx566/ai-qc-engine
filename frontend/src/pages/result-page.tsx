import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import { fetchTaskRun } from '@/api/task-run'
import { DocumentConsistencyQcApiError } from '@/api/document-consistency-qc-error'
import { TaskResultShell } from '@/components/review/task-result-shell'
import { resolveDocumentConsistencyQcFlowRun } from '@/lib/task-run-flow-contribution'
import { getTaskDocumentTypeLabel } from '@/lib/launcher-presentation'
import {
  resolveNoChildTaskRunMessage,
  resolveResultUnavailableMessage,
  TASK_FETCH_FAILED_USER_MESSAGE,
  TASK_LOADING_USER_MESSAGE,
  TASK_MISSING_ID_USER_MESSAGE,
  TASK_PRESENTATION_ERROR_USER_MESSAGE,
} from '@/lib/task-run-product-state'
import type { TaskRunState } from '@/types/task-run'

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

export function ResultPage() {
  const { taskRunId } = useParams<{ taskRunId: string }>()
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
          const taskDisplayName = taskRun.displayName.trim()
          if (!taskDisplayName) {
            setLoadState({
              ownerTaskRunId: taskRunId,
              status: 'error',
              message: TASK_PRESENTATION_ERROR_USER_MESSAGE,
            })
            return
          }
          if (taskRun.flowRuns.length === 0) {
            setLoadState({
              ownerTaskRunId: taskRunId,
              status: 'error',
              message: resolveNoChildTaskRunMessage(taskRun.state),
            })
            return
          }
          setLoadState({
            ownerTaskRunId: taskRunId,
            status: 'ready',
            taskId: taskRun.taskId,
            taskDisplayName,
            flowRunId: resolveDocumentConsistencyQcFlowRun(taskRun.flowRuns),
            taskState: taskRun.state,
          })
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

  if (!ownedLoadState.taskState.resultAvailable) {
    const message = resolveResultUnavailableMessage(ownedLoadState.taskState)
    return (
      <div className="flex h-svh items-center justify-center p-6 text-sm text-destructive">
        {message}
      </div>
    )
  }

  return (
    <TaskResultShell
      taskRunId={taskRunId}
      taskId={ownedLoadState.taskId}
      taskDisplayName={getTaskDocumentTypeLabel(
        ownedLoadState.taskId,
        ownedLoadState.taskDisplayName,
      )}
      flowRunId={ownedLoadState.flowRunId}
    />
  )
}
