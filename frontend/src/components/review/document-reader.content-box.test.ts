// @vitest-environment happy-dom

import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { DocumentReader } from './document-reader'
import type { BlockPresentation, DocumentBlock } from '@/types/document-review'

function renderContent(placement: 'center' | 'expanded') {
  const entries: [string, BlockPresentation, DocumentBlock['kind']][] = [
    ['title', { alignment: 'center' }, 'paragraph'],
    ['metadata', { alignment: 'left' }, 'paragraph'],
    ['heading', { alignment: 'left' }, 'heading'],
    ['body', { alignment: 'justify', indent_left_pt: 18, indent_first_line_pt: 21 }, 'paragraph'],
    ['right', { alignment: 'right' }, 'paragraph'],
    ['hanging', { alignment: 'left', indent_left_pt: 18, indent_first_line_pt: -12 }, 'paragraph'],
  ]
  const host = document.createElement('div')
  host.innerHTML = renderToStaticMarkup(createElement(DocumentReader, {
    slotId: 'source', contentPlacement: placement, surfaceWidth: 'full-document',
    document: {
      docId: 'generic-layout', fileName: 'generic.docx', displayName: 'Generic',
      blocks: entries.map(([id, presentation, kind], index) => ({
        blockId: id, sourceBlockId: id, docOrderIndex: index, headingPath: [],
        kind, displayText: id, presentation,
      })),
    },
  }))
  return host
}

describe('canonical document page content box', () => {
  it.each(['center', 'expanded'] as const)('owns symmetric fluid insets once for %s documents', (placement) => {
    const host = renderContent(placement)
    const surface = host.querySelector<HTMLElement>('article.document-surface')!
    // Positive minimum on narrow panes, proportional whitespace on desktop, bounded maximum.
    expect(surface.classList.contains('px-[clamp(1.5rem,10%,6rem)]')).toBe(true)
    expect(host.querySelectorAll('[class*="px-[clamp("]')).toHaveLength(1)
    for (const token of ['box-border', 'w-full', 'min-w-0', 'max-w-full', 'mx-auto']) {
      expect(surface.classList.contains(token)).toBe(true)
    }
    expect(surface.className).not.toMatch(/overflow-hidden|translate|scale|shrink-0/)
    expect(surface.querySelector('.document-body')!.className).toContain('[overflow-wrap:anywhere]')
  })

  it('keeps cover and body alignments inside the same page boundary and preserves independent indents', () => {
    const host = renderContent('expanded')
    const body = host.querySelector('.document-body')!
    const text = (id: string) => body.querySelector<HTMLElement>(`[data-block-id="${id}"] > :first-child`)!
    expect(text('title').classList.contains('text-center')).toBe(true)
    for (const id of ['metadata', 'heading', 'hanging']) {
      expect(text(id).classList.contains('text-left')).toBe(true)
    }
    expect(text('right').classList.contains('text-right')).toBe(true)
    expect(text('body').classList.contains('text-justify')).toBe(true)
    expect(text('body').style.marginLeft).toBe('18pt')
    expect(text('body').style.textIndent).toBe('21pt')
    expect(text('hanging').style.textIndent).toBe('-12pt')
    expect(text('metadata').style.paddingLeft).toBe('')
    expect(text('heading').style.paddingLeft).toBe('')
  })
})
