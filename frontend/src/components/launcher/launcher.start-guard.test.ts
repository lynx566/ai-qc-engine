// @vitest-environment happy-dom

import { act, createElement, Fragment } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  DocumentConsistencyQcApiError,
  ProductTaskStartApiError,
  fetchTaskCatalog,
  startClinicalTrialDocQcTask,
} from '@/api/clinical-trial-doc-qc'
import { fetchTaskRun } from '@/api/task-run'
import { Launcher } from '@/components/launcher/launcher'
import { Toaster } from '@/components/ui/sonner'
import { taskResultRoutePath } from '@/lib/launcher-state'
import { showLauncherUploadRequiredHint } from '@/lib/launcher-start-guard'
import { SUCCESS_RESULT_TASK_STATE } from '@/test-fixtures/task-run-state'
import type { TaskCatalogEntry } from '@/types/document-consistency-qc'
import type { TaskRunReadModel } from '@/types/task-run'

vi.mock('@/lib/launcher-start-guard', async () => {
  const actual = await vi.importActual<typeof import('@/lib/launcher-start-guard')>(
    '@/lib/launcher-start-guard',
  )
  return {
    ...actual,
    showLauncherUploadRequiredHint: vi.fn(actual.showLauncherUploadRequiredHint),
  }
})

vi.mock('@/api/clinical-trial-doc-qc', async () => {
  const actual = await vi.importActual<typeof import('@/api/clinical-trial-doc-qc')>(
    '@/api/clinical-trial-doc-qc',
  )
  return {
    ...actual,
    fetchTaskCatalog: vi.fn(),
    startClinicalTrialDocQcTask: vi.fn(),
  }
})

vi.mock('@/api/task-run', () => ({
  fetchTaskRun: vi.fn(),
}))

const singleSlotTask: TaskCatalogEntry = {
  taskId: 'internal_dsur_qc',
  displayName: 'DSUR 核查',
  description: '单文档核查',
  slots: [
    {
      slotId: 'source',
      expectedDocumentType: 'dsur',
      uploadLabel: '上传 DSUR 文档',
      helpText: '请上传 DSUR 文件',
    },
  ],
}

const mockFetchTaskCatalog = vi.mocked(fetchTaskCatalog)
const mockStartClinicalTrialDocQcTask = vi.mocked(startClinicalTrialDocQcTask)
const mockFetchTaskRun = vi.mocked(fetchTaskRun)
const mockShowLauncherUploadRequiredHint = vi.mocked(showLauncherUploadRequiredHint)

function taskRun(
  taskRunId: string,
  state: TaskRunReadModel['state'],
): TaskRunReadModel {
  return {
    taskRunId,
    taskId: 'internal_dsur_qc',
    displayName: 'DSUR 质控',
    flowRuns: [{ flowId: 'document_consistency_qc', flowRunId: 'flow_test' }],
    state,
  }
}

let container: HTMLDivElement
let root: Root

function LocationProbe() {
  const location = useLocation()
  return createElement('output', { 'data-location': true }, location.pathname)
}

function renderLauncher() {
  act(() => {
    root.render(
      createElement(
        MemoryRouter,
        null,
        createElement(
          Fragment,
          null,
          createElement(Launcher),
          createElement(Toaster),
          createElement(LocationProbe),
        ),
      ),
    )
  })
}

async function flushLauncherInit() {
  await act(async () => {
    await Promise.resolve()
  })
}

function getStartButton(): HTMLButtonElement {
  const buttons = [...container.querySelectorAll('button')]
  const startButton = buttons.find((button) => button.textContent === '开始')
  if (!startButton) {
    throw new Error('开始 button not found')
  }
  return startButton
}

function getHiddenFileInput(): HTMLInputElement {
  const input = container.querySelector('input[type="file"]')
  if (!(input instanceof HTMLInputElement)) {
    throw new Error('file input not found')
  }
  return input
}

function makeFile(name: string): File {
  return new File(['content'], name, {
    type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  })
}

async function uploadRequiredFile() {
  const fileInput = getHiddenFileInput()
  await act(async () => {
    Object.defineProperty(fileInput, 'files', {
      configurable: true,
      value: [makeFile('dsur.docx')],
    })
    fileInput.dispatchEvent(new Event('change', { bubbles: true }))
  })
}

