import { useNavigate } from 'react-router-dom'

import { QcSetupShell } from '@/components/qc-setup/qc-setup-shell'
import { taskResultRoutePath } from '@/lib/launcher-state'
import type { TaskRunState } from '@/types/task-run'

export type TaskQcSetupShellProps = {
  taskRunId: string
  taskId: string
  taskDisplayName: string
  flowRunId: string
  taskState: TaskRunState
  refreshTaskRunState: () => Promise<TaskRunState | null>
}

/** Task-owned QC Setup composition wrapping the DCQC Candidate Scope workspace. */
export function TaskQcSetupShell({
  taskRunId,
  taskId,
  taskDisplayName,
  flowRunId,
  taskState,
  refreshTaskRunState,
}: TaskQcSetupShellProps) {
  const navigate = useNavigate()

  return (
    <div
      className="flex h-svh w-full flex-col overflow-hidden launcher-tech-bg"
      data-task-qc-setup-shell
      data-task-run-id={taskRunId}
      data-task-id={taskId}
    >
      <QcSetupShell
        taskDisplayName={taskDisplayName}
        flowRunId={flowRunId}
        taskState={taskState}
        refreshTaskRunState={refreshTaskRunState}
        onProceedToResult={() => navigate(taskResultRoutePath(taskRunId))}
      />
    </div>
  )
}
