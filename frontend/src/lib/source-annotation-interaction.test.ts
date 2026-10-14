// @vitest-environment happy-dom

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import {
  isSourceAnnotationInteractionElement,
  resolveMouseEventInteractionElement,
  shouldActivateFindingTarget,
  shouldClearActiveSourceAnnotationOnDocumentMouseUp,
} from '@/lib/source-annotation-interaction'

const interactionModuleSource = () =>
  readFileSync(resolve(import.meta.dirname, 'source-annotation-interaction.ts'), 'utf8')

describe('source annotation interaction helpers', () => {
  it('defines explicit interaction selectors for annotation controls', () => {
    const source = interactionModuleSource()

    expect(source).toContain('data-source-persisted-mark="true"')
    expect(source).toContain('data-source-comment-icon="true"')
    expect(source).toContain('data-source-mark-action="true"')
    expect(source).toContain('data-source-comment-popover="true"')
    expect(source).toContain('data-source-annotation-navigator="true"')
  })

  it('resolves text node targets to their parent element', () => {
    const element = document.createElement('span')
    const text = document.createTextNode('标记')
    element.appendChild(text)

    expect(resolveMouseEventInteractionElement(text)).toBe(element)
  })

  it('clears active annotation only for generic document interaction targets', () => {
    const paragraph = document.createElement('p')
    const mark = document.createElement('span')
    mark.setAttribute('data-source-persisted-mark', 'true')

    expect(shouldClearActiveSourceAnnotationOnDocumentMouseUp(paragraph)).toBe(true)
    expect(isSourceAnnotationInteractionElement(mark)).toBe(true)
    expect(shouldClearActiveSourceAnnotationOnDocumentMouseUp(mark)).toBe(false)
  })

  it('does not activate a Finding target for annotation controls or live selections', () => {
    const sentence = document.createElement('span')
    const mark = document.createElement('span')
    mark.setAttribute('data-source-persisted-mark', 'true')
    sentence.appendChild(mark)
    document.body.append(sentence)

    expect(shouldActivateFindingTarget({ target: sentence })).toBe(true)
    expect(shouldActivateFindingTarget({ target: mark })).toBe(false)

    const range = document.createRange()
    range.selectNodeContents(sentence)
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)
    expect(shouldActivateFindingTarget({ target: sentence })).toBe(false)

    selection?.removeAllRanges()
    sentence.remove()
  })
})
