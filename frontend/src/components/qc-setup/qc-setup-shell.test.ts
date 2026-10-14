import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { Window } from 'happy-dom'
import { compile } from 'tailwindcss'

import { beforeAll, describe, expect, it } from 'vitest'

import { QcSetupShellLoaded } from '@/components/qc-setup/qc-setup-shell'
import {
  QC_SETUP_PROCEED_LABEL,
  QC_SETUP_PROCEED_PENDING_LABEL,
  QC_SETUP_PROCEED_WAITING_HINT,
  QC_FUNCTION_LABEL,
} from '@/lib/launcher-presentation'
import type { CandidateScopeContentDomainGroup, CandidateScopeFlowState, CandidateScopeSlotState, DocumentTypeDiagnostic, SlotReviewState } from '@/types/candidate-scope'
import type { DocumentView } from '@/types/document-review'
import type { TaskRunState } from '@/types/task-run'
import {
  FLOW_FAILED_TASK_STATE,
  PAUSED_TASK_STATE,
  SUCCESS_NO_RESULT_TASK_STATE,
  SUCCESS_RESULT_TASK_STATE,
} from '@/test-fixtures/task-run-state'

const document: DocumentView = {
  docId: 'doc_test',
  fileName: 'showcase.docx',
  displayName: '艾美妥珠单抗 研发期间安全性更新报告#2_fe_stub.docx',
  blocks: [
    {
      blockId: 'block_1',
      kind: 'paragraph',
      docOrderIndex: 0,
      headingPath: [],
      displayText: 'Sample paragraph',
    },
  ],
}

const ibDocument: DocumentView = {
  docId: 'doc_ib',
  fileName: 'ib.docx',
  displayName: 'VT8802 艾美妥珠单抗研究者手册 V1.3 2024.03.15.docx',
  blocks: [],
}

const activeSlot: CandidateScopeSlotState = {
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
}

const contentDomainGroups: CandidateScopeContentDomainGroup[] = [
  {
    contentDomainId: 'clinical_safety',
    displayLabel: '临床安全性',
    filterJobIds: ['dsur_clinical_safety', 'dsur_overview'],
  },
]

const flowState: CandidateScopeFlowState = {
  flowId: 'document_consistency_qc',
  flowRunId: 'document_consistency_qc_20260910_150115_296031Z',
  capabilityId: 'internal_dsur',
  capabilityTitle: '试验药临床安全性核查',
  flowStatus: 'paused_at_candidate_scope',
  canResume: true,
  contentDomainGroups,
  slots: [activeSlot],
}

const pausedTaskState: TaskRunState = PAUSED_TASK_STATE

const multiFileFlowState: CandidateScopeFlowState = {
  ...flowState,
  capabilityId: 'dsur_updated_ib',
  capabilityTitle: 'DSUR↔IB',
  contentDomainGroups: [
    {
      contentDomainId: 'clinical_safety',
      displayLabel: '临床安全性',
      filterJobIds: [
        'dsur_clinical_safety',
        'dsur_overview',
        'ib_clinical_safety',
        'ib_overview',
      ],
    },
  ],
  slots: [
    { ...activeSlot, slotId: 'source_a' },
    {
      slotId: 'source_b',
      docId: 'doc_ib',
      automaticAnchorBlockIds: [],
      currentAnchorBlockIds: [],
      headings: [],
    },
  ],
}

const activeReview: SlotReviewState = {
  currentSelected: new Set(['C0010', 'C0030']),
  draftSelected: new Set(['C0010', 'C0030']),
  isEditing: false,
}

const noop = () => {}

const documentTypeLabel = 'DSUR'

