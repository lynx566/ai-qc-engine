// @vitest-environment happy-dom

import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { renderToStaticMarkup } from 'react-dom/server'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { QcSetupSidebar } from '@/components/qc-setup/qc-setup-sidebar'
import {
  CANDIDATE_CHAPTER_HELPER_TEXT,
  QC_SETUP_PROCEED_LABEL,
  QC_SETUP_PROCEED_PENDING_LABEL,
  QC_SETUP_PROCEED_WAITING_HINT,
  QC_FUNCTION_ID,
  QC_FUNCTION_LABEL,
} from '@/lib/launcher-presentation'
import type { CandidateScopeContentDomainGroup, CandidateScopeSlotState } from '@/types/candidate-scope'

const contentDomainGroups: CandidateScopeContentDomainGroup[] = [
  {
    contentDomainId: 'clinical_safety',
    displayLabel: '临床安全性',
    filterJobIds: ['dsur_clinical_safety', 'dsur_overview'],
  },
]

const slotState: CandidateScopeSlotState = {
  slotId: 'source',
  docId: 'doc_test',
  automaticAnchorBlockIds: ['C0010', 'C0020', 'C0030', 'C0040'],
  currentAnchorBlockIds: ['C0010', 'C0030', 'C0040'],
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
      filterJobId: 'dsur_overview',
      anchorBlockId: 'C0020',
      title: '2. 全球上市批准状态',
      headingPath: ['2. 全球上市批准状态'],
      level: 1,
      docOrderIndex: 20,
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
    {
      docId: 'doc_test',
      filterJobId: 'dsur_clinical_safety',
      anchorBlockId: 'C0040',
      title: '4.3.1 安全性参考信息的一致性',
      headingPath: [
        '4. 临床安全性',
        '4.3 其他安全性观察',
        '4.3.1 安全性参考信息的一致性',
      ],
      level: 3,
      docOrderIndex: 110,
    },
  ],
}

const noop = () => {}

function renderSidebar(isEditing: boolean, focusedBlockId: string | null = null) {
  return renderToStaticMarkup(
    createElement(QcSetupSidebar, {
      flowId: 'document_consistency_qc',
      slotState,
      contentDomainGroups,
      currentSelected: new Set(['C0010', 'C0030', 'C0040']),
      draftSelected: new Set(['C0010', 'C0040']),
      isEditing,
      onStartEdit: noop,
      onApply: noop,
      onCancelEdit: noop,
      onToggleHeading: noop,
      onScrollToBlock: noop,
      focusedBlockId,
      nextStatus: 'idle',
      nextError: null,
      onNext: noop,
      isNextDisabled: isEditing,
      canResume: true,
    }),
  )
}

describe('qc setup sidebar copy', () => {
  it('shows frozen user-facing labels only', () => {
    const source = readFileSync(
      resolve(import.meta.dirname, 'qc-setup-sidebar.tsx'),
      'utf8',
    )

    expect(source).toContain('候选章节')
    expect(source).toContain('CANDIDATE_CHAPTER_HELPER_TEXT')
    expect(source).not.toContain('QC_FUNCTION_SECTION_LABEL')
    expect(source).toContain('调整')
    expect(source).not.toContain('核查章节范围')
    expect(source).not.toContain('调整候选章节')
    expect(source).not.toContain('质控功能')
    expect(source).not.toContain('候选核查范围')
    expect(source).not.toContain('可调整候选章节')
    expect(source).not.toContain('可进行候选章节调整')
    expect(source).not.toContain('Selected for Clinical Safety')
    expect(source).not.toContain('Filter Output Projection')
    expect(source).not.toContain('primary')
    expect(source).not.toContain('supporting')
    expect(source).not.toContain('个候选章节')
  })
})

