// @vitest-environment happy-dom

import { act, createElement } from 'react'
import { flushSync } from 'react-dom'
import { createRoot, type Root } from 'react-dom/client'
import type { Window } from 'happy-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  fetchCandidateScopeState,
  submitCandidateScopeNext,
} from '@/api/candidate-scope'
import { fetchCandidateScopeDocument } from '@/api/candidate-scope-document'
import { QcSetupShell } from '@/components/qc-setup/qc-setup-shell'
import {
  QC_SETUP_PROCEED_LABEL,
  QC_SETUP_PROCEED_PENDING_LABEL,
} from '@/lib/launcher-presentation'
import type { CandidateScopeFlowState } from '@/types/candidate-scope'
import type { TaskRunState } from '@/types/task-run'
import {
  FLOW_FAILED_TASK_STATE,
  PAUSED_TASK_STATE,
  SUCCESS_NO_RESULT_TASK_STATE,
  SUCCESS_RESULT_TASK_STATE,
} from '@/test-fixtures/task-run-state'

vi.mock('@/api/candidate-scope', async () => {
  const actual = await vi.importActual<typeof import('@/api/candidate-scope')>(
    '@/api/candidate-scope',
  )
  return {
    ...actual,
    fetchCandidateScopeState: vi.fn(),
    submitCandidateScopeNext: vi.fn(),
  }
})

vi.mock('@/api/candidate-scope-document', () => ({
  fetchCandidateScopeDocument: vi.fn(),
}))

const flowRunId = 'document_consistency_qc_20260910_150115_296031Z'

const flowState: CandidateScopeFlowState = {
  flowId: 'document_consistency_qc',
  flowRunId,
  capabilityId: 'internal_dsur',
  capabilityTitle: '试验药临床安全性核查',
  flowStatus: 'paused_at_candidate_scope',
  canResume: true,
  contentDomainGroups: [
    {
      contentDomainId: 'clinical_safety',
      displayLabel: '临床安全性',
      filterJobIds: ['dsur_clinical_safety', 'dsur_overview'],
    },
  ],
  slots: [
    {
      slotId: 'source',
      docId: 'doc_test',
      automaticAnchorBlockIds: ['C0010', 'C0030'],
      currentAnchorBlockIds: ['C0010', 'C0030'],
      headings: [
        {
          docId: 'doc_test',
          filterJobId: 'dsur_overview',
          anchorBlockId: 'C0010',
          title: '1. 执行概要',
          headingPath: ['1. 执行概要'],
          level: 1,
          docOrderIndex: 10,
        },
        {
          docId: 'doc_test',
          filterJobId: 'dsur_clinical_safety',
          anchorBlockId: 'C0030',
          title: '4.1 总体不良事件概览',
          headingPath: ['4. 临床安全性', '4.1 总体不良事件概览'],
          level: 2,
          docOrderIndex: 80,
        },
      ],
    },
  ],
}

const mockFetchCandidateScopeState = vi.mocked(fetchCandidateScopeState)
const mockSubmitCandidateScopeNext = vi.mocked(submitCandidateScopeNext)
const mockFetchCandidateScopeDocument = vi.mocked(fetchCandidateScopeDocument)

let container: HTMLDivElement
let root: Root

const onProceedToResult = vi.fn()
const refreshTaskRunState = vi.fn<() => Promise<TaskRunState>>()

const pausedTaskState: TaskRunState = PAUSED_TASK_STATE

function renderQcSetupShell(key = flowRunId, nextFlowRunId = flowRunId) {
  act(() => {
    root.render(createElement(QcSetupShell, {
      key,
      taskDisplayName: 'DSUR',
      flowRunId: nextFlowRunId,
      onProceedToResult,
      taskState: pausedTaskState,
      refreshTaskRunState,
    }))
  })
}

async function flushAsyncWork() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
  })
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

function getProceedButton(): HTMLButtonElement {
  const button = [...container.querySelectorAll('[data-sidebar-main-action]')].find(
    (candidate) => candidate.textContent === QC_SETUP_PROCEED_LABEL,
  )
  if (!(button instanceof HTMLButtonElement)) {
    throw new Error('Proceed button not found')
  }
  return button
}

