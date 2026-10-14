import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import {
  applyBlockNavigationFocus,
  blockNavigationFocusBaseClassName,
  blockNavigationFocusClassName,
  blockNavigationFocusVisibleClassName,
  outlineNavigationActiveClassName,
  clearBlockNavigationFocusState,
  initialBlockNavigationFocusState,
} from '@/lib/block-navigation-focus'

const documentReaderSource = () =>
  readFileSync(resolve(import.meta.dirname, '../components/review/document-reader.tsx'), 'utf8')

const documentReaderPresentationSource = () =>
  `${documentReaderSource()}\n${readFileSync(
    resolve(import.meta.dirname, '../components/review/document-render-groups.tsx'),
    'utf8',
  )}`

const interactionSource = () =>
  readFileSync(
    resolve(import.meta.dirname, '../components/review/source-document-interaction.tsx'),
    'utf8',
  )

const useBlockNavigationFocusSource = () =>
  readFileSync(resolve(import.meta.dirname, 'use-block-navigation-focus.ts'), 'utf8')

describe('outlineNavigationActiveClassName', () => {
  it('matches document block focus background', () => {
    expect(outlineNavigationActiveClassName).toContain(blockNavigationFocusVisibleClassName)
    expect(outlineNavigationActiveClassName).toContain(blockNavigationFocusBaseClassName)
  })
})

describe('blockNavigationFocusClassName', () => {
  it('applies persistent neutral gray background without border or ring', () => {
    const className = blockNavigationFocusClassName(true)

    expect(className).toContain(blockNavigationFocusBaseClassName)
    expect(className).toContain(blockNavigationFocusVisibleClassName)
    expect(className).not.toContain('ring')
    expect(className).not.toContain('outline')
    expect(className).not.toContain('border')
    expect(className).not.toContain('shadow')
  })

  it('leaves non-target headings without navigation background', () => {
    const className = blockNavigationFocusClassName(false)

    expect(className).toBe(blockNavigationFocusBaseClassName)
    expect(className).not.toContain(blockNavigationFocusVisibleClassName)
  })
})

describe('block navigation focus lifecycle state', () => {
  it('enters persistent focus on navigation', () => {
    expect(applyBlockNavigationFocus('block_a')).toEqual({
      focusedBlockId: 'block_a',
    })
  })

  it('replaces first target when navigating to a second block', () => {
    const first = applyBlockNavigationFocus('block_a')
    const second = applyBlockNavigationFocus('block_b')

    expect(second).toEqual({
      focusedBlockId: 'block_b',
    })
    expect(first.focusedBlockId).toBe('block_a')
  })

  it('clears focus explicitly', () => {
    expect(clearBlockNavigationFocusState()).toEqual(initialBlockNavigationFocusState)
  })
})

describe('DocumentReader block navigation presentation', () => {
  it('uses shared block navigation focus classes instead of ring outlines', () => {
    const source = documentReaderPresentationSource()

    expect(source).toContain('blockNavigationFocusClassName')
    expect(source).not.toContain('ring-2 ring-primary/40 ring-offset-2 ring-offset-white')
    expect(source).not.toContain('transition-shadow duration-300')
  })

  it('clears block focus on ordinary document interaction and persisted annotation clicks', () => {
    const reader = documentReaderSource()
    const source = interactionSource()

    expect(reader).toContain('onClearFocusedBlock')
    expect(source).toContain('shouldClearDocumentNavigationFocusOnDocumentMouseUp')
    expect(source).toMatch(/handleCommentIconClick[\s\S]*onClearFocusedBlock/)
    expect(source).toMatch(/handlePersistedMarkClick[\s\S]*onClearFocusedBlock/)
  })
})

describe('useBlockNavigationFocus', () => {
  it('does not use timeout or fade lifecycle', () => {
    const source = useBlockNavigationFocusSource()

    expect(source).not.toContain('setTimeout')
    expect(source).not.toContain('clearTimeout')
    expect(source).not.toContain('blockFocusFading')
    expect(source).not.toContain('BLOCK_FOCUS_HOLD_MS')
    expect(source).not.toContain('BLOCK_FOCUS_FADE_MS')
  })
})