describe('qc setup sidebar view mode', () => {
  it('shows function card title, candidate subsection, domain pill, and full catalog', () => {
    const html = renderSidebar(false)

    expect(html).not.toContain('>功能<')
    expect(html).not.toContain('质控功能')
    expect(html).toContain(QC_FUNCTION_LABEL)
    expect(html).toContain('data-function-card')
    expect(html).toContain(`data-function-id="${QC_FUNCTION_ID}"`)
    expect(html).toContain('候选章节')
    expect(html).toContain(CANDIDATE_CHAPTER_HELPER_TEXT)
    expect(html).toContain('临床安全性')
    expect(html).not.toMatch(/\d+\s*个候选章节/)
    expect(html).not.toContain('核查章节范围')
    expect(html).toContain('1. 执行概要')
    expect(html).toContain('2. 全球上市批准状态')
    expect(html).toContain('4.1 总体不良事件概览')
    expect(html).toContain('4.3.1 安全性参考信息的一致性')
    expect(html).not.toContain('ungrouped')
    expect(html).toContain('调整')
    expect(html).toContain('进行质控')
    expect(html).toContain('border border-[#E2E8F0]')
    expect(html).toContain('text-[#0F172A]')
    expect(html).toContain('data-sidebar-main-action')
    expect(html).toContain('bg-[#1e56e3]')
    expect(html).toContain('role="tab"')
    expect(html).toContain('data-content-domain-id="clinical_safety"')
    expect(html).toContain('pt-4')
    expect(html).toContain('text-[14px] font-semibold')
    expect(html).toContain('data-function-local-setting')
    expect(html).toContain('bg-[#F8FAFC]')
    expect(html).toContain('text-[13px] font-medium text-[#334155]')
    expect(html).not.toContain('lucide-chevron-down')
    expect(html).not.toContain('选择候选章节')
    expect(html).not.toContain('应用调整')
    expect(html).not.toContain('candidate-C0010')
    expect(html).not.toContain('候选核查范围')
    expect(html).not.toContain('调整候选章节')
    expect(html.indexOf('核查章节范围')).toBe(-1)

    const functionCardIndex = html.indexOf('data-function-card')
    const functionTitleIndex = html.indexOf(QC_FUNCTION_LABEL)
    const subsectionIndex = html.indexOf('候选章节')
    const helperIndex = html.indexOf(CANDIDATE_CHAPTER_HELPER_TEXT)
    const domainPillIndex = html.indexOf('data-content-domain-id="clinical_safety"')
    const modifyIndex = html.indexOf('>调整<')
    expect(html).toMatch(/data-function-card[\s\S]*data-function-local-setting/)
    expect(functionCardIndex).toBeLessThan(functionTitleIndex)
    expect(functionTitleIndex).toBeLessThan(subsectionIndex)
    expect(subsectionIndex).toBeLessThan(helperIndex)
    expect(helperIndex).toBeLessThan(domainPillIndex)
    expect(domainPillIndex).toBeLessThan(modifyIndex)
  })

  it('keeps candidate chapter configuration inside the function card', () => {
    const html = renderSidebar(false)
    const functionCardStart = html.indexOf('data-function-card')
    const functionCardEnd = html.indexOf('data-sidebar-task-footer')
    const functionCardHtml = html.slice(functionCardStart, functionCardEnd)

    expect(functionCardHtml).toContain(QC_FUNCTION_LABEL)
    expect(functionCardHtml).toContain('data-function-local-setting')
    expect(functionCardHtml).toContain('候选章节')
    expect(functionCardHtml).toContain(CANDIDATE_CHAPTER_HELPER_TEXT)
    expect(functionCardHtml).toContain('data-content-domain-id="clinical_safety"')
    expect(functionCardHtml).toContain('1. 执行概要')
  })

  it('marks selected headings with full-width blue pills and text indent on inner label', () => {
    const html = renderSidebar(false)

    expect(html).toContain('chapter-row')
    expect(html).toContain('!bg-[#e8f3ff]')
    expect(html).toContain('text-[#1f2329]!')
    expect(html).toContain('text-[#8c8c8c]')
    expect(html).toContain('is-selected')
    expect(html).toContain('min-h-[30px]')
    expect(html).toContain('break-words whitespace-normal')
    expect(html).toContain('px-[10px]')
    expect(html).toContain('rounded-[4px]')
    expect(html).toContain('hover:bg-[#f7f8fa]')
    expect(html).toContain('gap-1')
    expect(html).not.toContain('marginLeft')
    expect(html).not.toContain('border-l-[#2b5ae8]')
    expect(html).not.toContain('border-l-2')
    expect(html).not.toContain('border-l-[#BFDBFE]')
    expect(html).not.toContain('rounded-full bg-[#2563EB]')
    expect(html).not.toContain('lucide-check')
  })

  it('keeps hover text stable and removes click focus outlines', () => {
    const html = renderSidebar(false, 'doc_test:C0020')

    expect(html).toContain('hover:text-[#1f2329]!')
    expect(html).toContain('hover:text-[#8c8c8c]!')
    expect(html).toContain('outline-none!')
    expect(html).toContain('focus-visible:outline-none!')
    expect(html).toContain('focus:ring-0')
    expect(html).not.toContain('hover:text-foreground')
    expect(html).not.toContain('ring-[#2b5ae8]/15')
    expect(html).not.toContain('border-l-[3px]')
    expect(html).not.toContain('bg-secondary')
    expect(html).not.toContain('bg-zinc-200/60')
  })
})

