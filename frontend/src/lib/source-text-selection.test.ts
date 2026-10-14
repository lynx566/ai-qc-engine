// @vitest-environment happy-dom

import { beforeEach, describe, expect, it } from 'vitest'

import {
  createDomRangeForSourceTextRange,
  extractSourceTextRangeFromRange,
  extractSourceTextRangeFromSelection,
  SENTENCE_RANGE_ENABLED_ATTRIBUTE,
} from '@/lib/source-text-selection'

function createSentenceSpan(
  sentenceId: string,
  innerHtml: string,
  rangeEnabled = true,
): HTMLSpanElement {
  const span = document.createElement('span')
  span.setAttribute('data-sentence-id', sentenceId)
  if (rangeEnabled) {
    span.setAttribute(SENTENCE_RANGE_ENABLED_ATTRIBUTE, 'true')
  }
  span.innerHTML = innerHtml
  document.body.appendChild(span)
  return span
}

function selectRange(range: Range) {
  const selection = window.getSelection()
  selection?.removeAllRanges()
  selection?.addRange(range)
  return selection
}

beforeEach(() => {
  document.body.innerHTML = ''
})

describe('extractSourceTextRangeFromSelection', () => {
  it('returns valid range for same-sentence selection', () => {
    const span = createSentenceSpan('C0002:S001', '感染性肺炎2例')
    const textNode = span.firstChild as Text
    const range = document.createRange()
    range.setStart(textNode, 0)
    range.setEnd(textNode, 4)
    selectRange(range)

    const result = extractSourceTextRangeFromSelection(window.getSelection())
    expect(result).toEqual({
      supported: true,
      range: { startOffset: 0, endOffset: 4 },
      sentenceId: 'C0002:S001',
    })
  })

  it('rejects collapsed selection', () => {
    const span = createSentenceSpan('C0002:S001', '感染性肺炎2例')
    const textNode = span.firstChild as Text
    const range = document.createRange()
    range.setStart(textNode, 2)
    range.setEnd(textNode, 2)
    selectRange(range)

    const result = extractSourceTextRangeFromSelection(window.getSelection())
    expect(result).toEqual({ supported: false, reason: 'collapsed-selection' })
  })

  it('rejects cross-sentence selection', () => {
    const first = createSentenceSpan('C0002:S001', '第一句。')
    const gap = document.createTextNode(' ')
    const second = createSentenceSpan('C0002:S002', '第二句。')
    document.body.append(first, gap, second)

    const range = document.createRange()
    range.setStart(first.firstChild as Text, 0)
    range.setEnd(second.firstChild as Text, 2)
    selectRange(range)

    const result = extractSourceTextRangeFromSelection(window.getSelection())
    expect(result).toEqual({ supported: false, reason: 'cross-sentence' })
  })

  it('rejects selection that includes gap text', () => {
    const first = createSentenceSpan('C0002:S001', '第一句。')
    const gap = document.createTextNode('\n')
    const second = createSentenceSpan('C0002:S002', '第二句。')
    document.body.append(first, gap, second)

    const range = document.createRange()
    range.setStart(first.firstChild as Text, 3)
    range.setEnd(gap, 1)
    selectRange(range)

    const result = extractSourceTextRangeFromSelection(window.getSelection())
    expect(result).toEqual({ supported: false, reason: 'outside-sentence' })
  })

  it('rejects heading sentence without range-enabled attribute', () => {
    const span = createSentenceSpan('C0010:S001', '1. 执行概要', false)
    const textNode = span.firstChild as Text
    const range = document.createRange()
    range.setStart(textNode, 0)
    range.setEnd(textNode, 2)
    selectRange(range)

    const result = extractSourceTextRangeFromSelection(window.getSelection())
    expect(result).toEqual({ supported: false, reason: 'range-disabled-block' })
  })

  it('handles nested text nodes within one sentence', () => {
    const span = createSentenceSpan('C0002:S001', '前缀<mark>中</mark>后缀')
    const prefixNode = span.childNodes[0] as Text
    const middleNode = (span.querySelector('mark')?.firstChild ?? null) as Text
    const suffixNode = span.childNodes[2] as Text

    const range = document.createRange()
    range.setStart(prefixNode, 1)
    range.setEnd(suffixNode, 1)
    selectRange(range)

    const result = extractSourceTextRangeFromRange(range)
    expect(result).toEqual({
      supported: true,
      range: { startOffset: 1, endOffset: 4 },
      sentenceId: 'C0002:S001',
    })
    expect(middleNode.textContent).toBe('中')
  })

  it('rejects selection when either endpoint is outside the containment root', () => {
    const root = document.createElement('div')
    const inside = createSentenceSpan('C0002:S001', 'inside text')
    const outside = createSentenceSpan('C0002:S002', 'outside text')
    root.appendChild(inside)
    document.body.append(root, outside)

    const range = document.createRange()
    range.setStart(inside.firstChild as Text, 0)
    range.setEnd(inside.firstChild as Text, 3)
    const insideResult = extractSourceTextRangeFromRange(range, { containmentRoot: root })
    expect(insideResult.supported).toBe(true)

    const crossRange = document.createRange()
    crossRange.setStart(inside.firstChild as Text, 0)
    crossRange.setEnd(outside.firstChild as Text, 3)
    const outsideResult = extractSourceTextRangeFromRange(crossRange, {
      containmentRoot: root,
    })
    expect(outsideResult).toEqual({ supported: false, reason: 'outside-root' })
  })

  it('accepts selection whose endpoints belong to the same evidence viewport', () => {
    const workspace = document.createElement('div')
    const viewport = document.createElement('section')
    viewport.setAttribute('data-source-evidence-viewport', 'true')
    const span = createSentenceSpan('B1:S1', 'Target sentence.')
    viewport.appendChild(span)
    workspace.appendChild(viewport)
    document.body.appendChild(workspace)

    const range = document.createRange()
    range.setStart(span.firstChild as Text, 0)
    range.setEnd(span.firstChild as Text, 6)

    expect(extractSourceTextRangeFromRange(range, {
      containmentRoot: workspace,
      selectionBoundarySelector: '[data-source-evidence-viewport="true"]',
    })).toEqual({
      supported: true,
      range: { startOffset: 0, endOffset: 6 },
      sentenceId: 'B1:S1',
    })
  })

  it('rejects duplicate source sentence endpoints from different evidence viewports', () => {
    const workspace = document.createElement('div')
    const viewportA = document.createElement('section')
    const viewportB = document.createElement('section')
    viewportA.setAttribute('data-source-evidence-viewport', 'true')
    viewportB.setAttribute('data-source-evidence-viewport', 'true')
    const sentenceA = createSentenceSpan('B1:S1', 'Target sentence.')
    const sentenceB = createSentenceSpan('B1:S1', 'Target sentence.')
    viewportA.appendChild(sentenceA)
    viewportB.appendChild(sentenceB)
    workspace.append(viewportA, viewportB)
    document.body.appendChild(workspace)

    const range = document.createRange()
    range.setStart(sentenceA.firstChild as Text, 0)
    range.setEnd(sentenceB.firstChild as Text, 6)

    expect(extractSourceTextRangeFromRange(range, {
      containmentRoot: workspace,
      selectionBoundarySelector: '[data-source-evidence-viewport="true"]',
    })).toEqual({ supported: false, reason: 'cross-boundary' })
  })

  it('reads slot and document identity from the selected sentence', () => {
    const root = document.createElement('section')
    root.setAttribute('data-slot-id', 'second')
    root.setAttribute('data-doc-id', 'same-doc')
    const span = createSentenceSpan('B1:S1', 'First.')
    span.setAttribute('data-slot-id', 'second')
    span.setAttribute('data-doc-id', 'same-doc')
    root.appendChild(span)
    document.body.appendChild(root)

    const range = document.createRange()
    range.setStart(span.firstChild as Text, 0)
    range.setEnd(span.firstChild as Text, 5)
    expect(extractSourceTextRangeFromRange(range, { containmentRoot: root })).toEqual({
      supported: true,
      range: { startOffset: 0, endOffset: 5 },
      sentenceId: 'B1:S1',
      slotId: 'second',
      docId: 'same-doc',
    })
  })

  it('keeps code-point offsets local to the visible sentence when leading sentences are omitted', () => {
    const span = createSentenceSpan('B1:S3', 'Target sentence.')
    const range = document.createRange()
    range.setStart(span.firstChild as Text, 0)
    range.setEnd(span.firstChild as Text, 6)
    expect(extractSourceTextRangeFromRange(range)).toEqual({
      supported: true,
      range: { startOffset: 0, endOffset: 6 },
      sentenceId: 'B1:S3',
    })
  })

  it('returns code-point offsets for emoji selection', () => {
    const span = createSentenceSpan('C0100:S001', 'A😀B')
    const textNode = span.firstChild as Text
    const range = document.createRange()
    range.setStart(textNode, 1)
    range.setEnd(textNode, 3)
    selectRange(range)

    const result = extractSourceTextRangeFromSelection(window.getSelection())
    expect(result).toEqual({
      supported: true,
      range: { startOffset: 1, endOffset: 2 },
      sentenceId: 'C0100:S001',
    })
  })
})

describe('createDomRangeForSourceTextRange', () => {
  it('restores nested text-node selection from code-point offsets', () => {
    const span = createSentenceSpan('C0002:S001', '前缀<mark>中</mark>后缀')
    const domRange = createDomRangeForSourceTextRange(span, { startOffset: 1, endOffset: 4 })
    expect(domRange).not.toBeNull()
    const extracted = extractSourceTextRangeFromRange(domRange!)
    expect(extracted).toEqual({
      supported: true,
      range: { startOffset: 1, endOffset: 4 },
      sentenceId: 'C0002:S001',
    })
  })
})