describe('qc setup shell execution flow', () => {
  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)

    mockFetchCandidateScopeState.mockResolvedValue(flowState)
    refreshTaskRunState.mockResolvedValue({
      ...SUCCESS_RESULT_TASK_STATE,
    })
    mockFetchCandidateScopeDocument.mockResolvedValue({
      doc_id: 'doc_test',
      file_name: 'showcase.docx',
      display_name: 'showcase.docx',
      blocks: [
        {
          block_id: 'block_1',
          kind: 'paragraph',
          raw_text: 'Sample paragraph',
          normalized_text: 'Sample paragraph',
          doc_order_index: 0,
          heading_path: [],
        },
      ],
    })
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
    vi.clearAllMocks()
  })

  it.each(['mismatch', 'uncertain'] as const)('allows Run and submits the normal selections with a %s diagnostic', async (status) => {
    mockFetchCandidateScopeState.mockResolvedValue({
      ...flowState,
      slots: [{ ...flowState.slots[0]!, documentTypeDiagnostic: { status, expectedDocumentType: 'DSUR' } }],
    })
    mockSubmitCandidateScopeNext.mockResolvedValue({
      status: 'ready', flowId: 'document_consistency_qc', flowRunId,
      flowStatus: 'success', pausedAtCandidateScope: false, pausedSlotIds: [], completed: true,
    })
    renderQcSetupShell()
    await flushAsyncWork()
    expect(container.textContent).toContain('⚠ 请确认上传文件是否为 DSUR。')
    expect(getProceedButton().disabled).toBe(false)
    act(() => getProceedButton().click())
    await flushAsyncWork()
    expect(mockSubmitCandidateScopeNext).toHaveBeenCalledWith({
      flowRunId,
      slotDecisions: [{ slotId: 'source', candidateScope: [
        { filterJobId: 'dsur_clinical_safety', anchorBlockIds: ['C0030'] },
        { filterJobId: 'dsur_overview', anchorBlockIds: ['C0010'] },
      ] }],
    })
    expect(onProceedToResult).toHaveBeenCalledOnce()
  })

  it.each([false, true])('preserves pane instances, candidate section, draft and separate scroll owners across 840px with editing=%s', async (editing) => {
    mockFetchCandidateScopeState.mockResolvedValue({
      ...flowState,
      contentDomainGroups: [
        { contentDomainId: 'overview', displayLabel: '执行概要', filterJobIds: ['dsur_overview'] },
        { contentDomainId: 'clinical_safety', displayLabel: '临床安全性', filterJobIds: ['dsur_clinical_safety'] },
      ],
    })
    const browser = window as unknown as Window
    const originalWidth = window.innerWidth
    const originalHeight = window.innerHeight
    browser.happyDOM.setViewport({ width: 1024, height: 800 })
    try {
      renderQcSetupShell()
      await flushAsyncWork()
      const tab = container.querySelector<HTMLButtonElement>('[data-content-domain-id="clinical_safety"]')!
      act(() => tab.click())
      expect(tab.getAttribute('aria-selected')).toBe('true')
      if (editing) {
        act(() => [...container.querySelectorAll<HTMLButtonElement>('button')].find(button => button.textContent === '调整')!.click())
        const checkbox = container.querySelector<HTMLInputElement>('#candidate-C0030')!
        expect(checkbox.checked).toBe(true)
        act(() => checkbox.click())
        expect(checkbox.checked).toBe(false)
      }

      const documentPane = container.querySelector('main')!
      const setupPane = container.querySelector('aside')!
      const reader = documentPane.querySelector('.document-surface')!
      const documentScroll = documentPane.querySelector<HTMLElement>('[data-slot="scroll-area-viewport"]')!
      const candidateScroll = setupPane.querySelector<HTMLElement>('[data-slot="scroll-area-viewport"]')!
      const editCheckbox = setupPane.querySelector('#candidate-C0030')
      expect(documentScroll).not.toBe(candidateScroll)
      documentScroll.scrollTop = 125
      candidateScroll.scrollTop = 40
      act(() => documentScroll.dispatchEvent(new Event('scroll')))
      expect(candidateScroll.scrollTop).toBe(40)
      act(() => candidateScroll.dispatchEvent(new Event('scroll')))
      expect(documentScroll.scrollTop).toBe(125)

      for (const width of [839.5, 640, 840, 1024]) {
        act(() => {
          browser.happyDOM.setViewport({ width, height: 800 })
          window.dispatchEvent(new Event('resize'))
        })
        await flushAsyncWork()
        expect(container.querySelector('main')).toBe(documentPane)
        expect(container.querySelector('aside')).toBe(setupPane)
        expect(documentPane.nextElementSibling).toBe(setupPane)
        expect(documentPane.querySelector('.document-surface')).toBe(reader)
        expect(container.querySelector('[data-content-domain-id="clinical_safety"]')).toBe(tab)
        expect(tab.getAttribute('aria-selected')).toBe('true')
        expect(documentPane.querySelector('[data-slot="scroll-area-viewport"]')).toBe(documentScroll)
        expect(setupPane.querySelector('[data-slot="scroll-area-viewport"]')).toBe(candidateScroll)
        expect(documentScroll.scrollTop).toBe(125)
        expect(candidateScroll.scrollTop).toBe(40)
        if (editing) {
          expect(setupPane.querySelector('#candidate-C0030')).toBe(editCheckbox)
          expect((editCheckbox as HTMLInputElement).checked).toBe(false)
          expect(setupPane.querySelector('[data-candidate-chapter-edit-footer]')).not.toBeNull()
          expect(getProceedButton().disabled).toBe(true)
        } else {
          expect(setupPane.querySelector('[data-candidate-chapter-edit-footer]')).toBeNull()
          expect(setupPane.querySelector('[data-candidate-selected="true"]')?.textContent).toContain('4.1 总体不良事件概览')
        }
      }
    } finally {
      browser.happyDOM.setViewport({ width: originalWidth, height: originalHeight })
    }
  })

  it('requests Task-level result navigation after next request succeeds', async () => {
    let resolveSubmit: ((value: Awaited<ReturnType<typeof submitCandidateScopeNext>>) => void) | null =
      null
    mockSubmitCandidateScopeNext.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveSubmit = resolve
        }),
    )

    renderQcSetupShell()
    await flushAsyncWork()

    const proceedButton = getProceedButton()
    act(() => {
      proceedButton.click()
    })
    await flushAsyncWork()

    expect(container.textContent).toContain(QC_SETUP_PROCEED_PENDING_LABEL)
    expect(container.querySelector('.document-surface')).toBeTruthy()

    act(() => {
      resolveSubmit?.({
        status: 'ready',
        flowId: 'document_consistency_qc',
        flowRunId,
        flowStatus: 'success',
        pausedAtCandidateScope: false,
        pausedSlotIds: [],
        completed: true,
      })
    })
    await flushAsyncWork()

    expect(onProceedToResult).toHaveBeenCalledOnce()
    expect(container.textContent).not.toContain('已完成')
    expect(container.textContent).not.toContain('流程已完成')
    expect(container.textContent).not.toContain('>查看结果<')
  })

  it('does not navigate when Next says completed but refreshed Product Result is unavailable', async () => {
    mockSubmitCandidateScopeNext.mockResolvedValue({
      status: 'ready',
      flowId: 'document_consistency_qc',
      flowRunId,
      flowStatus: 'success',
      pausedAtCandidateScope: false,
      pausedSlotIds: [],
      completed: true,
    })
    refreshTaskRunState.mockResolvedValue({
      ...SUCCESS_NO_RESULT_TASK_STATE,
    })

    renderQcSetupShell()
    await flushAsyncWork()
    act(() => getProceedButton().click())
    await flushAsyncWork()

    expect(onProceedToResult).not.toHaveBeenCalled()
    expect(container.textContent).toContain('核查结果尚未生成')
  })

  it('stays on QC Setup and shows downstream failure from refreshed Product state', async () => {
    mockSubmitCandidateScopeNext.mockResolvedValue({
      status: 'ready',
      flowId: 'document_consistency_qc',
      flowRunId,
      flowStatus: 'failed',
      pausedAtCandidateScope: false,
      pausedSlotIds: [],
      completed: false,
    })
    refreshTaskRunState.mockResolvedValue({
      ...FLOW_FAILED_TASK_STATE,
    })

    renderQcSetupShell()
    await flushAsyncWork()
    act(() => getProceedButton().click())
    await flushAsyncWork()

    expect(onProceedToResult).not.toHaveBeenCalled()
    expect(container.textContent).toContain('核查执行失败')
  })

  it('restores proceed label and keeps document reader visible after request error', async () => {
    mockSubmitCandidateScopeNext.mockRejectedValue(new Error('network down'))

    renderQcSetupShell()
    await flushAsyncWork()

    act(() => {
      getProceedButton().click()
    })
    await flushAsyncWork()

    expect(container.textContent).toContain('候选范围提交失败')
    expect(container.textContent).toContain(QC_SETUP_PROCEED_LABEL)
    expect(container.textContent).not.toContain(QC_SETUP_PROCEED_PENDING_LABEL)
    expect(container.querySelector('.document-surface')).toBeTruthy()
    expect(onProceedToResult).not.toHaveBeenCalled()
  })

  it('retries only the TaskRun refresh after the candidate scope was submitted', async () => {
    mockSubmitCandidateScopeNext.mockResolvedValue({
      status: 'ready',
      flowId: 'document_consistency_qc',
      flowRunId,
      flowStatus: 'success',
      pausedAtCandidateScope: false,
      pausedSlotIds: [],
      completed: true,
    })
    refreshTaskRunState
      .mockRejectedValueOnce(new Error('refresh unavailable'))
      .mockResolvedValueOnce({ ...SUCCESS_RESULT_TASK_STATE })

    renderQcSetupShell()
    await flushAsyncWork()
    act(() => getProceedButton().click())
    await flushAsyncWork()

    expect(container.textContent).toContain('状态更新失败，请重试')
    expect(mockSubmitCandidateScopeNext).toHaveBeenCalledOnce()

    act(() => getProceedButton().click())
    await flushAsyncWork()

    expect(mockSubmitCandidateScopeNext).toHaveBeenCalledOnce()
    expect(refreshTaskRunState).toHaveBeenCalledTimes(2)
    expect(onProceedToResult).toHaveBeenCalledOnce()
  })

  it('ignores an old Next completion after the QC workspace changes', async () => {
    const refresh = deferred<TaskRunState>()
    mockSubmitCandidateScopeNext.mockResolvedValue({
      status: 'ready',
      flowId: 'document_consistency_qc',
      flowRunId,
      flowStatus: 'success',
      pausedAtCandidateScope: false,
      pausedSlotIds: [],
      completed: true,
    })
    refreshTaskRunState.mockReturnValue(refresh.promise)

    renderQcSetupShell('task-A')
    await flushAsyncWork()
    act(() => getProceedButton().click())
    await flushAsyncWork()

    flushSync(() => {
      root.render(createElement(QcSetupShell, {
        key: 'task-B',
        taskDisplayName: 'DSUR',
        flowRunId: 'flow_B',
        onProceedToResult,
        taskState: pausedTaskState,
        refreshTaskRunState,
      }))
    })
    refresh.resolve({ ...SUCCESS_RESULT_TASK_STATE })
    await flushAsyncWork()

    expect(onProceedToResult).not.toHaveBeenCalled()
  })

  it('keeps another slot request valid when the first slot document becomes ready', async () => {
    const sourceARequest = deferred<Awaited<ReturnType<typeof fetchCandidateScopeDocument>>>()
    const sourceBRequest = deferred<Awaited<ReturnType<typeof fetchCandidateScopeDocument>>>()
    const replacementSourceBRequest = deferred<
      Awaited<ReturnType<typeof fetchCandidateScopeDocument>>
    >()
    const multiSlotFlowState: CandidateScopeFlowState = {
      ...flowState,
      slots: [
        { ...flowState.slots[0]!, slotId: 'source_a', docId: 'doc_a' },
        { ...flowState.slots[0]!, slotId: 'source_b', docId: 'doc_b' },
      ],
    }
    let sourceBCallCount = 0

    mockFetchCandidateScopeState.mockResolvedValue(multiSlotFlowState)
    mockFetchCandidateScopeDocument.mockImplementation((_flowRunId, slotId) => {
      if (slotId === 'source_a') {
        return sourceARequest.promise
      }
      sourceBCallCount += 1
      return sourceBCallCount === 1
        ? sourceBRequest.promise
        : replacementSourceBRequest.promise
    })

    renderQcSetupShell()
    await flushAsyncWork()

    sourceARequest.resolve({
      doc_id: 'doc_a',
      file_name: 'source-a.docx',
      display_name: 'source-a.docx',
      content_blocks: [],
    })
    await flushAsyncWork()

    const sourceBButton = [...container.querySelectorAll('button')].find(
      (button) => button.textContent === 'source_b',
    )
    if (!(sourceBButton instanceof HTMLButtonElement)) {
      throw new Error('source_b selector not found')
    }
    act(() => sourceBButton.click())

    sourceBRequest.resolve({
      doc_id: 'doc_b',
      file_name: 'source-b.docx',
      display_name: 'source-b.docx',
      content_blocks: [],
    })
    await flushAsyncWork()

    expect(container.querySelector('.document-surface')).toBeTruthy()
  })
})
