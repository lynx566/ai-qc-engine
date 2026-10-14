type TaskSidebarTitleProps = {
  taskDisplayName: string
  context: 'qc-setup' | 'result' | 'result-panel'
}

/** Compact Product Task title shown at the top of Task-owned sidebars. */
export function TaskSidebarTitle({ taskDisplayName, context }: TaskSidebarTitleProps) {
  const contextProps =
    context === 'qc-setup'
      ? { 'data-task-qc-setup-context': true, 'data-task-page-title': true }
      : context === 'result-panel'
        ? { 'data-result-panel-title': true }
        : { 'data-task-result-context': true }

  const titleClassName =
    context === 'qc-setup' || context === 'result-panel'
      ? 'break-words text-[17px] font-semibold leading-snug text-[#262626]'
      : 'break-words text-[15px] font-semibold leading-snug text-[#262626]'

  return (
    <p
      {...contextProps}
      className={titleClassName}
      title={taskDisplayName}
    >
      {taskDisplayName}
    </p>
  )
}
