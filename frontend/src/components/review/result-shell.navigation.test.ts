import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('ResultShell document navigation wiring', () => {
  it('routes block and sentence navigation through the shared reader scroll helper', () => {
    const source = readFileSync(resolve(import.meta.dirname, 'result-shell.tsx'), 'utf8')
    const navigationModule = readFileSync(
      resolve(import.meta.dirname, '../../lib/document-navigation.ts'),
      'utf8',
    )

    expect(source).toContain('scrollElementIntoReaderView(target)')
    expect(navigationModule).toContain('documentReaderScrollAnchorClassName')
    expect(navigationModule).toContain('documentNavigationScrollIntoViewOptions')
  })

  it('routes block navigation through persistent shared block focus lifecycle', () => {
    const source = readFileSync(resolve(import.meta.dirname, 'result-shell.tsx'), 'utf8')
    const scrollToBlock = source.match(/const scrollToBlock = useCallback\([\s\S]*?\n  \)/)?.[0]
    const scrollToBlockPreservingEvidenceFocus = source.match(
      /const scrollToBlockPreservingEvidenceFocus = useCallback\([\s\S]*?\n  \)/,
    )?.[0]
    const hookSource = readFileSync(
      resolve(import.meta.dirname, '../../lib/use-block-navigation-focus.ts'),
      'utf8',
    )

    expect(scrollToBlock).toBeTruthy()
    expect(scrollToBlockPreservingEvidenceFocus).toBeTruthy()
    expect(scrollToBlock).toContain('scrollToBlockPreservingEvidenceFocus(blockId)')
    expect(scrollToBlockPreservingEvidenceFocus).toContain('focusBlock(blockId)')
    expect(scrollToBlock).not.toContain('setTimeout')
    expect(hookSource).not.toContain('setTimeout')
  })

  it('decouples annotation navigation from whole-sentence evidence focus', () => {
    const source = readFileSync(resolve(import.meta.dirname, 'result-shell.tsx'), 'utf8')
    const navigateToSourceAnnotation = source.match(
      /const navigateToSourceAnnotation = useCallback\([\s\S]*?\n  \)/,
    )?.[0]

    expect(navigateToSourceAnnotation).toBeTruthy()
    expect(navigateToSourceAnnotation).not.toContain('setFocusedEvidenceLocationKey(null)')
    expect(navigateToSourceAnnotation).toContain('clearBlockFocus()')
    expect(navigateToSourceAnnotation).not.toContain('sentenceNavigationFocusUpdate')
    expect(navigateToSourceAnnotation).toContain('scrollToSourceAnnotationElement')
    expect(navigateToSourceAnnotation).toContain('scrollToBlockPreservingEvidenceFocus')
  })
})
