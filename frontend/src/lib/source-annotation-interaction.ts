const SOURCE_ANNOTATION_INTERACTION_SELECTORS = [
  '[data-source-persisted-mark="true"]',
  '[data-source-comment-icon="true"]',
  '[data-source-edit-group="true"]',
  '[data-source-mark-action="true"]',
  '[data-source-comment-popover="true"]',
  '[data-source-edit-popover="true"]',
  '[data-source-annotation-navigator="true"]',
] as const

export function resolveMouseEventInteractionElement(
  target: EventTarget | null,
): Element | null {
  if (target instanceof Element) {
    return target
  }
  if (target instanceof Text) {
    return target.parentElement
  }
  return null
}

export function isSourceAnnotationInteractionElement(
  interactionElement: Element | null,
): boolean {
  if (!interactionElement) {
    return false
  }

  return SOURCE_ANNOTATION_INTERACTION_SELECTORS.some((selector) =>
    interactionElement.closest(selector),
  )
}

/**
 * Navigator active annotation emphasis clears only on generic document
 * interaction. Annotation controls stop bubbling and handle activation locally.
 */
export function shouldClearActiveSourceAnnotationOnDocumentMouseUp(
  interactionElement: Element | null,
): boolean {
  return !isSourceAnnotationInteractionElement(interactionElement)
}

export function shouldActivateFindingTarget(event: {
  target: EventTarget | null
}): boolean {
  const interactionElement = resolveMouseEventInteractionElement(event.target)
  if (isSourceAnnotationInteractionElement(interactionElement)) {
    return false
  }
  const selection = typeof window === 'undefined' ? null : window.getSelection()
  if (selection && !selection.isCollapsed) {
    return false
  }
  return true
}
