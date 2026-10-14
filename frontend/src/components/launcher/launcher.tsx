import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Info } from 'lucide-react'
import { cn } from 'cn'

import {
  DocumentConsistencyQcApiError,
  ProductTaskStartApiError,
  fetchTaskCatalog,
  startClinicalTrialDocQcTask,
} from '@/api/clinical-trial-doc-qc'
import { fetchTaskRun } from '@/api/task-run'
import { LauncherPageCard, LauncherPageShell } from '@/components/launcher/launcher-page-shell'
import { SlotFileUpload } from '@/components/launcher/slot-file-upload'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import {
  allRequiredSlotsHaveFiles,
  resolveTaskRunDefaultRoutePath,
  taskQcSetupRoutePath,
  createEmptySlotFiles,
  toSlotFileUploadMap,
} from '@/lib/launcher-state'
import {
  resolveLauncherStartAttempt,
  showLauncherUploadRequiredHint,
} from '@/lib/launcher-start-guard'
import {
  getSlotUploadLabel,
  getTaskTabTooltip,
  getTaskTabLabel,
  sortCatalogByTaskOrder,
} from '@/lib/launcher-presentation'
import type { LauncherSubmitStatus, TaskCatalogEntry } from '@/types/document-consistency-qc'

function taskTabClassName(isSelected: boolean, inputsLocked: boolean): string {
  return cn(
    'inline-flex h-10 shrink-0 cursor-pointer items-center justify-center gap-1.5 whitespace-nowrap rounded-md px-4 text-sm leading-none transition-all',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400/50 focus-visible:ring-offset-2',
    isSelected
      ? 'bg-white font-semibold text-[#1E293B] shadow-sm'
      : 'bg-transparent font-medium text-[#334155] hover:text-[#1E293B]',
    inputsLocked && 'pointer-events-none opacity-60',
  )
}

function LauncherTaskInfoIcon({ content }: { content: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className="inline-flex size-5 shrink-0 items-center justify-center rounded-full text-slate-500 hover:bg-slate-100 hover:text-slate-700"
          aria-label={content}
          onClick={(event) => event.stopPropagation()}
          onPointerDown={(event) => event.stopPropagation()}
        >
          <Info className="size-3.5" aria-hidden="true" />
        </button>
      </TooltipTrigger>
      <TooltipContent side="bottom" align="center" className="max-w-xs">
        {content}
      </TooltipContent>
    </Tooltip>
  )
}

