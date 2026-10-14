import { codePointLength } from '@/lib/source-text-range'
import { isRenderableHighlightAnnotation } from '@/lib/source-highlight-renderer'
import { isRenderableEditAnnotation } from '@/lib/source-edit'
import type { SourceAnnotation } from '@/types/source-annotation'

const TERMINAL_PUNCTUATION_RE = /[。；！？;!?]$/

export function splitSentenceTerminalPunctuation(rawText: string): {
  sourceBody: string
  terminalPunctuation: string
} {
  if (!rawText) {
    return { sourceBody: '', terminalPunctuation: '' }
  }
  const lastChar = rawText.slice(-1)
  if (TERMINAL_PUNCTUATION_RE.test(lastChar)) {
    return {
      sourceBody: rawText.slice(0, -1),
      terminalPunctuation: lastChar,
    }
  }
  return { sourceBody: rawText, terminalPunctuation: '' }
}

export function clipHighlightsToSourceBody(
  highlights: readonly SourceAnnotation[],
  sourceBody: string,
): SourceAnnotation[] {
  const bodyLength = codePointLength(sourceBody)
  const clipped: SourceAnnotation[] = []

  for (const highlight of highlights) {
    if (!isRenderableHighlightAnnotation(highlight) || !highlight.range) {
      continue
    }
    const startOffset = highlight.range.startOffset
    const endOffset = Math.min(highlight.range.endOffset, bodyLength)
    if (startOffset >= bodyLength || endOffset <= startOffset) {
      continue
    }
    clipped.push({
      ...highlight,
      range: {
        startOffset,
        endOffset,
      },
    })
  }

  return clipped
}

export function clipCommentsToSourceBody(
  comments: readonly SourceAnnotation[],
  sourceBody: string,
): SourceAnnotation[] {
  const bodyLength = codePointLength(sourceBody)
  const clipped: SourceAnnotation[] = []

  for (const comment of comments) {
    if (!comment.range) {
      continue
    }
    const startOffset = comment.range.startOffset
    const endOffset = Math.min(comment.range.endOffset, bodyLength)
    if (startOffset >= bodyLength || endOffset <= startOffset) {
      continue
    }
    clipped.push({
      ...comment,
      range: {
        startOffset,
        endOffset,
      },
    })
  }

  return clipped
}

export function clipEditsToSourceBody(
  edits: readonly SourceAnnotation[],
  sourceBody: string,
): SourceAnnotation[] {
  const bodyLength = codePointLength(sourceBody)
  const clipped: SourceAnnotation[] = []

  for (const edit of edits) {
    if (!isRenderableEditAnnotation(edit) || !edit.range) {
      continue
    }
    const startOffset = edit.range.startOffset
    const endOffset = Math.min(edit.range.endOffset, bodyLength)
    if (startOffset >= bodyLength || endOffset <= startOffset) {
      continue
    }
    clipped.push({
      ...edit,
      range: {
        startOffset,
        endOffset,
      },
    })
  }

  return clipped
}

export function isSourceAnnotationUiElement(element: Element | null): boolean {
  if (!element) {
    return false
  }
  return (
    element.closest('[data-source-comment-icon="true"]') !== null ||
    element.closest('[data-source-annotation-ui="true"]') !== null ||
    element.closest('[data-source-ui="true"]') !== null
  )
}

export function collectSentenceSourceText(sentenceSpan: HTMLElement): string {
  const parts: string[] = []
  const walker = document.createTreeWalker(sentenceSpan, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement
      if (isSourceAnnotationUiElement(parent)) {
        return NodeFilter.FILTER_REJECT
      }
      return NodeFilter.FILTER_ACCEPT
    },
  })

  let current = walker.nextNode()
  while (current) {
    if (current.nodeType === Node.TEXT_NODE) {
      parts.push(current.textContent ?? '')
    }
    current = walker.nextNode()
  }

  return parts.join('')
}
