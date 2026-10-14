// @vitest-environment happy-dom

import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ExtractBundleDto } from '@/adapters/extract-bundle.dto'
import { fetchCandidateScopeDocument } from '@/api/candidate-scope-document'
import { useSlotDocumentLoader } from '@/lib/use-slot-document-loader'

vi.mock('@/api/candidate-scope-document', () => ({
  fetchCandidateScopeDocument: vi.fn(),
}))

const mockFetchCandidateScopeDocument = vi.mocked(fetchCandidateScopeDocument)

type SlotInput = {
  slotId: string
  docId: string
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function bundle(docId: string): ExtractBundleDto {
  return {
    doc_id: docId,
    file_name: `${docId}.docx`,
    display_name: `${docId}.docx`,
    content_blocks: [],
  }
}

function LoaderHarness({
  flowRunId,
  slots,
}: {
  flowRunId: string
  slots: SlotInput[]
}) {
  const state = useSlotDocumentLoader(flowRunId, slots)

  return createElement(
    'div',
    null,
    slots.map((slot) =>
      createElement(
        'span',
        { key: slot.slotId, 'data-slot-id': slot.slotId },
        `${state.documentLoadStatusBySlotId[slot.slotId] ?? 'missing'}:` +
          `${state.documentsBySlotId[slot.slotId]?.docId ?? 'none'}`,
      ),
    ),
  )
}

function slotText(container: HTMLElement, slotId: string) {
  return container.querySelector(`[data-slot-id="${slotId}"]`)?.textContent
}

async function flushAsyncWork() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
  })
}

describe('useSlotDocumentLoader', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
    vi.clearAllMocks()
  })

  it('keeps the current document ready when a superseded request finishes later', async () => {
    const oldRequest = deferred<ExtractBundleDto>()
    const currentRequest = deferred<ExtractBundleDto>()
    mockFetchCandidateScopeDocument.mockImplementation((flowRunId) =>
      flowRunId === 'flow_old' ? oldRequest.promise : currentRequest.promise,
    )

    act(() => {
      root.render(
        createElement(LoaderHarness, {
          flowRunId: 'flow_old',
          slots: [{ slotId: 'source', docId: 'doc_old' }],
        }),
      )
    })
    await flushAsyncWork()

    act(() => {
      root.render(
        createElement(LoaderHarness, {
          flowRunId: 'flow_current',
          slots: [{ slotId: 'source', docId: 'doc_current' }],
        }),
      )
    })
    await flushAsyncWork()

    currentRequest.resolve(bundle('doc_current'))
    await flushAsyncWork()
    expect(slotText(container, 'source')).toBe('ready:doc_current')

    oldRequest.resolve(bundle('doc_old'))
    await flushAsyncWork()
    expect(slotText(container, 'source')).toBe('ready:doc_current')
  })

  it('keeps each slot request alive when another slot completes', async () => {
    const sourceARequest = deferred<ExtractBundleDto>()
    const sourceBRequest = deferred<ExtractBundleDto>()
    mockFetchCandidateScopeDocument.mockImplementation((_flowRunId, slotId) =>
      slotId === 'source_a' ? sourceARequest.promise : sourceBRequest.promise,
    )

    act(() => {
      root.render(
        createElement(LoaderHarness, {
          flowRunId: 'flow_multi',
          slots: [
            { slotId: 'source_a', docId: 'doc_a' },
            { slotId: 'source_b', docId: 'doc_b' },
          ],
        }),
      )
    })
    await flushAsyncWork()

    sourceARequest.resolve(bundle('doc_a'))
    await flushAsyncWork()
    expect(slotText(container, 'source_a')).toBe('ready:doc_a')
    expect(slotText(container, 'source_b')).toBe('loading:none')

    sourceBRequest.resolve(bundle('doc_b'))
    await flushAsyncWork()
    expect(slotText(container, 'source_a')).toBe('ready:doc_a')
    expect(slotText(container, 'source_b')).toBe('ready:doc_b')
  })

  it('does not reveal an old ready document when inputs return to an earlier identity', async () => {
    const firstARequest = deferred<ExtractBundleDto>()
    const bRequest = deferred<ExtractBundleDto>()
    const secondARequest = deferred<ExtractBundleDto>()
    let aRequestCount = 0
    mockFetchCandidateScopeDocument.mockImplementation((flowRunId) => {
      if (flowRunId === 'flow_b') {
        return bRequest.promise
      }
      aRequestCount += 1
      return aRequestCount === 1 ? firstARequest.promise : secondARequest.promise
    })

    act(() => {
      root.render(
        createElement(LoaderHarness, {
          flowRunId: 'flow_a',
          slots: [{ slotId: 'source', docId: 'doc_a' }],
        }),
      )
    })
    firstARequest.resolve(bundle('doc_a'))
    await flushAsyncWork()
    expect(slotText(container, 'source')).toBe('ready:doc_a')

    act(() => {
      root.render(
        createElement(LoaderHarness, {
          flowRunId: 'flow_b',
          slots: [{ slotId: 'source', docId: 'doc_b' }],
        }),
      )
    })
    await flushAsyncWork()

    act(() => {
      root.render(
        createElement(LoaderHarness, {
          flowRunId: 'flow_a',
          slots: [{ slotId: 'source', docId: 'doc_a' }],
        }),
      )
    })
    expect(slotText(container, 'source')).toBe('loading:none')

    secondARequest.resolve(bundle('doc_a'))
    await flushAsyncWork()
    expect(slotText(container, 'source')).toBe('ready:doc_a')
  })
})
