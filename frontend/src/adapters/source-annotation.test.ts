import { describe, expect, it } from 'vitest'

import {
  adaptSourceAnnotationState,
  serializeSourceSentenceAnchor,
} from '@/adapters/source-annotation'

describe('adaptSourceAnnotationState', () => {
  it('adapts empty state', () => {
    const adapted = adaptSourceAnnotationState({
      flow_run_id: 'document_consistency_qc_test',
      annotations: {},
    })
    expect(adapted.flowRunId).toBe('document_consistency_qc_test')
    expect(adapted.annotationsById.size).toBe(0)
  })

  it('preserves canonical anchor fields in camelCase', () => {
    const adapted = adaptSourceAnnotationState({
      flow_run_id: 'document_consistency_qc_test',
      annotations: {
        ann_1: {
          annotation_id: 'ann_1',
          anchor: {
            slot_id: 'source',
            doc_id: 'doc_test',
            block_id: 'C0002',
            sentence_id: 'C0002:S001',
          },
          created_at: '2026-09-13T00:00:00Z',
          updated_at: '2026-09-13T00:00:00Z',
        },
      },
    })
    const entry = adapted.annotationsById.get('ann_1')
    expect(entry?.anchor).toEqual({
      slotId: 'source',
      docId: 'doc_test',
      blockId: 'C0002',
      sentenceId: 'C0002:S001',
    })
  })
})

describe('adaptSourceAnnotation optional range', () => {
  it('preserves optional range in camelCase', () => {
    const adapted = adaptSourceAnnotationState({
      flow_run_id: 'document_consistency_qc_test',
      annotations: {
        ann_1: {
          annotation_id: 'ann_1',
          anchor: {
            slot_id: 'source',
            doc_id: 'doc_test',
            block_id: 'C0002',
            sentence_id: 'C0002:S001',
          },
          range: {
            start_offset: 2,
            end_offset: 5,
          },
          created_at: '2026-09-13T00:00:00Z',
          updated_at: '2026-09-13T00:00:00Z',
        },
      },
    })
    const entry = adapted.annotationsById.get('ann_1')
    expect(entry?.range).toEqual({
      startOffset: 2,
      endOffset: 5,
    })
  })
})

describe('adaptSourceAnnotation highlight kind', () => {
  it('preserves highlight kind and range', () => {
    const adapted = adaptSourceAnnotationState({
      flow_run_id: 'document_consistency_qc_test',
      annotations: {
        ann_1: {
          annotation_id: 'ann_1',
          anchor: {
            slot_id: 'source',
            doc_id: 'doc_test',
            block_id: 'C0002',
            sentence_id: 'C0002:S001',
          },
          kind: 'highlight',
          range: { start_offset: 0, end_offset: 2 },
          created_at: '2026-09-13T00:00:00Z',
          updated_at: '2026-09-13T00:00:00Z',
        },
      },
    })
    const entry = adapted.annotationsById.get('ann_1')
    expect(entry?.kind).toBe('highlight')
    expect(entry?.range).toEqual({ startOffset: 0, endOffset: 2 })
  })
})

describe('adaptSourceAnnotation comment kind', () => {
  it('preserves comment kind and content without range', () => {
    const adapted = adaptSourceAnnotationState({
      flow_run_id: 'document_consistency_qc_test',
      annotations: {
        ann_1: {
          annotation_id: 'ann_1',
          anchor: {
            slot_id: 'source',
            doc_id: 'doc_test',
            block_id: 'C0002',
            sentence_id: 'C0002:S001',
          },
          kind: 'comment',
          content: '这里应改为80.0%',
          created_at: '2026-09-13T00:00:00Z',
          updated_at: '2026-09-13T00:00:00Z',
        },
      },
    })
    const entry = adapted.annotationsById.get('ann_1')
    expect(entry?.kind).toBe('comment')
    expect(entry?.content).toBe('这里应改为80.0%')
    expect(entry?.range).toBeUndefined()
  })
})

describe('serializeSourceSentenceAnchor', () => {
  it('serializes extract local block_id without composed doc prefix', () => {
    const serialized = serializeSourceSentenceAnchor({
      slotId: 'source',
      docId: 'doc_test',
      blockId: 'C0002',
      sentenceId: 'C0002:S001',
    })
    expect(serialized.block_id).toBe('C0002')
    expect(serialized.block_id).not.toContain(':')
  })
})
