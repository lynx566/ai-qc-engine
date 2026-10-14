import { isSourceAnnotationUiElement, collectSentenceSourceText } from '@/lib/source-sentence-presentation'
import {
  codePointOffsetToUtf16Offset,
  normalizeSourceTextRange,
  utf16OffsetToCodePointOffset,
} from '@/lib/source-text-range'
import type { SourceTextRange } from '@/types/source-annotation'

export const SENTENCE_RANGE_ENABLED_ATTRIBUTE = 'data-sentence-range-enabled'

export type SourceTextSelectionUnsupportedReason =
  | 'no-selection'
  | 'collapsed-selection'
  | 'cross-sentence'
  | 'outside-sentence'
  | 'outside-root'
  | 'cross-boundary'
  | 'range-disabled-block'
  | 'invalid-offset'

export type SourceTextSelectionIdentity = {
  sentenceId: string
  slotId?: string
  docId?: string
}

export type SourceTextSelectionResult =
  | { supported: true; range: SourceTextRange } & SourceTextSelectionIdentity
  | { supported: false; reason: SourceTextSelectionUnsupportedReason }

function isTextNode(node: Node): node is Text {
  return node.nodeType === Node.TEXT_NODE
}

function findSentenceSpan(node: Node | null): HTMLElement | null {
  let current: Node | null = node
  while (current) {
    if (current instanceof HTMLElement && current.hasAttribute('data-sentence-id')) {
      return current
    }
    current = current.parentNode
  }
  return null
}

function collectTextNodes(root: Node): Text[] {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement
      if (isSourceAnnotationUiElement(parent)) {
        return NodeFilter.FILTER_REJECT
      }
      return NodeFilter.FILTER_ACCEPT
    },
  })
  const nodes: Text[] = []
  let current = walker.nextNode()
  while (current) {
    if (isTextNode(current)) {
      nodes.push(current)
    }
    current = walker.nextNode()
  }
  return nodes
}

function sentenceLocalUtf16Offset(
  sentenceSpan: HTMLElement,
  container: Node,
  offset: number,
): number | null {
  let accumulated = 0
  for (const textNode of collectTextNodes(sentenceSpan)) {
    if (textNode === container) {
      if (offset < 0 || offset > textNode.data.length) {
        return null
      }
      return accumulated + offset
    }
    accumulated += textNode.data.length
  }
  return null
}

function isRangeEnabledSentenceSpan(sentenceSpan: HTMLElement): boolean {
  return sentenceSpan.getAttribute(SENTENCE_RANGE_ENABLED_ATTRIBUTE) === 'true'
}

function readAttributeFromSentenceOrAncestor(
  sentenceSpan: HTMLElement,
  attribute: string,
): string | undefined {
  const own = sentenceSpan.getAttribute(attribute)
  if (own) {
    return own
  }
  return sentenceSpan.closest(`[${attribute}]`)?.getAttribute(attribute) ?? undefined
}

export function readSentenceDocumentIdentity(
  sentenceSpan: HTMLElement,
): Pick<SourceTextSelectionIdentity, 'slotId' | 'docId'> {
  return {
    slotId: readAttributeFromSentenceOrAncestor(sentenceSpan, 'data-slot-id'),
    docId: readAttributeFromSentenceOrAncestor(sentenceSpan, 'data-doc-id'),
  }
}

function isNodeContainedInRoot(node: Node, root: Node): boolean {
  const element = node.nodeType === Node.TEXT_NODE ? node.parentNode : node
  if (!element || !(element instanceof Node)) {
    return false
  }
  return root.contains(element)
}

function closestSelectionBoundary(node: Node, selector: string): Element | null {
  const element = node.nodeType === Node.TEXT_NODE ? node.parentElement : node
  return element instanceof Element ? element.closest(selector) : null
}