function renderShell(
  isEditing: boolean,
  nextStatus: 'idle' | 'freezing' | 'error' = 'idle',
  options: {
    flowState?: CandidateScopeFlowState
    documentsBySlotId?: Record<string, DocumentView>
    activeSlot?: CandidateScopeSlotState
    resultAvailable?: boolean
    taskState?: TaskRunState
  } = {},
) {
  const resolvedFlowState = options.flowState ?? flowState
  const resolvedActiveSlot = options.activeSlot ?? activeSlot
  return renderToStaticMarkup(
    createElement(MemoryRouter, null, createElement(QcSetupShellLoaded, {
      taskDisplayName: documentTypeLabel,
      document,
      documentsBySlotId: options.documentsBySlotId ?? { source: document },
      documentStatus: 'ready',
      documentError: null,
      flowState: resolvedFlowState,
      activeSlot: resolvedActiveSlot,
      activeReview: {
        ...activeReview,
        isEditing,
      },
      focusedBlockId: null,
      onClearFocusedBlock: noop,
      onSelectSlot: noop,
      onStartEdit: noop,
      onApply: noop,
      onCancelEdit: noop,
      onToggleHeading: noop,
      onScrollToBlock: noop,
      nextStatus,
      nextError: null,
      onNext: noop,
      taskState: options.taskState ?? {
        ...pausedTaskState,
        resultAvailable: options.resultAvailable ?? false,
      },
      isNextDisabled: isEditing || nextStatus === 'freezing',
    })),
  )
}

let paneCss: string
beforeAll(async () => {
  const html = renderShell(false)
  const paneClasses = [
    html.match(/^<div class="([^"]*)"/)?.[1],
    html.match(/<main class="([^"]*)"/)?.[1],
    html.match(/<aside class="([^"]*)"/)?.[1],
  ].flatMap(className => className?.split(' ') ?? [])
    // Borders emit a property-layer prelude unsupported by Happy DOM; sizing does not.
    .filter(className => !className.startsWith('border'))
  const compiler = await compile('@theme inline { --spacing: 0.25rem; } @tailwind utilities;')
  paneCss = compiler.build(paneClasses)
})

describe('qc setup slot document-type warnings', () => {
  it.each(['DSUR', 'CSR', 'IB'] as const)('uses the diagnostic expected type %s for both advisory statuses', (expectedDocumentType) => {
    for (const status of ['mismatch', 'uncertain'] as const) {
      const slot = { ...activeSlot, documentTypeDiagnostic: {
        status, expectedDocumentType, reason: 'doc_type_conflict',
      } satisfies DocumentTypeDiagnostic }
      const browser = new Window()
      browser.document.body.innerHTML = renderShell(false, 'idle', {
        flowState: { ...flowState, slots: [slot] }, activeSlot: slot,
      })
      const identity = browser.document.querySelector('[data-document-identity]')!
      expect(identity.nextElementSibling?.textContent).toBe(`⚠ 请确认上传文件是否为 ${expectedDocumentType}。`)
      expect(browser.document.body.textContent).not.toContain('doc_type_conflict')
      const run = browser.document.querySelector<HTMLButtonElement>('[data-sidebar-main-action]')!
      expect(run.disabled).toBe(false)
    }
  })

  it.each([undefined, { status: 'match', expectedDocumentType: 'DSUR' } satisfies DocumentTypeDiagnostic])('renders no warning for missing or matching diagnostics: %s', (diagnostic) => {
    const slot = { ...activeSlot, documentTypeDiagnostic: diagnostic }
    const html = renderShell(false, 'idle', { flowState: { ...flowState, slots: [slot] }, activeSlot: slot })
    expect(html).not.toContain('请确认上传文件是否为')
  })

  it.each(['mismatch', 'uncertain'] as const)('places the %s warning only below its affected document in a dual-document task', (status) => {
    const slotA = { ...multiFileFlowState.slots[0]!, documentTypeDiagnostic: {
      status, expectedDocumentType: 'DSUR',
    } satisfies DocumentTypeDiagnostic }
    const slotB = { ...multiFileFlowState.slots[1]!, documentTypeDiagnostic: {
      status: 'match', expectedDocumentType: 'IB',
    } satisfies DocumentTypeDiagnostic }
    for (const activeSlot of [slotA, slotB]) {
      const browser = new Window()
      browser.document.body.innerHTML = renderShell(false, 'idle', {
        flowState: { ...multiFileFlowState, slots: [slotA, slotB] }, activeSlot,
        documentsBySlotId: { source_a: document, source_b: ibDocument },
      })
      const fileA = [...browser.document.querySelectorAll('button')].find(button => button.textContent === document.displayName)!
      const fileB = [...browser.document.querySelectorAll('button')].find(button => button.textContent === ibDocument.displayName)!
      expect(fileA.nextElementSibling?.textContent).toBe('⚠ 请确认上传文件是否为 DSUR。')
      expect(fileB.parentElement?.textContent).not.toContain('请确认上传文件是否为')
      expect(browser.document.body.textContent?.match(/请确认上传文件是否为/g)).toHaveLength(1)
    }
  })
})