async function clickStart() {
  const startButton = getStartButton()
  await act(async () => {
    startButton.click()
  })
}

function locationPath(): string {
  return container.querySelector('[data-location]')?.textContent ?? ''
}

async function expectLocationPath(path: string) {
  await vi.waitFor(() => {
    expect(locationPath()).toBe(path)
  })
}

describe('launcher start guard interaction', () => {
  beforeEach(() => {
    vi.useRealTimers()
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)

    mockFetchTaskCatalog.mockResolvedValue({
      tasks: [singleSlotTask],
    })
    mockStartClinicalTrialDocQcTask.mockResolvedValue({
      taskRunId: 'task_run_123',
    })
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
    vi.clearAllMocks()
  })

  it('shows upload hint when start is clicked without a file', async () => {
    renderLauncher()
    await flushLauncherInit()

    const startButton = getStartButton()
    expect(startButton.disabled).toBe(false)

    await act(async () => {
      startButton.click()
    })

    expect(mockShowLauncherUploadRequiredHint).toHaveBeenCalledTimes(1)
    expect(mockStartClinicalTrialDocQcTask).not.toHaveBeenCalled()
    expect(startButton.textContent).toBe('开始')
  })

  it('does not use cursor-not-allowed on the inactive start button', async () => {
    renderLauncher()
    await flushLauncherInit()

    const startButton = getStartButton()
    expect(startButton.className).not.toContain('cursor-not-allowed')
  })

  it('renders confirmed product copy for known task ids instead of catalog display metadata', async () => {
    mockFetchTaskCatalog.mockResolvedValue({
      tasks: [
        {
          taskId: 'internal_dsur_qc',
          displayName: 'Custom Product Name',
          description: 'Custom Product Description',
          slots: [
            {
              slotId: 'source',
              expectedDocumentType: 'Custom Document Type',
              uploadLabel: 'Custom Upload',
              helpText: 'Custom Upload Help',
            },
          ],
        },
      ],
    })

    renderLauncher()
    await flushLauncherInit()

    expect(container.textContent).toContain('研发期间安全性更新报告（DSUR）')
    expect(container.textContent).toContain('点击或拖拽上传DSUR')
    expect(container.textContent).toContain('目前仅支持中文 .docx 文件')
    expect(container.textContent).not.toContain('Custom Product Name')
    expect(container.textContent).not.toContain('Custom Upload')
    expect(container.textContent).not.toContain('Custom Upload Help')
    expect(container.textContent).not.toContain('Custom Document Type')
  })

  it('starts Product Task when a required file is uploaded', async () => {
    renderLauncher()
    await flushLauncherInit()

    const fileInput = getHiddenFileInput()
    await act(async () => {
      Object.defineProperty(fileInput, 'files', {
        configurable: true,
        value: [makeFile('dsur.docx')],
      })
      fileInput.dispatchEvent(new Event('change', { bubbles: true }))
    })

    const startButton = getStartButton()
    await act(async () => {
      startButton.click()
      await Promise.resolve()
    })

    expect(mockStartClinicalTrialDocQcTask).toHaveBeenCalledTimes(1)
    expect(mockStartClinicalTrialDocQcTask).toHaveBeenCalledWith(
      'internal_dsur_qc',
      expect.any(Map),
    )
  })

  it('starts Product Task when a required file is dropped onto the upload target', async () => {
    renderLauncher()
    await flushLauncherInit()

    const uploadTarget = container.querySelector('[data-slot="slot-file-upload-target"]')
    if (!(uploadTarget instanceof HTMLButtonElement)) {
      throw new Error('upload target not found')
    }

    const dropEvent = new DragEvent('drop', { bubbles: true, cancelable: true })
    const dataTransfer = new DataTransfer()
    dataTransfer.items.add(makeFile('dsur.docx'))
    Object.defineProperty(dropEvent, 'dataTransfer', {
      configurable: true,
      value: dataTransfer,
    })

    await act(async () => {
      uploadTarget.dispatchEvent(dropEvent)
      await Promise.resolve()
    })

    await clickStart()

    expect(mockStartClinicalTrialDocQcTask).toHaveBeenCalledTimes(1)
    expect(mockStartClinicalTrialDocQcTask).toHaveBeenCalledWith(
      'internal_dsur_qc',
      expect.any(Map),
    )
  })

  it('shows loading copy while submitting', async () => {
    let resolveCreate:
      | ((value: Awaited<ReturnType<typeof startClinicalTrialDocQcTask>>) => void)
      | null = null
    mockStartClinicalTrialDocQcTask.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveCreate = resolve
        }),
    )

    renderLauncher()
    await flushLauncherInit()

    const fileInput = getHiddenFileInput()
    await act(async () => {
      Object.defineProperty(fileInput, 'files', {
        configurable: true,
        value: [makeFile('dsur.docx')],
      })
      fileInput.dispatchEvent(new Event('change', { bubbles: true }))
    })

    const startButton = getStartButton()
    await act(async () => {
      startButton.click()
      await Promise.resolve()
    })

    expect(startButton.textContent).toBe('功能准备中…')

    await act(async () => {
      resolveCreate?.({
        taskRunId: 'task_run_123',
      })
      await Promise.resolve()
    })
  })

  it('does not start duplicate tasks on repeated clicks while submitting', async () => {
    let resolveCreate:
      | ((value: Awaited<ReturnType<typeof startClinicalTrialDocQcTask>>) => void)
      | null = null
    mockStartClinicalTrialDocQcTask.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveCreate = resolve
        }),
    )

    renderLauncher()
    await flushLauncherInit()

    const fileInput = getHiddenFileInput()
    await act(async () => {
      Object.defineProperty(fileInput, 'files', {
        configurable: true,
        value: [makeFile('dsur.docx')],
      })
      fileInput.dispatchEvent(new Event('change', { bubbles: true }))
    })

    const startButton = getStartButton()
    await act(async () => {
      startButton.click()
      startButton.click()
      await Promise.resolve()
    })

    expect(mockStartClinicalTrialDocQcTask).toHaveBeenCalledTimes(1)
    expect(startButton.disabled).toBe(true)

    await act(async () => {
      resolveCreate?.({
        taskRunId: 'task_run_123',
      })
      await Promise.resolve()
    })
  })

  it('falls back to Task-owned QC setup when Start fails with TaskRun identity and TaskRun fetch fails', async () => {
    mockStartClinicalTrialDocQcTask.mockRejectedValue(
      Object.assign(new ProductTaskStartApiError('checkpoint failed', 'task_run_failed'), {
        flowRunId: 'flow_must_not_drive_navigation',
      }),
    )
    mockFetchTaskRun.mockRejectedValue(new DocumentConsistencyQcApiError('任务加载失败，请重试'))
    renderLauncher()
    await flushLauncherInit()

    await uploadRequiredFile()
    await clickStart()

    expect(mockFetchTaskRun).toHaveBeenCalledTimes(1)
    expect(mockFetchTaskRun).toHaveBeenCalledWith('task_run_failed')
    await expectLocationPath('/task-runs/task_run_failed/qc-setup')
  })

  it('routes according to TaskRun state when Start fails with TaskRun identity and TaskRun fetch succeeds', async () => {
    const taskRunId = 'task_run_result_ready'
    mockStartClinicalTrialDocQcTask.mockRejectedValue(
      new ProductTaskStartApiError('checkpoint failed', taskRunId),
    )
    mockFetchTaskRun.mockResolvedValue(
      taskRun(taskRunId, SUCCESS_RESULT_TASK_STATE),
    )
    renderLauncher()
    await flushLauncherInit()

    await uploadRequiredFile()
    await clickStart()

    expect(mockFetchTaskRun).toHaveBeenCalledTimes(1)
    expect(mockFetchTaskRun).toHaveBeenCalledWith(taskRunId)
    await expectLocationPath(taskResultRoutePath(taskRunId))
  })

  it('stays on the Launcher when Start fails without TaskRun identity', async () => {
    mockStartClinicalTrialDocQcTask.mockRejectedValue(
      new DocumentConsistencyQcApiError('unsupported task_id'),
    )
    renderLauncher()
    await flushLauncherInit()

    await uploadRequiredFile()
    await clickStart()

    expect(mockFetchTaskRun).not.toHaveBeenCalled()
    await vi.waitFor(() => {
      expect(locationPath()).toBe('/')
      expect(container.textContent).toContain('unsupported task_id')
    })
  })
})