export function extractSourceTextRangeFromRange(
  range: Range,
  options?: {
    containmentRoot?: Node | null
    selectionBoundarySelector?: string
    isRangeEnabledSentence?: (sentenceSpan: HTMLElement) => boolean
  },
): SourceTextSelectionResult {
  const isRangeEnabledSentence =
    options?.isRangeEnabledSentence ?? isRangeEnabledSentenceSpan

  if (options?.containmentRoot) {
    if (
      !isNodeContainedInRoot(range.startContainer, options.containmentRoot) ||
      !isNodeContainedInRoot(range.endContainer, options.containmentRoot)
    ) {
      return { supported: false, reason: 'outside-root' }
    }
  }

  if (options?.selectionBoundarySelector) {
    const startBoundary = closestSelectionBoundary(
      range.startContainer,
      options.selectionBoundarySelector,
    )
    const endBoundary = closestSelectionBoundary(
      range.endContainer,
      options.selectionBoundarySelector,
    )
    if (!startBoundary || startBoundary !== endBoundary) {
      return { supported: false, reason: 'cross-boundary' }
    }
  }

  const startSentence = findSentenceSpan(range.startContainer)
  const endSentence = findSentenceSpan(range.endContainer)
  if (!startSentence || !endSentence) {
    return { supported: false, reason: 'outside-sentence' }
  }
  if (startSentence !== endSentence) {
    return { supported: false, reason: 'cross-sentence' }
  }
  if (!isRangeEnabledSentence(startSentence)) {
    return { supported: false, reason: 'range-disabled-block' }
  }

  const sentenceText = collectSentenceSourceText(startSentence)
  const startUtf16 = sentenceLocalUtf16Offset(
    startSentence,
    range.startContainer,
    range.startOffset,
  )
  const endUtf16 = sentenceLocalUtf16Offset(
    startSentence,
    range.endContainer,
    range.endOffset,
  )
  if (startUtf16 === null || endUtf16 === null) {
    return { supported: false, reason: 'invalid-offset' }
  }

  if (startUtf16 === endUtf16) {
    return { supported: false, reason: 'collapsed-selection' }
  }

  try {
    const startOffset = utf16OffsetToCodePointOffset(sentenceText, startUtf16)
    const endOffset = utf16OffsetToCodePointOffset(sentenceText, endUtf16)
    const normalized = normalizeSourceTextRange(startOffset, endOffset)
    const identity = readSentenceDocumentIdentity(startSentence)
    return {
      supported: true,
      range: normalized,
      sentenceId: startSentence.getAttribute('data-sentence-id') ?? '',
      ...(identity.slotId ? { slotId: identity.slotId } : {}),
      ...(identity.docId ? { docId: identity.docId } : {}),
    }
  } catch {
    return { supported: false, reason: 'invalid-offset' }
  }
}

export function extractSourceTextRangeFromSelection(
  selection: Selection | null,
  options?: {
    containmentRoot?: Node | null
    selectionBoundarySelector?: string
    isRangeEnabledSentence?: (sentenceSpan: HTMLElement) => boolean
  },
): SourceTextSelectionResult {
  if (!selection || selection.rangeCount === 0) {
    return { supported: false, reason: 'no-selection' }
  }

  return extractSourceTextRangeFromRange(selection.getRangeAt(0), options)
}

export function createDomRangeForSourceTextRange(
  sentenceSpan: HTMLElement,
  range: SourceTextRange,
): Range | null {
  const sentenceText = collectSentenceSourceText(sentenceSpan)
  try {
    const startUtf16 = codePointOffsetToUtf16Offset(sentenceText, range.startOffset)
    const endUtf16 = codePointOffsetToUtf16Offset(sentenceText, range.endOffset)
    let accumulated = 0
    let startNode: Text | null = null
    let startOffset = 0
    let endNode: Text | null = null
    let endOffset = 0

    for (const textNode of collectTextNodes(sentenceSpan)) {
      const nodeStart = accumulated
      const nodeEnd = accumulated + textNode.data.length

      if (startNode === null && startUtf16 >= nodeStart && startUtf16 <= nodeEnd) {
        startNode = textNode
        startOffset = startUtf16 - nodeStart
      }
      if (endNode === null && endUtf16 >= nodeStart && endUtf16 <= nodeEnd) {
        endNode = textNode
        endOffset = endUtf16 - nodeStart
      }

      accumulated = nodeEnd
    }

    if (!startNode || !endNode) {
      return null
    }

    const domRange = document.createRange()
    domRange.setStart(startNode, startOffset)
    domRange.setEnd(endNode, endOffset)
    return domRange
  } catch {
    return null
  }
}
