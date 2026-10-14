export type SourceSentenceAnchor = {
  slotId: string
  docId: string
  blockId: string
  sentenceId: string
}

export type SourceTextRange = {
  startOffset: number
  endOffset: number
}

export type SourceAnnotationKind = 'highlight' | 'comment' | 'edit'

export type SourceAnnotation = {
  annotationId: string
  anchor: SourceSentenceAnchor
  createdAt: string
  updatedAt: string
  kind?: SourceAnnotationKind
  range?: SourceTextRange
  content?: string
  replacementText?: string
}

export type SourceAnnotationStatePayload = {
  flowRunId: string
  annotationsById: Map<string, SourceAnnotation>
}
