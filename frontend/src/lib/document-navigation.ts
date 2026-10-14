import { blockDomId, sentenceDomId } from '@/lib/document-anchors'

export type SentenceNavigationTarget = {
  docId: string
  blockId: string
  sentenceId: string
}

export type SentenceScrollResult = 'sentence' | 'block'

/** Applied to DocumentReader scroll viewport; pairs with block:"start" scrollIntoView. */
export const documentReaderScrollAnchorClassName = 'scroll-pt-[28%]'

export const documentNavigationScrollIntoViewOptions: ScrollIntoViewOptions = {
  behavior: 'smooth',
  block: 'start',
}

export function scrollElementIntoReaderView(element: HTMLElement): void {
  element.scrollIntoView(documentNavigationScrollIntoViewOptions)
  element.focus({ preventScroll: true })
}

export function scrollToSentenceTarget(
  target: SentenceNavigationTarget,
  options: {
    scrollToBlock: (blockId: string) => void
    rootDocument?: Document
  },
): SentenceScrollResult {
  const rootDocument = options.rootDocument ?? window.document
  const sentenceElement = rootDocument.getElementById(
    sentenceDomId(target.docId, target.sentenceId),
  )

  if (sentenceElement) {
    scrollElementIntoReaderView(sentenceElement)
    return 'sentence'
  }

  const blockElement = rootDocument.getElementById(blockDomId(target.blockId))
  if (blockElement) {
    options.scrollToBlock(target.blockId)
    return 'block'
  }

  options.scrollToBlock(target.blockId)
  return 'block'
}

export function scrollToSourceAnnotationElement(
  annotationId: string,
  fallbackTarget: SentenceNavigationTarget,
  options: {
    scrollToBlock: (blockId: string) => void
    rootDocument?: Document
  },
): SentenceScrollResult {
  const rootDocument = options.rootDocument ?? window.document
  const annotationElement = rootDocument.querySelector(
    `[data-source-annotation-id="${annotationId}"]`,
  )

  if (annotationElement instanceof HTMLElement) {
    scrollElementIntoReaderView(annotationElement)
    return 'sentence'
  }

  return scrollToSentenceTarget(fallbackTarget, options)
}
