import { describe, expect, it } from 'vitest'

import { normalizeTocOutlineLevel, parseTocEntryText } from '@/lib/toc-entry'

describe('normalizeTocOutlineLevel', () => {
  it('maps extended Word TOC styles to outline depth', () => {
    expect(normalizeTocOutlineLevel(11)).toBe(1)
    expect(normalizeTocOutlineLevel(21)).toBe(2)
    expect(normalizeTocOutlineLevel(2)).toBe(2)
  })
})

describe('parseTocEntryText', () => {
  it('splits tab-separated title and page number', () => {
    expect(parseTocEntryText('1.前言\t4')).toEqual({
      title: '1.前言',
      pageNumber: '4',
    })
  })

  it('falls back to trailing page number when tabs were normalized away', () => {
    expect(parseTocEntryText('2.全球上市批准状态 4')).toEqual({
      title: '2.全球上市批准状态',
      pageNumber: '4',
    })
  })

  it('returns title-only entries without a page number', () => {
    expect(parseTocEntryText('目录')).toEqual({ title: '目录' })
  })
})
