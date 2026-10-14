// @vitest-environment happy-dom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { toast } from 'sonner'
import { ResultShell } from '@/components/review/result-shell'

vi.mock('sonner', () => ({ toast: { error: vi.fn() } }))
let host: HTMLDivElement, root: Root
const flow = 'document_consistency_qc_test'
const raw = {
  flow_id: 'document_consistency_qc', flow_run_id: flow, capability_id: 'internal_dsur',
  flow_status: 'success', comparison_run_status: 'success', finalization_status: 'completed', fallback_comparison_modes: [],
  findings: [{ finding_id: 'L001', label: 'fail', conclusion: 'Review issue', evidence_refs: [
    { slot_id: 'source', doc_id: 'doc_test', block_id: 'C0031', sentence_id: 'C0031:S001', sentence_alias: 'T0001' },
  ] }],
  scope_results: [{ slot_id: 'source', doc_id: 'doc_test', scope_id: 'HS0001', heading_path: ['Safety'],
    outline_heading_block_id: 'C0030', semantic_module_id: 'clinical_safety', execution_status: 'complete', has_successful_check: true }],
}
const json = (data: unknown) => new Response(JSON.stringify(data), { headers: { 'Content-Type': 'application/json' } })
let reviewResponse: Promise<Response> | undefined
let reportResponse: Promise<Response> | undefined
let annotationResponse: Promise<Response> | undefined
let annotations: Record<string, unknown>
let requests: Array<{ path: string; init?: RequestInit }>

beforeEach(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  host = document.createElement('div'); document.body.append(host); root = createRoot(host)
  requests = []; reviewResponse = undefined; reportResponse = undefined; annotationResponse = undefined; annotations = {}
  vi.spyOn(HTMLElement.prototype, 'scrollIntoView').mockImplementation(() => {})
  vi.spyOn(window, 'matchMedia').mockImplementation(query => ({ matches: true, media: query,
    addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {},
    dispatchEvent: () => true, onchange: null }))
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:qc-report')
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  vi.stubGlobal('fetch', vi.fn(async (path: string, init?: RequestInit) => {
    requests.push({ path, init })
    if (path.endsWith('/qc-report')) return reportResponse ?? new Response('%PDF-test', {
      headers: { 'Content-Type': 'application/pdf', 'Content-Disposition': "attachment; filename*=UTF-8''%E6%8A%A5%E5%91%8A.pdf" },
    })
    if (path.includes('/finding-review')) return init?.method === 'PATCH'
      ? reviewResponse ?? json({ flow_run_id: flow, findings: {} }) : json({ flow_run_id: flow, findings: {} })
    if (path.includes('/source-annotations')) return init?.method === 'PATCH'
      ? annotationResponse! : json({ flow_run_id: flow, annotations })
    if (path.includes('/candidate-scope/document')) return json({ doc_id: 'doc_test', file_name: 'sample.docx', display_name: '很长的文件名.docx', content_blocks: [
      { block_id: 'C0030', kind: 'heading', raw_text: 'Safety', normalized_text: 'Safety', doc_order_index: 0, heading_path: ['Safety'], meta: { heading_level: 1 } },
      { block_id: 'C0031', kind: 'paragraph', raw_text: 'A paragraph.', normalized_text: 'A paragraph.', doc_order_index: 1, heading_path: ['Safety'],
        sentences: [{ sentence_id: 'C0031:S001', raw_text: 'A paragraph.', normalized_text: 'A paragraph.' }] },
    ] })
    if (path.includes('/result?')) return json(raw)
    throw new Error(`unexpected request: ${path}`)
  }))
})
afterEach(() => { act(() => root.unmount()); host.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.clearAllMocks() })

async function mount() {
  await act(async () => root.render(createElement(MemoryRouter, null, createElement(ResultShell, {
    flowRunId: flow, taskDisplayName: 'DSUR', taskRunId: 'task_run_download',
  }))))
}
const button = () => host.querySelector<HTMLButtonElement>('button[data-qc-report-export="true"]')!
const exports = () => requests.filter(request => request.path.endsWith('/qc-report'))

