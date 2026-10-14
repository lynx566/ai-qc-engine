import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('QcSetupShell block navigation wiring', () => {
  it('uses shared persistent block focus lifecycle for heading navigation', () => {
    const source = readFileSync(resolve(import.meta.dirname, 'qc-setup-shell.tsx'), 'utf8')
    const scrollToBlock = source.match(/const scrollToBlock = useCallback\([\s\S]*?\n  \)/)?.[0]
    const hookSource = readFileSync(
      resolve(import.meta.dirname, '../../lib/use-block-navigation-focus.ts'),
      'utf8',
    )

    expect(source).toContain('useBlockNavigationFocus')
    expect(source).toContain('onClearFocusedBlock={clearBlockFocus}')
    expect(scrollToBlock).toBeTruthy()
    expect(scrollToBlock).toContain('focusBlock(blockId)')
    expect(scrollToBlock).not.toContain('setTimeout')
    expect(hookSource).not.toContain('setTimeout')
  })

  it('passes shared block focus presentation and dismissal to DocumentReader', () => {
    const source = readFileSync(resolve(import.meta.dirname, 'qc-setup-shell.tsx'), 'utf8')
    const documentReaderSource = `${readFileSync(
      resolve(import.meta.dirname, '../review/document-reader.tsx'),
      'utf8',
    )}\n${readFileSync(
      resolve(import.meta.dirname, '../review/document-render-groups.tsx'),
      'utf8',
    )}`

    expect(source).toContain('onClearFocusedBlock={onClearFocusedBlock}')
    expect(source).toContain('contentPlacement="expanded"')
    expect(source).toContain('canvasLayout="workspace"')
    expect(documentReaderSource).toContain('blockNavigationFocusClassName')
    expect(documentReaderSource).toContain('onClearFocusedBlock')
    expect(documentReaderSource).not.toContain(
      'ring-2 ring-primary/40 ring-offset-2 ring-offset-white',
    )
  })

  it('clears block focus when switching slots', () => {
    const source = readFileSync(resolve(import.meta.dirname, 'qc-setup-shell.tsx'), 'utf8')
    const handleSelectSlot = source.match(/const handleSelectSlot = useCallback\([\s\S]*?\n  \)/)?.[0]

    expect(handleSelectSlot).toBeTruthy()
    expect(handleSelectSlot).toContain('clearBlockFocus()')
  })
})
