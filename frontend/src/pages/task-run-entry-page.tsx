import { useEffect, useState } from 'react'
import { Navigate, useParams } from 'react-router-dom'

import { fetchTaskRun } from '@/api/task-run'
import { DocumentConsistencyQcApiError } from '@/api/document-consistency-qc-error'
import { resolveTaskRunDefaultRoutePath } from '@/lib/launcher-state'
import {
  TASK_FETCH_FAILED_USER_MESSAGE,
  TASK_LOADING_USER_MESSAGE,
  TASK_MISSING_ID_USER_MESSAGE,
} from '@/lib/task-run-product-state'

export function TaskRunEntryPage() {
  const { taskRunId } = useParams<{ taskRunId: string }>()
  const [targetPath, setTargetPath] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

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
        setTargetPath(resolveTaskRunDefaultRoutePath(taskRunId, taskRun.state))
      })
      .catch((error) => {
        if (cancelled) {
          return
        }
        const message =
          error instanceof DocumentConsistencyQcApiError
            ? error.message
            : TASK_FETCH_FAILED_USER_MESSAGE
        setErrorMessage(message)
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

  if (errorMessage) {
    return (
      <div className="flex h-svh items-center justify-center p-6 text-sm text-destructive">
        {errorMessage}
      </div>
    )
  }

  if (targetPath) {
    return <Navigate to={targetPath} replace />
  }

  return (
    <div className="flex h-svh items-center justify-center p-6 text-sm text-muted-foreground">
      {TASK_LOADING_USER_MESSAGE}
    </div>
  )
}