describe('Result report export', () => {
  it.each([320, 839, 840, 1024])('preserves a wrapping header and readable secondary button at %spx', async (width) => {
    vi.mocked(window.matchMedia).mockImplementation(query => ({ matches: width >= 840, media: query,
      addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {},
      dispatchEvent: () => true, onchange: null }))
    await mount()
    const row = button().parentElement!
    expect(row.querySelector('h1')?.textContent).toBe('质控结果')
    expect(row.className).toContain('flex-wrap')
    expect(row.className).toContain('min-w-0')
    expect(button().className).toContain('shrink-0')
    expect(button().className).toContain('whitespace-nowrap')
    expect(host.querySelector('[data-document-identity]')?.className).toContain('break-words')
    expect(host.querySelector('[data-result-findings-panel]')?.className).toContain('min-w-0')
  })

  it('places one secondary action in the findings pane header and none in full-document view', async () => {
    await mount()
    expect(button()).not.toBeNull()
    expect(button().closest('header')?.textContent).toContain('质控结果')
    expect(button().getAttribute('data-variant')).toBe('outline')
    expect(button().getAttribute('aria-label')).toBe('导出报告')
    expect(host.querySelector('[data-result-workspace-toolbar]')?.querySelector('[data-qc-report-export]')).toBeNull()
    expect(host.querySelector('[data-finding-review-card]')?.querySelector('[data-qc-report-export]')).toBeNull()
    act(() => host.querySelector<HTMLButtonElement>('[data-result-show-full-document="true"]')!.click())
    expect(button()).toBeNull()
    act(() => host.querySelector<HTMLButtonElement>('[data-result-show-findings-overview="true"]')!.click())
    expect(host.querySelectorAll('[data-qc-report-export]')).toHaveLength(1)
  })

  it('downloads pending findings without a human-completion gate and restores idle', async () => {
    await mount()
    await act(async () => button().click())
    expect(exports()).toHaveLength(1)
    expect(exports()[0]!.path).toBe('/api/clinical-trial-doc-qc/task-runs/task_run_download/qc-report')
    expect(URL.createObjectURL).toHaveBeenCalledOnce()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:qc-report')
    expect(button().disabled).toBe(false)
  })

  it('waits for an in-flight review save, disables export, and ignores duplicate clicks', async () => {
    await mount()
    let resolve!: (response: Response) => void
    reviewResponse = new Promise(yes => { resolve = yes })
    act(() => host.querySelector<HTMLButtonElement>('button[aria-label="确认"]')!.click())
    await act(async () => { button().click(); button().click() })
    expect(exports()).toHaveLength(0)
    expect(button().disabled).toBe(true)
    expect(button().getAttribute('aria-busy')).toBe('true')
    await act(async () => resolve(json({ flow_run_id: flow, findings: {} })))
    expect(exports()).toHaveLength(1)
    expect(button().disabled).toBe(false)
  })

  it('commits the current unblurred note and does not request a report before save succeeds', async () => {
    await mount()
    let resolve!: (response: Response) => void
    reviewResponse = new Promise(yes => { resolve = yes })
    act(() => host.querySelector<HTMLButtonElement>('button[aria-label="添加笔记"]')!.click())
    const field = host.querySelector('textarea')!
    act(() => {
      field.focus()
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(field, '未 blur 的笔记')
      field.dispatchEvent(new Event('input', { bubbles: true }))
    })
    await act(async () => button().click())
    const save = requests.find(request => request.init?.method === 'PATCH')!
    expect(JSON.parse(String(save.init?.body)).note).toBe('未 blur 的笔记')
    expect(exports()).toHaveLength(0)
    await act(async () => resolve(json({ flow_run_id: flow, findings: {} })))
    expect(exports()).toHaveLength(1)
  })

  it('never downloads stale state after a save failure', async () => {
    await mount()
    reviewResponse = Promise.resolve(new Response(JSON.stringify({ message: 'SECRET save error' }), { status: 500 }))
    await act(async () => host.querySelector<HTMLButtonElement>('button[aria-label="确认"]')!.click())
    await act(async () => button().click())
    expect(exports()).toHaveLength(0)
    expect(toast.error).toHaveBeenCalledWith('保存失败，暂无法导出报告。')
    expect(button().disabled).toBe(false)
  })

  it('does not treat a successful mark as a retry of a failed decision save', async () => {
    await mount()
    reviewResponse = Promise.resolve(new Response(JSON.stringify({ message: 'failed' }), { status: 500 }))
    await act(async () => host.querySelector<HTMLButtonElement>('button[aria-label="确认"]')!.click())
    reviewResponse = undefined
    await act(async () => host.querySelector<HTMLButtonElement>('button[aria-label="标记提醒"]')!.click())
    await act(async () => button().click())
    expect(exports()).toHaveLength(0)
    expect(toast.error).toHaveBeenCalledWith('保存失败，暂无法导出报告。')
  })

  it.each([['comment', false], ['comment', true], ['edit', false], ['edit', true]] as const)('preserves unblurred %s drafts and waits for both save owners (failure=%s)', async (kind, failAnnotation) => {
    const annotation = { annotation_id: 'ann_item', kind, content: kind === 'comment' ? 'saved comment' : undefined,
      replacement_text: kind === 'edit' ? 'replacement' : undefined,
      anchor: { slot_id: 'source', doc_id: 'doc_test', block_id: 'C0031', sentence_id: 'C0031:S001' },
      range: { start_offset: 0, end_offset: 1 }, created_at: '2026-10-10T00:00:00Z', updated_at: '2026-10-10T00:00:00Z' }
    annotations = { ann_item: annotation }
    await mount()
    let finishReview!: (value: Response) => void, finishAnnotation!: (value: Response) => void
    reviewResponse = new Promise(yes => { finishReview = yes })
    annotationResponse = new Promise(yes => { finishAnnotation = yes })
    act(() => host.querySelector<HTMLButtonElement>('button[aria-label="确认"]')!.click())
    act(() => {
      const marker = host.querySelector<HTMLElement>(kind === 'comment'
        ? '[data-source-comment-icon="true"]' : '[data-source-edit-group="true"]')!
      if (kind === 'comment') marker.click()
      else marker.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
    })
    const field = document.querySelector<HTMLInputElement | HTMLTextAreaElement>(kind === 'comment'
      ? '[data-source-comment-popover] textarea' : '[data-source-edit-popover] input')!
    act(() => {
      field.focus()
      Object.getOwnPropertyDescriptor(kind === 'comment' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype,
        'value')!.set!.call(field, 'new unsaved annotation')
      field.dispatchEvent(new Event('input', { bubbles: true }))
      button().dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }))
    })
    expect(document.querySelector(kind === 'comment' ? '[data-source-comment-popover]' : '[data-source-edit-popover]')).not.toBeNull()
    await act(async () => button().click())
    expect(requests.some(request => request.path.includes('/source-annotations')
      && JSON.parse(String(request.init?.body ?? '{}'))[kind === 'comment' ? 'content' : 'replacement_text'] === 'new unsaved annotation')).toBe(true)
    expect(exports()).toHaveLength(0)
    await act(async () => finishReview(json({ flow_run_id: flow, findings: {} })))
    expect(exports()).toHaveLength(0)
    await act(async () => finishAnnotation(failAnnotation
      ? new Response(JSON.stringify({ message: 'SECRET annotation failure' }), { status: 500 })
      : json({ ...annotation, [kind === 'comment' ? 'content' : 'replacement_text']: 'new unsaved annotation' })))
    expect(exports()).toHaveLength(failAnnotation ? 0 : 1)
    if (failAnnotation) expect(toast.error).toHaveBeenCalledWith('保存失败，暂无法导出报告。')
    expect(button().disabled).toBe(false)
    expect(host.querySelector(kind === 'comment'
      ? '[data-source-annotation-label="comment"]' : '[data-source-annotation-label="revision"]')?.textContent).toContain('1')
  })

  it('discards an old download response after switching TaskRun', async () => {
    await mount()
    let finish!: (value: Response) => void
    reportResponse = new Promise(yes => { finish = yes })
    await act(async () => button().click())
    expect(button().disabled).toBe(true)
    await act(async () => root.render(createElement(MemoryRouter, null, createElement(ResultShell, {
      flowRunId: flow, taskDisplayName: 'DSUR', taskRunId: 'task_run_other',
    }))))
    await act(async () => finish(new Response('%PDF-old')))
    expect(URL.createObjectURL).not.toHaveBeenCalled()
    expect(button().disabled).toBe(false)
  })

  it('uses a generic message on a failed network request and allows retry', async () => {
    await mount()
    vi.mocked(fetch).mockRejectedValueOnce(new Error('SECRET network'))
    await act(async () => button().click())
    expect(toast.error).toHaveBeenCalledWith('报告生成失败，请稍后重试。')
    expect(button().disabled).toBe(false)
    await act(async () => button().click())
    expect(URL.createObjectURL).toHaveBeenCalledOnce()
  })

  it.each([[409, '报告状态正在更新，请稍后重试。'], [400, '当前质控结果暂无法生成报告。'],
    [500, '报告生成失败，请稍后重试。']])('shows safe HTTP %s feedback and restores the button', async (status, message) => {
    await mount()
    reportResponse = Promise.resolve(new Response(JSON.stringify({ message: 'SECRET C:/private/path' }), { status }))
    await act(async () => button().click())
    expect(toast.error).toHaveBeenCalledWith(message)
    expect(button().disabled).toBe(false)
    expect(URL.createObjectURL).not.toHaveBeenCalled()
  })
})
