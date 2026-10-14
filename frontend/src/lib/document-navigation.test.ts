import { describe, expect, it, vi } from 'vitest'

import { sentenceDomId } from '@/lib/document-anchors'
import {
  documentNavigationScrollIntoViewOptions,
  documentReaderScrollAnchorClassName,
  scrollElementIntoReaderView,
  scrollToSentenceTarget,
} from '@/lib/document-navigation'

describe('scrollToSentenceTarget', () => {
  it('returns sentence result when sentence element exists', () => {
    const sentenceElement = {
      scrollIntoView: vi.fn(),
      focus: vi.fn(),
    }
    const scrollToBlock = vi.fn()
    const rootDocument = {
      getElementById: vi.fn((id: string) => {
        if (id === sentenceDomId('doc_test', 'C0002:S001')) {
          return sentenceElement
        }
        return null
      }),
    } as unknown as Document

    expect(
      scrollToSentenceTarget(
        {
          docId: 'doc_test',
          blockId: 'doc_test:C0002',
          sentenceId: 'C0002:S001',
        },
        { scrollToBlock, rootDocument },
      ),
    ).toBe('sentence')
  })

  it('scrolls to sentence element without invoking block focus callback', () => {
    const sentenceElement = {
      scrollIntoView: vi.fn(),
      focus: vi.fn(),
    }
    const scrollToBlock = vi.fn()
    const rootDocument = {
      getElementById: vi.fn((id: string) => {
        if (id === sentenceDomId('doc_test', 'C0002:S001')) {
          return sentenceElement
        }
        return null
      }),
    } as unknown as Document

    const result = scrollToSentenceTarget(
      {
        docId: 'doc_test',
        blockId: 'doc_test:C0002',
        sentenceId: 'C0002:S001',
      },
      { scrollToBlock, rootDocument },
    )

    expect(result).toBe('sentence')
    expect(sentenceElement.scrollIntoView).toHaveBeenCalledWith(
      documentNavigationScrollIntoViewOptions,
    )
    expect(scrollToBlock).not.toHaveBeenCalled()
  })

  it('exposes a reader scroll anchor for scroll-padding-top alignment', () => {
    expect(documentReaderScrollAnchorClassName).toContain('28%')
  })

  it('scrollElementIntoReaderView uses shared alignment options', () => {
    const element = {
      scrollIntoView: vi.fn(),
      focus: vi.fn(),
    } as unknown as HTMLElement

    scrollElementIntoReaderView(element)

    expect(element.scrollIntoView).toHaveBeenCalledWith(documentNavigationScrollIntoViewOptions)
    expect(element.focus).toHaveBeenCalledWith({ preventScroll: true })
  })

  it('falls back to block navigation when sentence dom is missing', () => {
    const scrollToBlock = vi.fn()
    const rootDocument = {
      getElementById: vi.fn(() => null),
    } as unknown as Document

    const result = scrollToSentenceTarget(
      {
        docId: 'doc_test',
        blockId: 'doc_test:T0001',
        sentenceId: 'T0001:S001',
      },
      { scrollToBlock, rootDocument },
    )

    expect(result).toBe('block')
    expect(scrollToBlock).toHaveBeenCalledWith('doc_test:T0001')
  })
})
