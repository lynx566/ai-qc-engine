// @vitest-environment happy-dom

import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { ResultOutlineSidebar } from '@/components/review/result-outline-sidebar'
import { outlineNavigationActiveClassName } from '@/lib/block-navigation-focus'
import type { DocumentOutlineEntry } from '@/lib/document-outline'

const outlineEntries: DocumentOutlineEntry[] = [
  { blockId: 'doc_test:C0001', title: '1. Summary', headingLevel: 1,
    headingPath: ['1. Summary'], docOrderIndex: 10 },
  { blockId: 'doc_test:C0030', title: '4. Clinical safety', headingLevel: 1,
    headingPath: ['4. Clinical safety'], docOrderIndex: 80 },
]

describe('ResultOutlineSidebar', () => {
  it('uses uniform dark normal-weight labels on white with unchanged indentation', () => {
    const entries = [1, 2, 3].map((headingLevel) => ({
      blockId: `level-${headingLevel}`, title: `Heading level ${headingLevel}`,
      headingLevel, headingPath: [], docOrderIndex: headingLevel,
    }))
    const host = document.createElement('div')
    host.innerHTML = renderToStaticMarkup(createElement(ResultOutlineSidebar, {
      outlineEntries: entries, scopeResultsByOutlineBlockId: new Map(), reviewState: null,
      activeOutlineBlockId: 'level-2', onSelectHeading: () => {},
    }))
    const rows = host.querySelectorAll<HTMLButtonElement>('button')
    expect(Array.from(rows, (row) => row.style.paddingLeft)).toEqual(['8px', '20px', '32px'])
    expect(rows[0].parentElement?.classList.contains('space-y-1')).toBe(true)
    const labels = Array.from(rows, (row) => row.querySelector('span')!)
    expect(host.querySelector('[data-slot="scroll-area"]')?.classList.contains('bg-white')).toBe(true)
    expect(host.querySelector('[data-slot="scroll-area-viewport"]')?.classList.contains('bg-white')).toBe(true)
    for (const label of labels) {
      expect(label.classList.contains('text-[14px]')).toBe(true)
      expect(label.classList.contains('font-normal')).toBe(true)
      expect(label.classList.contains('text-[#262626]')).toBe(true)
      expect(label.classList.contains('leading-[1.4]')).toBe(true)
      expect(label.classList.contains('font-semibold')).toBe(false)
    }
    for (const token of outlineNavigationActiveClassName.split(' ')) {
      expect(rows[1].classList.contains(token)).toBe(true)
    }
    expect(rows[2].classList.contains('hover:bg-muted/70')).toBe(true)
  })
  it('renders document navigation without retired scope finding progress', () => {
    const html = renderToStaticMarkup(createElement(ResultOutlineSidebar, {
      outlineEntries,
      scopeResultsByOutlineBlockId: new Map(),
      reviewState: null,
      activeOutlineBlockId: 'doc_test:C0030',
      onSelectHeading: () => {},
    }))

    expect(html).toContain('1. Summary')
    expect(html).toContain('4. Clinical safety')
    expect(html).toContain(outlineNavigationActiveClassName)
    expect(html).not.toContain('问题/已解决')
  })
})
