import { ResultShell } from '@/components/review/result-shell'

export type TaskResultShellProps = {
  taskRunId: string
  taskId: string
  taskDisplayName: string
  flowRunId: string
}

/** Task-owned Result phase composition wrapping the DCQC result workspace. */
export function TaskResultShell({
  taskRunId,
  taskId,
  taskDisplayName,
  flowRunId,
}: TaskResultShellProps) {
  return (
    <div
      className="flex h-dvh min-h-0 w-full flex-col overflow-hidden launcher-tech-bg"
      data-task-result-shell
      data-task-run-id={taskRunId}
      data-task-id={taskId}
    >
      <ResultShell flowRunId={flowRunId} taskDisplayName={taskDisplayName} taskRunId={taskRunId} />
    </div>
  )
}
