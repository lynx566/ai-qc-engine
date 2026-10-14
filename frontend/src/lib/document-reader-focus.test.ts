import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import { documentReaderScrollAnchorClassName } from '@/lib/document-navigation'

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

describe('document reader presentation', () => {
  it('does not render permanent candidate selection overlays', () => {
    const source = documentReaderPresentationSource()

    expect(source).not.toContain('Selected for Clinical Safety')
    expect(source).not.toContain('selectedBlockIds')
    expect(source).not.toContain('candidate-block')
    expect(source).toContain('focusedBlockId')
    expect(source).toContain('onClearFocusedBlock')
    expect(source).toContain('blockNavigationFocusClassName')
    expect(source).not.toContain('ring-2 ring-primary/40 ring-offset-2 ring-offset-white')
    expect(source).not.toContain('blockFocusFading')
  })

  it('applies reader scroll anchor padding on the scroll viewport', () => {
    const source = readFileSync(
      resolve(import.meta.dirname, '../components/review/document-reader.tsx'),
      'utf8',
    )

    expect(documentReaderScrollAnchorClassName).toContain('28%')
    expect(source).toContain('documentReaderScrollAnchorClassName')
    expect(source).toContain('viewportClassName={cn(')
  })
})

describe('DocumentReader focusedSentence lifecycle wiring', () => {
  it('clears evidence focus on ordinary document interaction but preserves it during selection', () => {
    const reader = documentReaderSource()
    const source = interactionSource()

    expect(reader).toContain('SourceDocumentInteraction')
    expect(reader).toContain('onClearFocusedSentence')
    expect(source).toContain('onClearActiveSourceAnnotation')
    expect(source).toContain('shouldClearDocumentNavigationFocusOnDocumentMouseUp')
    expect(source).toContain('resolveMouseEventInteractionElement')
    expect(source).toContain('isSourceAnnotationInteractionElement')
    expect(source).toContain('handlePersistedMarkClick')
    expect(source).toContain('clearDocumentNavigationFocusIfNeeded(true, false)')
    expect(source).toContain('clearDocumentNavigationFocusIfNeeded(false, false)')
    expect(source).toContain('if (extracted.supported)')
    const pointerDownHandler = source.match(
      /const handlePointerDown = \(event: PointerEvent\) => \{[\s\S]*?\n    \}/,
    )?.[0]
    expect(pointerDownHandler).toBeTruthy()
    expect(pointerDownHandler).not.toContain('onClearFocusedSentence')
    expect(source).not.toMatch(/onMouseDown[\s\S]{0,120}onClearFocusedSentence/)
  })

  it('clears evidence focus when opening existing persisted annotations', () => {
    const source = interactionSource()

    expect(source).toContain('handleCommentIconClick')
    expect(source).toMatch(/handleCommentIconClick[\s\S]*onClearFocusedBlock/)
    expect(source).toContain('handlePersistedMarkClick')
    expect(source).toMatch(/handlePersistedMarkClick[\s\S]*onClearFocusedBlock/)
  })
})