export function Launcher() {
  const navigate = useNavigate()
  const [catalog, setCatalog] = useState<TaskCatalogEntry[]>([])
  const [catalogError, setCatalogError] = useState<string | null>(null)
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)
  const [slotFiles, setSlotFiles] = useState<Map<string, File | null>>(new Map())
  const [submitStatus, setSubmitStatus] = useState<LauncherSubmitStatus>('idle')
  const [submitError, setSubmitError] = useState<string | null>(null)
  const startInFlightRef = useRef(false)

  const orderedCatalog = useMemo(() => sortCatalogByTaskOrder(catalog), [catalog])

  const selectedTask = useMemo(
    () => catalog.find((entry) => entry.taskId === selectedTaskId) ?? null,
    [catalog, selectedTaskId],
  )

  const inputsLocked = submitStatus === 'submitting'

  useEffect(() => {
    void (async () => {
      try {
        const response = await fetchTaskCatalog()
        const ordered = sortCatalogByTaskOrder(response.tasks)
        setCatalog(response.tasks)
        setCatalogError(null)
        if (ordered.length > 0) {
          setSelectedTaskId(ordered[0].taskId)
          setSlotFiles(createEmptySlotFiles(ordered[0]))
        }
      } catch (error) {
        const message =
          error instanceof DocumentConsistencyQcApiError
            ? error.message
            : '加载失败，请稍后重试'
        setCatalogError(message)
      }
    })()
  }, [])

  const handleTaskChange = useCallback(
    (taskId: string) => {
      if (inputsLocked) {
        return
      }
      setSelectedTaskId(taskId)
      const task = catalog.find((entry) => entry.taskId === taskId) ?? null
      setSlotFiles(createEmptySlotFiles(task))
      setSubmitError(null)
      setSubmitStatus('idle')
      startInFlightRef.current = false
    },
    [catalog, inputsLocked],
  )

  const handleSlotFileChange = useCallback(
    (slotId: string, file: File | null) => {
      if (inputsLocked) {
        return
      }
      setSlotFiles((previous) => {
        const next = new Map(previous)
        next.set(slotId, file)
        return next
      })
      setSubmitError(null)
    },
    [inputsLocked],
  )

  const startLooksInactive = !allRequiredSlotsHaveFiles(selectedTask, slotFiles)
  const startSubmitting = submitStatus === 'submitting'

  const handleStart = useCallback(async () => {
    const attempt = resolveLauncherStartAttempt(
      selectedTask,
      slotFiles,
      submitStatus,
    )
    if (attempt === 'show_upload_required_hint') {
      showLauncherUploadRequiredHint()
      return
    }
    if (attempt === 'blocked_submitting' || !selectedTask || startInFlightRef.current) {
      return
    }

    startInFlightRef.current = true
    setSubmitStatus('submitting')
    setSubmitError(null)

    try {
      const result = await startClinicalTrialDocQcTask(
        selectedTask.taskId,
        toSlotFileUploadMap(slotFiles),
      )

      navigate(taskQcSetupRoutePath(result.taskRunId))
    } catch (error) {
      if (error instanceof ProductTaskStartApiError && error.taskRunId) {
        try {
          const taskRun = await fetchTaskRun(error.taskRunId)
          navigate(resolveTaskRunDefaultRoutePath(error.taskRunId, taskRun.state))
        } catch {
          navigate(taskQcSetupRoutePath(error.taskRunId))
        }
        return
      }
      const message =
        error instanceof DocumentConsistencyQcApiError ? error.message : '任务启动失败'
      setSubmitError(message)
      setSubmitStatus('error')
    } finally {
      startInFlightRef.current = false
    }
  }, [navigate, selectedTask, slotFiles, submitStatus])

  if (catalogError) {
    return (
      <LauncherPageShell>
        <LauncherPageCard className="w-fit max-w-full py-16 text-center text-sm text-destructive shadow-sm">
          {catalogError}
        </LauncherPageCard>
      </LauncherPageShell>
    )
  }

  if (catalog.length === 0) {
    return (
      <LauncherPageShell>
        <LauncherPageCard className="w-fit max-w-full py-16 text-center text-sm text-slate-600 shadow-sm">
          正在加载…
        </LauncherPageCard>
      </LauncherPageShell>
    )
  }

  return (
    <LauncherPageShell>
      <TooltipProvider>
        <LauncherPageCard>
          <div className="space-y-10">
            <div className="space-y-6">
              <div className="flex justify-center">
                <div
                  role="tablist"
                  aria-label="质控任务"
                  className="inline-flex w-fit max-w-full flex-wrap items-center justify-center gap-1 rounded-lg bg-[#DBEAFE] p-1"
                >
                {orderedCatalog.map((entry) => {
                  const isSelected = entry.taskId === selectedTaskId

                  return (
                    <div
                      key={entry.taskId}
                      role="tab"
                      aria-selected={isSelected}
                      tabIndex={inputsLocked ? -1 : 0}
                      onClick={() => handleTaskChange(entry.taskId)}
                      onKeyDown={(event) => {
                        if (inputsLocked) {
                          return
                        }
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          handleTaskChange(entry.taskId)
                        }
                      }}
                      className={taskTabClassName(isSelected, inputsLocked)}
                    >
                      {getTaskTabLabel(entry.taskId, entry.displayName)}
                      {(() => {
                        const tooltip = getTaskTabTooltip(entry.taskId)
                        return tooltip ? (
                          <LauncherTaskInfoIcon content={tooltip} />
                        ) : null
                      })()}
                    </div>
                  )
                })}
                </div>
              </div>
          </div>

          {selectedTask ? (
            <div>
              <section
                className={cn(
                  'grid gap-8',
                  selectedTask.slots.length > 1 ? 'sm:grid-cols-2' : 'grid-cols-1',
                )}
              >
                {selectedTask.slots.map((slot) => {
                  const currentFile = slotFiles.get(slot.slotId) ?? null
                  return (
                    <SlotFileUpload
                      key={slot.slotId}
                      inputId={`slot-upload-${slot.slotId}`}
                      title={getSlotUploadLabel(
                        selectedTask.taskId,
                        slot.slotId,
                        slot.uploadLabel,
                      )}
                      file={currentFile}
                      disabled={inputsLocked}
                      className={
                        selectedTask.slots.length > 1 ? 'max-w-sm' : undefined
                      }
                      onFileChange={(file) => handleSlotFileChange(slot.slotId, file)}
                    />
                  )
                })}
              </section>
              <div className="mx-auto mt-6 flex max-w-xl items-center justify-center gap-2 px-4">
                <Info className="size-4 shrink-0 text-[#94A3B8]" aria-hidden="true" />
                <p className="text-[13px] leading-snug text-[#334155]">
                  若您上传的文件中存在修订痕迹，系统会自动接受所有修订再进行质控。
                </p>
              </div>
            </div>
          ) : null}

          <div className="flex flex-col items-center gap-4 pt-4">
            {submitError ? (
              <p className="w-full text-center text-sm text-destructive">{submitError}</p>
            ) : null}
            <Button
              type="button"
              variant="secondary"
              className={cn(
                'h-10 min-w-[120px] rounded-md px-6 text-sm font-semibold',
                'disabled:opacity-100',
                startLooksInactive
                  ? 'border border-[#CBD5E1] bg-[#F1F5F9] text-[#475569] hover:bg-[#F1F5F9]'
                  : 'border border-[#2563EB] bg-[#2563EB] text-white shadow-sm hover:bg-[#1D4ED8]',
              )}
              disabled={startSubmitting}
              onClick={() => void handleStart()}
            >
              {submitStatus === 'submitting' ? '功能准备中…' : '开始'}
            </Button>
          </div>
          </div>
        </LauncherPageCard>
      </TooltipProvider>
    </LauncherPageShell>
  )
}
