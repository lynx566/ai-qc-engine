// @vitest-environment happy-dom

import { createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { act } from 'react'
import { describe, expect, it } from 'vitest'

import { SentenceMarkedText } from '@/components/review/sentence-marked-text'
import type { SourceAnnotation } from '@/types/source-annotation'

const anchor = {
  slotId: 'source',
  docId: 'doc_test',
  blockId: 'C0002',
  sentenceId: 'C0002:S001',
}

describe('comment and edit overlap DOM order', () => {
  it('renders comment icon before replacement when ranges share edit end', () => {
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)

    const commentAnnotation: SourceAnnotation = {
      annotationId: 'ann_comment',
      anchor,
      kind: 'comment',
      content: 'note',
      range: { startOffset: 6, endOffset: 11 },
      createdAt: '2026-09-13T00:00:00Z',
      updatedAt: '2026-09-13T00:00:00Z',
    }
    const editAnnotation: SourceAnnotation = {
      annotationId: 'ann_edit',
      anchor,
      kind: 'edit',
      range: { startOffset: 6, endOffset: 11 },
      replacementText: '80.0%',
      createdAt: '2026-09-13T00:00:00Z',
      updatedAt: '2026-09-13T00:00:00Z',
    }

    act(() => {
      root.render(
        createElement(SentenceMarkedText, {
          docId: 'doc_test',
          displayText: 'ADR发生率为70.0%。',
          mode: 'paragraph',
          sentences: [
            {
              sentenceId: 'C0002:S001',
              rawText: 'ADR发生率为70.0%。',
              normalizedText: 'ADR发生率为70.0%。',
            },
          ],
          commentAnnotationsBySentenceId: new Map([['C0002:S001', [commentAnnotation]]]),
          editAnnotationsBySentenceId: new Map([['C0002:S001', [editAnnotation]]]),
        }),
      )
    })

    const html = container.innerHTML
    const iconIndex = html.indexOf('data-source-comment-icon="true"')
    const replacementIndex = html.indexOf('data-source-annotation-ui="true"')
    expect(iconIndex).toBeGreaterThan(-1)
    expect(replacementIndex).toBeGreaterThan(-1)
    expect(iconIndex).toBeLessThan(replacementIndex)
  })
})
