import {
  adaptSourceAnnotation,
  adaptSourceAnnotationState,
  serializeSourceSentenceAnchor,
  serializeSourceTextRange,
} from '@/adapters/source-annotation'
import { throwDocumentConsistencyQcResponseError } from '@/api/document-consistency-qc-error'
import type {
  SourceAnnotation,
  SourceAnnotationStatePayload,
  SourceSentenceAnchor,
  SourceTextRange,
} from '@/types/source-annotation'

export type CreateSourceHighlightInput = {
  anchor: SourceSentenceAnchor
  range: SourceTextRange
}

export type CreateSourceCommentInput = {
  anchor: SourceSentenceAnchor
  range: SourceTextRange
  content: string
}

export type CreateSourceEditInput = {
  anchor: SourceSentenceAnchor
  range: SourceTextRange
  replacementText: string
}

export type UpdateSourceCommentInput = {
  annotationId: string
  content: string
}

export type UpdateSourceEditInput = {
  annotationId: string
  replacementText: string
}

const API_BASE = '/api/document-consistency-qc'

export async function fetchSourceAnnotations(
  flowRunId: string,
): Promise<SourceAnnotationStatePayload> {
  const params = new URLSearchParams({
    flow_run_id: flowRunId,
  })
  const response = await fetch(`${API_BASE}/source-annotations?${params.toString()}`)
  if (!response.ok) {
    await throwDocumentConsistencyQcResponseError(response, '源标注加载失败')
  }
  const payload = await response.json()
  return adaptSourceAnnotationState(payload)
}

export async function createSourceAnnotation(
  flowRunId: string,
  anchor: SourceSentenceAnchor,
  range?: SourceTextRange,
): Promise<SourceAnnotation> {
  const body: {
    flow_run_id: string
    anchor: ReturnType<typeof serializeSourceSentenceAnchor>
    range?: ReturnType<typeof serializeSourceTextRange>
  } = {
    flow_run_id: flowRunId,
    anchor: serializeSourceSentenceAnchor(anchor),
  }
  if (range) {
    body.range = serializeSourceTextRange(range)
  }

  const response = await fetch(`${API_BASE}/source-annotations`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    await throwDocumentConsistencyQcResponseError(response, '源标注创建失败')
  }
  const payload = await response.json()
  return adaptSourceAnnotation(payload)
}

export async function createSourceHighlight(
  flowRunId: string,
  input: CreateSourceHighlightInput,
): Promise<SourceAnnotation> {
  const response = await fetch(`${API_BASE}/source-annotations`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      flow_run_id: flowRunId,
      kind: 'highlight',
      anchor: serializeSourceSentenceAnchor(input.anchor),
      range: serializeSourceTextRange(input.range),
    }),
  })
  if (!response.ok) {
    await throwDocumentConsistencyQcResponseError(response, '高亮创建失败')
  }
  const payload = await response.json()
  return adaptSourceAnnotation(payload)
}

export async function createSourceComment(
  flowRunId: string,
  input: CreateSourceCommentInput,
): Promise<SourceAnnotation> {
  const response = await fetch(`${API_BASE}/source-annotations`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      flow_run_id: flowRunId,
      kind: 'comment',
      anchor: serializeSourceSentenceAnchor(input.anchor),
      range: serializeSourceTextRange(input.range),
      content: input.content,
    }),
  })
  if (!response.ok) {
    await throwDocumentConsistencyQcResponseError(response, '批注创建失败')
  }
  const payload = await response.json()
  return adaptSourceAnnotation(payload)
}

export async function createSourceEdit(
  flowRunId: string,
  input: CreateSourceEditInput,
): Promise<SourceAnnotation> {
  const response = await fetch(`${API_BASE}/source-annotations`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      flow_run_id: flowRunId,
      kind: 'edit',
      anchor: serializeSourceSentenceAnchor(input.anchor),
      range: serializeSourceTextRange(input.range),
      replacement_text: input.replacementText.trim(),
    }),
  })
  if (!response.ok) {
    await throwDocumentConsistencyQcResponseError(response, '修订创建失败')
  }
  const payload = await response.json()
  return adaptSourceAnnotation(payload)
}

export async function patchSourceAnnotationContent(
  flowRunId: string,
  input: UpdateSourceCommentInput,
): Promise<SourceAnnotation> {
  const response = await fetch(`${API_BASE}/source-annotations`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      flow_run_id: flowRunId,
      annotation_id: input.annotationId,
      content: input.content,
    }),
  })
  if (!response.ok) {
    await throwDocumentConsistencyQcResponseError(response, '批注保存失败')
  }
  const payload = await response.json()
  return adaptSourceAnnotation(payload)
}

export async function patchSourceAnnotationReplacementText(
  flowRunId: string,
  input: UpdateSourceEditInput,
): Promise<SourceAnnotation> {
  const response = await fetch(`${API_BASE}/source-annotations`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      flow_run_id: flowRunId,
      annotation_id: input.annotationId,
      replacement_text: input.replacementText.trim(),
    }),
  })
  if (!response.ok) {
    await throwDocumentConsistencyQcResponseError(response, '修订保存失败')
  }
  const payload = await response.json()
  return adaptSourceAnnotation(payload)
}

export async function deleteSourceAnnotation(
  flowRunId: string,
  annotationId: string,
): Promise<SourceAnnotationStatePayload> {
  const params = new URLSearchParams({
    flow_run_id: flowRunId,
    annotation_id: annotationId,
  })
  const response = await fetch(`${API_BASE}/source-annotations?${params.toString()}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    await throwDocumentConsistencyQcResponseError(response, '源标注删除失败')
  }
  const payload = await response.json()
  return adaptSourceAnnotationState(payload)
}