describe('qc setup sidebar edit mode', () => {
  it('shows checkbox tree and card-local apply controls when editing', () => {
    const html = renderSidebar(true)

    expect(html).toContain('候选章节')
    expect(html).toContain(CANDIDATE_CHAPTER_HELPER_TEXT)
    expect(html).toContain('选择候选章节')
    expect(html).toContain('应用调整')
    expect(html).toContain('取消')
    expect(html).toContain('data-candidate-chapter-edit-footer')
    expect(html).toContain('candidate-C0010')
    expect(html).toContain('2. 全球上市批准状态')
    expect(html).toContain('4.3.1 安全性参考信息的一致性')
    expect(html).not.toContain('候选核查范围')
    expect(html).not.toContain('>调整<')

    const functionCardIndex = html.indexOf('data-function-card')
    const editFooterIndex = html.indexOf('data-candidate-chapter-edit-footer')
    const taskFooterIndex = html.indexOf('data-sidebar-task-footer')
    expect(functionCardIndex).toBeLessThan(editFooterIndex)
    expect(editFooterIndex).toBeLessThan(taskFooterIndex)
    expect(html).toContain('>进行质控<')
  })

  it('does not show apply controls in view mode', () => {
    const html = renderSidebar(false)

    expect(html).not.toContain('data-candidate-chapter-edit-footer')
    expect(html).not.toContain('应用调整')
    expect(html).toContain('>调整<')
  })

  it('hosts edit panel inside the sidebar branch', () => {
    const html = renderSidebar(true)

    expect(html).toMatch(/<div[\s\S]*选择候选章节[\s\S]*candidate-C0010[\s\S]*<\/div>/)
  })
})

describe('qc setup sidebar actions', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
  })

  it('calls onApply when card-local apply action is clicked', () => {
    const onApply = vi.fn()

    act(() => {
      root.render(
        createElement(QcSetupSidebar, {
          flowId: 'document_consistency_qc',
          slotState,
          contentDomainGroups,
          currentSelected: new Set(['C0010', 'C0030', 'C0040']),
          draftSelected: new Set(['C0010', 'C0040']),
          isEditing: true,
          onStartEdit: () => {},
          onApply,
          onCancelEdit: () => {},
          onToggleHeading: () => {},
          onScrollToBlock: () => {},
          focusedBlockId: null,
          nextStatus: 'idle',
          nextError: null,
          onNext: () => {},
          isNextDisabled: true,
          canResume: true,
        }),
      )
    })

    const applyButton = [...container.querySelectorAll('button')].find(
      (button) => button.textContent === '应用调整',
    )
    expect(applyButton).toBeTruthy()

    act(() => {
      applyButton?.click()
    })

    expect(onApply).toHaveBeenCalledTimes(1)
  })

  it('calls onCancelEdit when card-local cancel action is clicked', () => {
    const onCancelEdit = vi.fn()

    act(() => {
      root.render(
        createElement(QcSetupSidebar, {
          flowId: 'document_consistency_qc',
          slotState,
          contentDomainGroups,
          currentSelected: new Set(['C0010', 'C0030', 'C0040']),
          draftSelected: new Set(['C0010', 'C0040']),
          isEditing: true,
          onStartEdit: () => {},
          onApply: () => {},
          onCancelEdit,
          onToggleHeading: () => {},
          onScrollToBlock: () => {},
          focusedBlockId: null,
          nextStatus: 'idle',
          nextError: null,
          onNext: () => {},
          isNextDisabled: true,
          canResume: true,
        }),
      )
    })

    const cancelButton = [...container.querySelectorAll('button')].find(
      (button) => button.textContent === '取消',
    )
    expect(cancelButton).toBeTruthy()

    act(() => {
      cancelButton?.click()
    })

    expect(onCancelEdit).toHaveBeenCalledTimes(1)
  })

  it('calls onNext when proceed action is clicked', () => {
    const onNext = vi.fn()

    act(() => {
      root.render(
        createElement(QcSetupSidebar, {
          flowId: 'document_consistency_qc',
          slotState,
          contentDomainGroups,
          currentSelected: new Set(['C0010', 'C0030', 'C0040']),
          draftSelected: new Set(['C0010', 'C0040']),
          isEditing: false,
          onStartEdit: () => {},
          onApply: () => {},
          onCancelEdit: () => {},
          onToggleHeading: () => {},
          onScrollToBlock: () => {},
          focusedBlockId: null,
          nextStatus: 'idle',
          nextError: null,
          onNext,
          isNextDisabled: false,
          canResume: true,
        }),
      )
    })

    const proceedButton = [...container.querySelectorAll('button')].find(
      (button) => button.textContent === '进行质控',
    )
    expect(proceedButton).toBeTruthy()

    act(() => {
      proceedButton?.click()
    })

    expect(onNext).toHaveBeenCalledTimes(1)
  })
})

