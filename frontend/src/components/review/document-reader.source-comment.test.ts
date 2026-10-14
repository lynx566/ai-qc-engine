import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const readerSourcePath = resolve(import.meta.dirname, 'document-reader.tsx')
const interactionSourcePath = resolve(
  import.meta.dirname,
  'source-document-interaction.tsx',
)
const toolbarSourcePath = resolve(import.meta.dirname, 'source-selection-toolbar.tsx')

describe('DocumentReader source comment wiring', () => {
  it('shows selection toolbar with revision and comment actions', () => {
    const readerSource = readFileSync(readerSourcePath, 'utf8')
    const interactionSource = readFileSync(interactionSourcePath, 'utf8')
    const toolbarSource = readFileSync(toolbarSourcePath, 'utf8')

    expect(readerSource).toContain('SourceDocumentInteraction')
    expect(interactionSource).toContain('SourceSelectionToolbar')
    expect(interactionSource).toContain("selectionAction?.mode === 'selection'")

    expect(toolbarSource.indexOf('修订')).toBeLessThan(toolbarSource.indexOf('批注'))
    expect(toolbarSource).toContain('修订')
    expect(toolbarSource).toContain('批注')
    expect(toolbarSource).not.toContain('标记')
    expect(toolbarSource).not.toContain('高亮')

    expect(interactionSource).not.toContain('highlightDisabled')
    expect(interactionSource).not.toContain('selectionOverlapsExistingHighlight')
    expect(interactionSource).not.toContain('highlightSaving')
    expect(interactionSource).not.toContain('onHighlight')
  })

  it('persists captured selection range when creating a comment', () => {
    const source = readFileSync(interactionSourcePath, 'utf8')

    expect(source).toContain('handleCommentIconClick')
    expect(source).toContain('onCommentIconClick')
    expect(source).toContain('createPortal')
    expect(source).toContain('onCreateComment({')
    expect(source).toContain('anchor: commentPopover.anchor')
    expect(source).toContain('range: commentPopover.range')
    expect(source).toContain('selectionAction.range')
  })
})