describe('qc setup shell edit-mode layout', () => {
  it('places the flexible document left and the desktop fixed-width operation panel right', () => {
    for (const isEditing of [false, true]) {
      const html = renderShell(isEditing)
      expect(html.indexOf('<main')).toBeLessThan(html.indexOf('<aside'))
      const operationClasses = html.match(/<aside class="([^"]*)"/)?.[1]?.split(' ')
      const documentClasses = html.match(/<main class="([^"]*)"/)?.[1]?.split(' ')
      expect(operationClasses).toEqual(expect.arrayContaining(['min-[840px]:w-96', 'min-[840px]:shrink-0', 'max-[840px]:min-w-0', 'border-l']))
      expect(operationClasses).not.toContain('w-96')
      expect(operationClasses).not.toContain('shrink-0')
      expect(operationClasses).not.toContain('border-r')
      expect(documentClasses).toEqual(expect.arrayContaining(['min-w-0', 'flex-1']))
    }
  })

  it.each([
    { width: 640, narrow: true },
    { width: 839.5, narrow: true },
    { width: 840, narrow: false },
    { width: 1024, narrow: false },
  ])('applies pane width and height containment at $width px in view and edit modes', ({ width, narrow }) => {
    // Compile the actual rendered classes; fresh windows avoid Happy DOM's media-style cache.
    const browser = new Window({ width, height: 800 })
    const style = browser.document.createElement('style')
    style.textContent = paneCss
    browser.document.head.append(style)
    for (const isEditing of [false, true]) {
      browser.document.body.innerHTML = renderShell(isEditing)
      const workspace = browser.document.body.firstElementChild!
      const documentPane = workspace.firstElementChild!
      const setupPane = workspace.lastElementChild!
      const workspaceStyle = browser.getComputedStyle(workspace)
      const documentStyle = browser.getComputedStyle(documentPane)
      const setupStyle = browser.getComputedStyle(setupPane)

      expect(workspace.children).toHaveLength(2)
      expect(documentPane.tagName).toBe('MAIN')
      expect(setupPane.tagName).toBe('ASIDE')
      expect(documentPane.querySelector('.document-surface')).not.toBeNull()
      expect(setupPane.querySelector('[data-function-card]')).not.toBeNull()
      expect(documentStyle.display).toBe('flex')
      expect(setupStyle.display).toBe('flex')
      expect(documentStyle.minWidth).toBe('0px')
      expect(setupStyle.minWidth).toBe(narrow ? '0px' : '')
      expect(setupPane.classList.contains('border-l')).toBe(true)
      expect(workspaceStyle.display).toBe(narrow ? 'grid' : 'flex')
      expect(workspaceStyle.gridTemplateColumns).toBe(narrow ? 'minmax(0,1fr) minmax(0,1fr)' : '')
      expect(workspaceStyle.gridTemplateRows).toBe(narrow ? 'minmax(0,1fr)' : '')
      expect(workspaceStyle.height).toBe('100%')
      expect(workspaceStyle.minHeight).toBe('0px')
      expect(workspaceStyle.overflow).toBe('hidden')
      expect(setupStyle.height).toBe('100%')
      expect(setupStyle.minHeight).toBe('0px')
      if (narrow) {
        expect(['', 'auto']).toContain(setupStyle.width)
        expect(setupStyle.flexShrink).not.toBe('0')
      } else {
        expect(setupStyle.width).toBe('calc(4px * 96)')
        expect(setupStyle.flexShrink).toBe('0')
        expect(documentStyle.flexGrow).toBe('1')
        expect(documentStyle.flexBasis).toBe('0%')
      }
    }
  })

  it('keeps document reader as the sole main child regardless of edit mode', () => {
    const idleHtml = renderShell(false)
    const editHtml = renderShell(true)

    expect(idleHtml).toMatch(/<main[\s\S]*document-surface[\s\S]*<\/main>/)
    expect(editHtml).toMatch(/<main[\s\S]*document-surface[\s\S]*<\/main>/)
  })

  it('shows filename, qc function, and candidate chapter hierarchy', () => {
    const html = renderShell(false)
    const identity = html.match(/<p[^>]*data-document-identity="true"[^>]*>[\s\S]*?<\/p>/)?.[0]

    expect(html).toContain('data-task-page-title="true"')
    expect(html).toContain('>质控功能<')
    expect(html).toContain('data-document-identity="true"')
    expect(html).toContain(`DSUR · ${document.displayName}`)
    expect(identity).toBeTruthy()
    expect(identity).toContain('whitespace-normal')
    expect(identity).toContain('break-words')
    expect(identity).not.toMatch(/truncate|whitespace-nowrap|line-clamp|break-all|overflow-wrap:anywhere/)
    expect(identity).not.toMatch(/\bgrid\b|grid-cols|\bflex\b|text-indent|\bindent-|\bpl-/)
    expect(identity).not.toContain('data-document-identity-prefix')
    expect(identity).not.toContain('data-document-identity-filename')
    expect(identity).toContain(`>DSUR · ${document.displayName}</p>`)
    expect(html).not.toContain('DSUR 质控')
    expect(html).not.toContain('DSUR质控')
    expect(html).not.toContain('>功能<')
    expect(html).not.toContain('border-[#F0F0F0]')
    expect(html).toContain(QC_FUNCTION_LABEL)
    expect(html).toContain('data-function-card')
    expect(html).toContain('候选章节')
    expect(html).toContain('临床安全性')
    expect(html).not.toContain('候选核查范围')
  })

  it('does not render Product Task or capability titles inside the Flow workspace', () => {
    const productTaskTitle = 'IB 撰写准确性与一致性'
    // Negative fixture: an obsolete capability title must not appear in the workspace.
    const capabilityTitle = '内部 IB 一致性检查'
    const html = renderShell(false, 'idle', {
      flowState: {
        ...flowState,
        capabilityTitle,
      },
    })

    expect(html).not.toContain(productTaskTitle)
    expect(html).not.toContain(capabilityTitle)
  })

  it('shows labeled filenames for multi-file capabilities', () => {
    const html = renderShell(false, 'idle', {
      flowState: multiFileFlowState,
      documentsBySlotId: {
        source_a: document,
        source_b: ibDocument,
      },
      activeSlot: { ...activeSlot, slotId: 'source_a' },
    })

    expect(html).toContain('DSUR')
    expect(html).toContain(document.displayName)
    expect(html).toContain('IB')
    expect(html).toContain(ibDocument.displayName)
  })

  it('shows only the primary proceed action in the footer when not editing', () => {
    const html = renderShell(false)
    expect(html).toContain('进行质控')
    expect(html).not.toContain('调整候选章节')
    expect(html).toContain('调整')
  })

  it('shows card-local apply controls and keeps task-level proceed action in edit mode', () => {
    const html = renderShell(true)
    expect(html).toContain('应用调整')
    expect(html).toContain('取消')
    expect(html).toContain('data-candidate-chapter-edit-footer')
    expect(html).toContain('data-sidebar-task-footer')
    expect(html).toContain('>进行质控<')

    const editFooterIndex = html.indexOf('data-candidate-chapter-edit-footer')
    const taskFooterIndex = html.indexOf('data-sidebar-task-footer')
    expect(editFooterIndex).toBeLessThan(taskFooterIndex)
  })

  it('uses refined sidebar surface styling without a qc setup page title', () => {
    const html = renderShell(false)

    expect(html).toContain('launcher-tech-bg')
    expect(html).toContain('bg-white')
    expect(html).toContain('border-[#D8DEE7]')
    expect(html).not.toContain('质控配置')
    expect(html).not.toContain('配置页')
    expect(html).not.toContain('border-l-blue-300')
  })

  it('shows qc execution pending copy without replacing the document reader', () => {
    const html = renderShell(false, 'freezing')

    expect(html).toContain(QC_SETUP_PROCEED_PENDING_LABEL)
    expect(html).toContain(QC_SETUP_PROCEED_WAITING_HINT)
    expect(html).not.toContain('已完成')
    expect(html).not.toContain('流程已完成')
    expect(html).toMatch(/<main[\s\S]*document-surface[\s\S]*<\/main>/)
  })

  it('does not show qc setup completed placeholder copy', () => {
    const html = renderShell(false, 'idle')

    expect(html).toContain(QC_SETUP_PROCEED_LABEL)
    expect(html).not.toContain('已完成')
    expect(html).not.toContain('流程已完成。')
    expect(html).not.toContain('>查看结果<')
  })

  it('shows historical read-only hint when canResume is false', () => {
    const html = renderToStaticMarkup(
      createElement(MemoryRouter, null, createElement(QcSetupShellLoaded, {
        taskDisplayName: documentTypeLabel,
        document,
        documentsBySlotId: { source: document },
        documentStatus: 'ready',
        documentError: null,
        flowState: { ...flowState, canResume: false, flowStatus: 'success' },
        activeSlot,
        activeReview,
        focusedBlockId: null,
        onClearFocusedBlock: noop,
        onSelectSlot: noop,
        onStartEdit: noop,
        onApply: noop,
        onCancelEdit: noop,
        onToggleHeading: noop,
        onScrollToBlock: noop,
        nextStatus: 'idle',
        nextError: null,
        onNext: noop,
        taskState: {
          ...SUCCESS_RESULT_TASK_STATE,
        },
        isNextDisabled: true,
      })),
    )

    expect(html).toContain('当前页面仅供历史查看')
    expect(html).toContain('document-surface')
    expect(html).not.toContain('>查看结果<')
  })

  it('hides historical Result link when prerequisites are absent', () => {
    const html = renderShell(false, 'idle', {
      flowState: { ...flowState, canResume: false, flowStatus: 'success' },
      taskState: SUCCESS_NO_RESULT_TASK_STATE,
    })
    expect(html).not.toContain('>查看结果<')
  })

  it('shows downstream Flow failure without presenting it as Product failure', () => {
    const html = renderShell(false, 'idle', {
      flowState: { ...flowState, canResume: false, flowStatus: 'failed' },
      taskState: {
        ...FLOW_FAILED_TASK_STATE,
      },
    })

    expect(html).toContain('核查执行失败')
    expect(html).not.toContain('Product Start')
    expect(html).not.toContain('>查看结果<')
  })

  it('allows Result entry for partial outcome when Product Result is available', () => {
    const html = renderShell(false, 'idle', {
      flowState: { ...flowState, canResume: false, flowStatus: 'partial' },
      taskState: {
        ...SUCCESS_RESULT_TASK_STATE,
        flowOutcome: 'partial',
      },
    })

    expect(html).not.toContain('>查看结果<')
  })

  it('does not interpret flow_execution_requested as a live running state', () => {
    const html = renderShell(false, 'idle', {
      flowState: { ...flowState, canResume: false, flowStatus: 'success' },
      taskState: {
        ...SUCCESS_RESULT_TASK_STATE,
      },
    })

    expect(html).not.toContain('正在运行')
    expect(html).not.toContain('仍在处理')
  })
})
