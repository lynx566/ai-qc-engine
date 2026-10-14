export type ResultDocumentRenderer = 'canonical' | 'evidence_viewports'

export type ResultDocumentCapabilities = {
  directory: boolean
  annotationContext: boolean
  annotationNavigator: boolean
}

export function deriveResultDocumentCapabilities(
  renderer: ResultDocumentRenderer,
): ResultDocumentCapabilities {
  if (renderer === 'canonical') {
    return { directory: true, annotationContext: true, annotationNavigator: true }
  }

  return { directory: false, annotationContext: true, annotationNavigator: false }
}
