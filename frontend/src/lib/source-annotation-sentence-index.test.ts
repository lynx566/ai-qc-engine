import { describe, expect, it } from 'vitest'

import {
  buildCommentAnnotationsBySentenceId,
  selectSourceAnnotationsForBlock,
} from '@/lib/source-annotation-sentence-index'
import type { SourceAnnotation } from '@/types/source-annotation'

function comment(annotationId: string, blockId: string): SourceAnnotation {
  return {
    annotationId,
    anchor: {
      slotId: 'source',
      docId: 'doc-a',
      blockId,
      sentenceId: 'shared:S1',
    },
    kind: 'comment',
    content: annotationId,
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
  }
}

describe('source annotation sentence index', () => {
  it('selects annotations by canonical source block as well as sentence identity', () => {
    const first = comment('ann-first', 'B1')
    const second = comment('ann-second', 'B2')
    const documentIndex = buildCommentAnnotationsBySentenceId(
      [first, second],
      'source',
      'doc-a',
    )

    expect(selectSourceAnnotationsForBlock(documentIndex, 'B1')).toEqual(
      new Map([['shared:S1', [first]]]),
    )
    expect(selectSourceAnnotationsForBlock(documentIndex, 'B2')).toEqual(
      new Map([['shared:S1', [second]]]),
    )
  })
})
