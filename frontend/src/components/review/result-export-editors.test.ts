// @vitest-environment happy-dom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { ResultSaveContext } from '@/components/review/result-save-context'
import { ResultSaveCoordinator } from '@/lib/result-save-coordinator'
import { SourceCommentPopover } from '@/components/review/source-comment-popover'
import { SourceEditPopover } from '@/components/review/source-edit-popover'
import { FindingReviewCard } from '@/components/review/finding-review-card'
import { buildFindingPresentation } from '@/lib/finding-review-presentation'

let host: HTMLDivElement, root: Root, coordinator: ResultSaveCoordinator
beforeEach(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true
  host = document.createElement('div'); document.body.append(host)
  root = createRoot(host); coordinator = new ResultSaveCoordinator()
})
afterEach(() => { act(() => root.unmount()); host.remove() })

function typeInto(field: HTMLInputElement | HTMLTextAreaElement, value: string) {
  act(() => {
    const prototype = field instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype
    Object.getOwnPropertyDescriptor(prototype, 'value')!.set!.call(field, value)
    field.dispatchEvent(new Event('input', { bubbles: true }))
  })
}

describe('Export commits registered Result editors', () => {
  it.each(['comment', 'edit'])('commits the current unblurred %s using its existing save callback', async (kind) => {
    const saved: string[] = []
    act(() => root.render(createElement(ResultSaveContext.Provider, { value: coordinator },
      kind === 'comment' ? createElement(SourceCommentPopover, {
        mode: 'create', top: 0, left: 0, onCancel: () => {}, onSave: async content => { saved.push(content) },
      }) : createElement(SourceEditPopover, {
        mode: 'create', top: 0, left: 0, onCancel: () => {}, onSave: async content => { saved.push(content) },
      }),
    )))
    const field = host.querySelector<HTMLInputElement | HTMLTextAreaElement>('textarea,input')!
    field.focus(); typeInto(field, '刚输入的内容')
    expect(document.activeElement).toBe(field)
    expect(saved).toEqual([])
    await act(() => coordinator.flush())
    expect(saved).toEqual(['刚输入的内容'])
  })

  it('commits an unblurred Finding note before export', async () => {
    const patches: unknown[] = []
    act(() => root.render(createElement(ResultSaveContext.Provider, { value: coordinator },
      createElement(FindingReviewCard, {
        presentation: buildFindingPresentation({ findingId: 'L001', label: 'fail', conclusion: 'Issue', evidenceRefs: [] }, null),
        saving: false, onSelectFinding: () => {},
        onPatchFindingReview: async (_id, patch) => { patches.push(patch) },
      }),
    )))
    act(() => host.querySelector<HTMLButtonElement>('button[aria-label="添加笔记"]')!.click())
    const field = host.querySelector('textarea')!
    field.focus(); typeInto(field, '尚未保存的笔记')
    await act(() => coordinator.flush())
    expect(patches).toEqual([{ note: '尚未保存的笔记' }])
  })

  it('does not resubmit an editor whose save is already in flight', async () => {
    let calls = 0
    act(() => root.render(createElement(ResultSaveContext.Provider, { value: coordinator },
      createElement(SourceCommentPopover, {
        mode: 'edit', top: 0, left: 0, initialContent: 'saved', saving: true,
        onCancel: () => {}, onSave: () => { calls++ },
      }),
    )))
    await act(() => coordinator.flush())
    expect(calls).toBe(0)
  })
})