describe('qc setup sidebar execution state', () => {
  function renderSidebarWithState({
    nextStatus,
    nextError = null,
    isNextDisabled = false,
    onNext = () => {},
  }: {
    nextStatus: 'idle' | 'freezing' | 'error'
    nextError?: string | null
    isNextDisabled?: boolean
    onNext?: () => void
  }) {
    return renderToStaticMarkup(
      createElement(QcSetupSidebar, {
        flowId: 'document_consistency_qc',
        slotState,
        contentDomainGroups,
        currentSelected: new Set(['C0010', 'C0030', 'C0040']),
        draftSelected: new Set(['C0010', 'C0030', 'C0040']),
        isEditing: false,
        onStartEdit: noop,
        onApply: noop,
        onCancelEdit: noop,
        onToggleHeading: noop,
        onScrollToBlock: noop,
        focusedBlockId: null,
        nextStatus,
        nextError,
        onNext,
        isNextDisabled,
        canResume: true,
      }),
    )
  }

  it('shows idle proceed label without waiting hint', () => {
    const html = renderSidebarWithState({ nextStatus: 'idle' })

    expect(html).toContain(`>${QC_SETUP_PROCEED_LABEL}<`)
    expect(html).not.toContain(QC_SETUP_PROCEED_PENDING_LABEL)
    expect(html).not.toContain(QC_SETUP_PROCEED_WAITING_HINT)
    expect(html).not.toContain('已完成')
    expect(html).not.toContain('流程已完成')
  })

  it('shows pending proceed label, waiting hint, and disables the action while freezing', () => {
    const html = renderSidebarWithState({ nextStatus: 'freezing', isNextDisabled: true })

    expect(html).toContain(`>${QC_SETUP_PROCEED_PENDING_LABEL}<`)
    expect(html).toContain(QC_SETUP_PROCEED_WAITING_HINT)
    expect(html).toContain('disabled=""')
    expect(html).not.toContain(`>${QC_SETUP_PROCEED_LABEL}<`)
  })

  it('restores proceed label and hides waiting hint after request error', () => {
    const html = renderSidebarWithState({
      nextStatus: 'error',
      nextError: '候选范围提交失败',
    })

    expect(html).toContain(`>${QC_SETUP_PROCEED_LABEL}<`)
    expect(html).not.toContain(QC_SETUP_PROCEED_PENDING_LABEL)
    expect(html).not.toContain(QC_SETUP_PROCEED_WAITING_HINT)
    expect(html).toContain('候选范围提交失败')
  })
})

describe('qc setup sidebar execution actions', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
  })

  it('does not call onNext again while proceed action is disabled during freezing', () => {
    const onNext = vi.fn()

    act(() => {
      root.render(
        createElement(QcSetupSidebar, {
          flowId: 'document_consistency_qc',
          slotState,
          contentDomainGroups,
          currentSelected: new Set(['C0010', 'C0030', 'C0040']),
          draftSelected: new Set(['C0010', 'C0030', 'C0040']),
          isEditing: false,
          onStartEdit: () => {},
          onApply: () => {},
          onCancelEdit: () => {},
          onToggleHeading: () => {},
          onScrollToBlock: () => {},
          focusedBlockId: null,
          nextStatus: 'freezing',
          nextError: null,
          onNext,
          isNextDisabled: true,
          canResume: true,
        }),
      )
    })

    const proceedButton = container.querySelector('[data-sidebar-main-action]') as HTMLButtonElement
    expect(proceedButton).toBeTruthy()
    expect(proceedButton.disabled).toBe(true)

    act(() => {
      proceedButton.click()
    })

    expect(onNext).not.toHaveBeenCalled()
  })
})
