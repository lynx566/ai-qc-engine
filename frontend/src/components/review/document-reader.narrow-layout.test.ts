// @vitest-environment happy-dom

import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'
import { DocumentReader } from '@/components/review/document-reader'

const readerSource = readFileSync(
  resolve(import.meta.dirname, 'document-reader.tsx'),
  'utf8',
)
const blockContentSource = readFileSync(
  resolve(import.meta.dirname, 'document-block-content.tsx'),
  'utf8',
)

function renderReader(
  contentPlacement: 'center' | 'expanded' = 'center',
  surfaceWidth: 'default' | 'full-document' = 'default',
) {
  const host = document.createElement('div')
  host.innerHTML = renderToStaticMarkup(createElement(DocumentReader, {
    document: { docId: 'layout-document', fileName: 'layout.docx', displayName: 'Layout', blocks: [] },
    slotId: 'source',
    contentPlacement,
    surfaceWidth,
    canvasLayout: 'workspace',
  }))
  return {
    host,
    canvas: host.querySelector<HTMLElement>('[data-document-canvas]')!,
    interaction: host.querySelector<HTMLElement>('[data-source-document-interaction]')!,
    surface: host.querySelector<HTMLElement>('article.document-surface')!,
  }
}

describe('DocumentReader narrow-desktop layout', () => {
  it('widens the explicit Full Document surface without changing centered padding or narrow fitting', () => {
    const full = renderReader('center', 'full-document')
    const standard = renderReader()
    expect(full.surface.classList.contains('min-[840px]:max-w-[56rem]')).toBe(true)
    expect(full.surface.classList.contains('min-[840px]:max-w-[48rem]')).toBe(false)
    expect(full.surface.classList.contains('max-w-[56rem]')).toBe(false)
    expect(full.surface.classList.contains('mx-auto')).toBe(true)
    expect(full.canvas.className).toBe(standard.canvas.className)
    expect(full.surface.className.replace('max-w-[56rem]', 'max-w-[48rem]')).toBe(standard.surface.className)
    expect(full.surface.parentElement).toBe(full.interaction)
  })
  it('allows the document surface to shrink within the reader pane', () => {
    const { canvas, interaction, surface } = renderReader()
    for (const element of [canvas, interaction, surface]) {
      expect(element.classList.contains('w-full')).toBe(true)
      expect(element.classList.contains('min-w-0')).toBe(true)
      expect(element.classList.contains('max-w-full')).toBe(true)
      expect(element.classList.contains('shrink-0')).toBe(false)
    }
    expect(surface.classList.contains('min-[840px]:max-w-[48rem]')).toBe(true)
    expect(surface.classList.contains('max-w-[48rem]')).toBe(false)
    const viewport = canvas.closest('[data-slot="scroll-area-viewport"]')!
    expect(viewport.classList.contains('[&>div]:!block')).toBe(true)
    expect(viewport.classList.contains('[&>div]:!w-full')).toBe(true)
    expect(viewport.classList.contains('[&>div]:!min-w-0')).toBe(true)
  })

  it('centers the capped article itself with symmetric auto margins inside the interaction owner', () => {
    const { host, canvas, interaction, surface } = renderReader()
    expect(host.querySelectorAll('[data-source-document-interaction]')).toHaveLength(1)
    expect(host.querySelectorAll('article.document-surface')).toHaveLength(1)
    expect(surface.parentElement).toBe(interaction)
    expect(interaction.parentElement).toBe(canvas)
    expect(interaction.classList.contains('relative')).toBe(true)
    expect(interaction.classList.contains('w-full')).toBe(true)
    expect(surface.classList.contains('mx-auto')).toBe(true)
    expect(surface.classList.contains('min-[840px]:max-w-[48rem]')).toBe(true)
    expect(canvas.classList.contains('max-w-[48rem]')).toBe(false)
  })

  it('tightens horizontal padding below 840px and restores wider padding above', () => {
    const { canvas, surface } = renderReader()
    for (const token of ['px-2', 'min-[840px]:px-4', 'min-[840px]:sm:px-8']) {
      expect(canvas.classList.contains(token)).toBe(true)
    }
    for (const token of ['px-6', 'py-12', 'min-[840px]:px-10', 'min-[840px]:sm:px-14']) {
      expect(surface.classList.contains(token)).toBe(true)
    }
  })

  it('centers the expanded QC Setup article inside its interaction owner without changing geometry contracts', () => {
    const centered = renderReader()
    const expanded = renderReader('expanded')
    expect(centered.surface.classList.contains('min-[840px]:max-w-[48rem]')).toBe(true)
    expect(expanded.surface.classList.contains('min-[840px]:max-w-[56rem]')).toBe(true)
    expect(expanded.surface.classList.contains('mx-auto')).toBe(true)
    expect(expanded.surface.parentElement).toBe(expanded.interaction)
    expect(expanded.interaction.parentElement).toBe(expanded.canvas)
    expect(expanded.host.querySelectorAll('[data-source-document-interaction]')).toHaveLength(1)
    expect(expanded.host.querySelectorAll('article.document-surface')).toHaveLength(1)
    for (const token of ['w-full', 'min-w-0', 'max-w-full']) {
      expect(expanded.surface.classList.contains(token)).toBe(true)
      expect(expanded.interaction.classList.contains(token)).toBe(true)
    }
    expect(expanded.surface.classList.contains('max-w-[56rem]')).toBe(false)
    for (const token of ['px-3', 'min-[840px]:px-4', 'min-[840px]:sm:px-6']) {
      expect(expanded.canvas.classList.contains(token)).toBe(true)
    }
    for (const token of ['px-6', 'py-12', 'min-[840px]:px-10', 'min-[840px]:sm:px-12', 'min-[840px]:sm:py-14']) {
      expect(expanded.surface.classList.contains(token)).toBe(true)
    }
  })

  it('keeps table overflow scoped inside the document surface', () => {
    expect(blockContentSource).toContain('max-w-full overflow-x-auto')
    expect(blockContentSource).toContain('min-w-[28rem]')
  })

  it('supports workspace canvas top alignment for Result without changing default canvas padding', () => {
    expect(readerSource).toContain("canvasLayout?: 'default' | 'workspace'")
    expect(readerSource).toContain('data-document-canvas-layout={canvasLayout}')
    expect(readerSource).toContain('py-6 min-[840px]:sm:py-10')
    expect(readerSource).toContain('pt-2 pb-6 min-[840px]:sm:pt-2 min-[840px]:sm:pb-8')
  })
})
