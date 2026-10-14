import type {
  SourceAnnotation,
  SourceAnnotationKind,
  SourceAnnotationStatePayload,
  SourceSentenceAnchor,
  SourceTextRange,
} from '@/types/source-annotation'

type RawSourceSentenceAnchor = {
  slot_id: string
  doc_id: string
  block_id: string
  sentence_id: string
}

type RawSourceTextRange = {
  start_offset: number
  end_offset: number
}

type RawSourceAnnotation = {
  annotation_id: string
  anchor: RawSourceSentenceAnchor
  created_at: string
  updated_at: string
  kind?: SourceAnnotationKind
  range?: RawSourceTextRange
  content?: string
  replacement_text?: string
}

type RawSourceAnnotationStatePayload = {
  flow_run_id: string
  annotations: Record<string, RawSourceAnnotation>
}

export function adaptSourceSentenceAnchor(raw: RawSourceSentenceAnchor): SourceSentenceAnchor {
  return {
    slotId: raw.slot_id,
    docId: raw.doc_id,
    blockId: raw.block_id,
    sentenceId: raw.sentence_id,
  }
}

export function adaptSourceTextRange(raw: RawSourceTextRange): SourceTextRange {
  return {
    startOffset: raw.start_offset,
    endOffset: raw.end_offset,
  }
}

export function adaptSourceAnnotation(raw: RawSourceAnnotation): SourceAnnotation {
  return {
    annotationId: raw.annotation_id,
    anchor: adaptSourceSentenceAnchor(raw.anchor),
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    kind: raw.kind,
    range: raw.range ? adaptSourceTextRange(raw.range) : undefined,
    content: raw.content,
    replacementText: raw.replacement_text,
  }
}

export function adaptSourceAnnotationState(
  raw: RawSourceAnnotationStatePayload,
): SourceAnnotationStatePayload {
  const annotationsById = new Map<string, SourceAnnotation>()
  for (const entry of Object.values(raw.annotations ?? {})) {
    annotationsById.set(entry.annotation_id, adaptSourceAnnotation(entry))
  }
  return {
    flowRunId: raw.flow_run_id,
    annotationsById,
  }
}

export function serializeSourceSentenceAnchor(
  anchor: SourceSentenceAnchor,
): RawSourceSentenceAnchor {
  return {
    slot_id: anchor.slotId,
    doc_id: anchor.docId,
    block_id: anchor.blockId,
    sentence_id: anchor.sentenceId,
  }
}

export function serializeSourceTextRange(range: SourceTextRange): RawSourceTextRange {
  return {
    start_offset: range.startOffset,
    end_offset: range.endOffset,
  }
}
