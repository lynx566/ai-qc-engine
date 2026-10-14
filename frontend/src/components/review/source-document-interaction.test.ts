// @vitest-environment happy-dom

import { createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { act } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { SourceDocumentInteraction } from '@/components/review/source-document-interaction'
import { SENTENCE_RANGE_ENABLED_ATTRIBUTE } from '@/lib/source-text-selection'
import type { SourceAnnotation } from '@/types/source-annotation'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true

const anchor = {
  slotId: 'source',
  docId: 'doc-a',
  blockId: 'B1',
  sentenceId: 'B1:S1',
}

const commentAnnotation: SourceAnnotation = {
  annotationId: 'ann-comment',
  anchor,
  kind: 'comment',
  range: { startOffset: 0, endOffset: 6 },
  content: 'old note',
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
}

const editAnnotation: SourceAnnotation = {
  annotationId: 'ann-edit',
  anchor,
  kind: 'edit',
  range: { startOffset: 0, endOffset: 6 },
  replacementText: 'old',
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
}

let container: HTMLDivElement
let root: ReturnType<typeof createRoot>

beforeEach(() => {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  vi.spyOn(Range.prototype, 'getBoundingClientRect').mockReturnValue({
    x: 0,
    y: 0,
    top: 0,
    left: 0,
    bottom: 20,
    right: 100,
    width: 100,
    height: 20,
    toJSON: () => ({}),
  } as DOMRect)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  document.body.querySelector('[data-source-comment-popover="true"]')?.parentElement?.remove()
  document.body.querySelector('[data-source-edit-popover="true"]')?.parentElement?.remove()
  vi.restoreAllMocks()
})

function setNativeValue(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
  const proto = element instanceof HTMLTextAreaElement
    ? HTMLTextAreaElement.prototype
    : HTMLInputElement.prototype
  Object.getOwnPropertyDescriptor(proto, 'value')?.set?.call(element, value)
  element.dispatchEvent(new Event('input', { bubbles: true }))
}

function selectSentenceText() {
  const textNode = container.querySelector('[data-sentence-id="B1:S1"]')?.firstChild as Text
  const range = document.createRange()
  range.setStart(textNode, 0)
  range.setEnd(textNode, 6)
  const selection = window.getSelection()
  selection?.removeAllRanges()
  selection?.addRange(range)
  act(() => {
    container
      .querySelector('[data-source-document-interaction="true"]')
      ?.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
  })
}

describe('SourceDocumentInteraction', () => {
  it('opens the selection toolbar for a valid in-root sentence selection', () => {
    act(() =>
      root.render(
        createElement(
          SourceDocumentInteraction,
          {
            sourceAnnotations: new Map(),
            resolveSentenceAnchor: () => anchor,
          },
          () =>
            createElement(
              'span',
              {
                'data-sentence-id': 'B1:S1',
                [SENTENCE_RANGE_ENABLED_ATTRIBUTE]: 'true',
              },
              'Target sentence.',
            ),
        ),
      ),
    )

    selectSentenceText()
    expect(container.textContent).toContain('修订')
    expect(container.textContent).toContain('批注')
    expect(container.textContent).not.toContain('高亮')
  })

  it('creates a comment and a proposed revision from the shared toolbar', async () => {
    const onCreateComment = vi.fn(async () => {})
    const onCreateEdit = vi.fn(async () => {})

    act(() =>
      root.render(
        createElement(
          SourceDocumentInteraction,
          {
            sourceAnnotations: new Map(),
            resolveSentenceAnchor: (identity) => ({
              ...anchor,
              sentenceId: identity.sentenceId,
              slotId: identity.slotId ?? anchor.slotId,
              docId: identity.docId ?? anchor.docId,
            }),
            onCreateComment,
            onCreateEdit,
          },
          () =>
            createElement(
              'span',
              {
                'data-sentence-id': 'B1:S1',
                'data-slot-id': 'source',
                'data-doc-id': 'doc-a',
                [SENTENCE_RANGE_ENABLED_ATTRIBUTE]: 'true',
              },
              'Target sentence.',
            ),
        ),
      ),
    )

    selectSentenceText()
    act(() => {
      [...container.querySelectorAll('button')]
        .find((button) => button.textContent === '批注')
        ?.click()
    })
    const commentInput = document.body.querySelector(
      '[data-source-comment-popover="true"] textarea',
    ) as HTMLTextAreaElement
    act(() => {
      setNativeValue(commentInput, 'new comment')
    })
    await act(async () => {
      ;[...document.body.querySelectorAll('[data-source-comment-popover="true"] button')]
        .find((button) => button.textContent === '保存')
        ?.click()
    })
    expect(onCreateComment).toHaveBeenCalledWith({
      anchor,
      range: { startOffset: 0, endOffset: 6 },
      content: 'new comment',
    })

    selectSentenceText()
    act(() => {
      [...container.querySelectorAll('button')]
        .find((button) => button.textContent === '修订')
        ?.click()
    })
    const editInput = document.body.querySelector(
      '[data-source-edit-popover="true"] input',
    ) as HTMLInputElement
    act(() => {
      setNativeValue(editInput, '建议修改')
    })
    await act(async () => {
      ;[...document.body.querySelectorAll('[data-source-edit-popover="true"] button')]
        .find((button) => button.textContent === '保存')
        ?.click()
    })
    expect(onCreateEdit).toHaveBeenCalledWith({
      anchor,
      range: { startOffset: 0, endOffset: 6 },
      replacementText: '建议修改',
    })
  })

  it('updates and deletes visible comments and revisions without highlight-creation UI', async () => {
    const onUpdateComment = vi.fn(async () => {})
    const onDeleteComment = vi.fn(async () => {})
    const onUpdateEdit = vi.fn(async () => {})
    const onDeleteEdit = vi.fn(async () => {})
    const onDeleteHighlight = vi.fn(async () => {})

    act(() =>
      root.render(
        createElement(
          SourceDocumentInteraction,
          {
            sourceAnnotations: new Map([
              [commentAnnotation.annotationId, commentAnnotation],
              [editAnnotation.annotationId, editAnnotation],
            ]),
            resolveSentenceAnchor: () => anchor,
            onUpdateComment,
            onDeleteComment,
            onUpdateEdit,
            onDeleteEdit,
            onDeleteHighlight,
          },
          (handlers) =>
            createElement(
              'div',
              null,
              createElement('span', {
                'data-sentence-id': 'B1:S1',
                [SENTENCE_RANGE_ENABLED_ATTRIBUTE]: 'true',
              }, 'Target sentence.'),
              createElement('button', {
                'data-source-comment-icon': 'true',
                onClick: (event: { currentTarget: HTMLElement }) => {
                  handlers.onCommentIconClick('ann-comment', event.currentTarget)
                },
              }, 'open-comment'),
              createElement('button', {
                'data-source-edit-group': 'true',
                onClick: (event: { currentTarget: HTMLElement }) => {
                  handlers.onEditInlineClick('ann-edit', event.currentTarget)
                },
              }, 'open-edit'),
              createElement('button', {
                'data-source-persisted-mark': 'true',
                onClick: (event: { currentTarget: HTMLElement }) => {
                  handlers.onPersistedMarkClick('ann-hl', event.currentTarget)
                },
              }, 'open-highlight'),
            ),
        ),
      ),
    )

    act(() => {
      [...container.querySelectorAll('button')]
        .find((button) => button.textContent === 'open-comment')
        ?.click()
    })
    const commentInput = document.body.querySelector(
      '[data-source-comment-popover="true"] textarea',
    ) as HTMLTextAreaElement
    act(() => {
      setNativeValue(commentInput, 'updated')
    })
    await act(async () => {
      ;[...document.body.querySelectorAll('[data-source-comment-popover="true"] button')]
        .find((button) => button.textContent === '保存')
        ?.click()
    })
    expect(onUpdateComment).toHaveBeenCalledWith({
      annotationId: 'ann-comment',
      content: 'updated',
    })

    act(() => {
      [...container.querySelectorAll('button')]
        .find((button) => button.textContent === 'open-comment')
        ?.click()
    })
    await act(async () => {
      ;[...document.body.querySelectorAll('[data-source-comment-popover="true"] button')]
        .find((button) => button.textContent === '删除')
        ?.click()
    })
    expect(onDeleteComment).toHaveBeenCalledWith('ann-comment')

    act(() => {
      [...container.querySelectorAll('button')]
        .find((button) => button.textContent === 'open-edit')
        ?.click()
    })
    await act(async () => {
      ;[...document.body.querySelectorAll('[data-source-edit-popover="true"] button')]
        .find((button) => button.textContent === '删除')
        ?.click()
    })
    expect(onDeleteEdit).toHaveBeenCalledWith('ann-edit')

    expect(container.textContent).not.toContain('高亮')
    expect(onDeleteHighlight).not.toHaveBeenCalled()
  })

  it('forwards selectionBoundarySelector and rejects cross-viewport selections', () => {
    act(() =>
      root.render(
        createElement(
          SourceDocumentInteraction,
          {
            sourceAnnotations: new Map(),
            resolveSentenceAnchor: () => anchor,
            selectionBoundarySelector: '[data-source-evidence-viewport="true"]',
          },
          () =>
            createElement(
              'div',
              null,
              createElement(
                'div',
                { 'data-source-evidence-viewport': 'true' },
                createElement(
                  'span',
                  {
                    'data-sentence-id': 'B1:S1',
                    [SENTENCE_RANGE_ENABLED_ATTRIBUTE]: 'true',
                  },
                  'Left sentence.',
                ),
              ),
              createElement(
                'div',
                { 'data-source-evidence-viewport': 'true' },
                createElement(
                  'span',
                  {
                    'data-sentence-id': 'B1:S1',
                    [SENTENCE_RANGE_ENABLED_ATTRIBUTE]: 'true',
                  },
                  'Right sentence.',
                ),
              ),
            ),
        ),
      ),
    )

    const sentences = container.querySelectorAll<HTMLElement>('[data-sentence-id="B1:S1"]')
    const range = document.createRange()
    range.setStart(sentences[0]!.firstChild as Text, 0)
    range.setEnd(sentences[1]!.firstChild as Text, 5)
    window.getSelection()?.removeAllRanges()
    window.getSelection()?.addRange(range)
    act(() => {
      container
        .querySelector('[data-source-document-interaction="true"]')
        ?.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
    })

    expect(container.textContent).not.toContain('修订')
    expect(container.textContent).not.toContain('批注')
  })
})
