// @vitest-environment happy-dom

import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

import { SourceSectionReader } from '@/components/review/source-section-reader'
import { DocumentReader } from '@/components/review/document-reader'
import { blockDomId } from '@/lib/document-anchors'
import {
  deriveSourceEvidenceViewportDescriptors,
  sourceBlockRenderId,
  sourceSentenceRenderId,
} from '@/lib/source-evidence-viewport'
import type { DocumentBlock, DocumentView } from '@/types/document-review'
import type { SourceAnnotation } from '@/types/source-annotation'

globalThis.IS_REACT_ACT_ENVIRONMENT = true

function textBlock(
  sourceBlockId: string,
  kind: DocumentBlock['kind'],
  docOrderIndex: number,
  text: string,
  headingLevel?: DocumentBlock['headingLevel'],
): DocumentBlock {
  return {
    blockId: `doc-a:${sourceBlockId}`,
    sourceBlockId,
    kind,
    docOrderIndex,
    headingLevel,
    headingPath: ['Section one'],
    displayText: text,
    sentences: [{
      sentenceId: `${sourceBlockId}:S1`,
      rawText: text,
      normalizedText: text,
    }],
  }
}

const documentView: DocumentView = {
  docId: 'doc-a',
  fileName: 'doc-a.docx',
  displayName: 'Document A',
  blocks: [
    textBlock('H1', 'heading', 0, 'Section one', 1),
    textBlock('P1', 'paragraph', 1, 'Before evidence.'),
    textBlock('L1', 'list_item', 2, 'First item.'),
    textBlock('L2', 'list_item', 3, 'Second item.'),
    textBlock('CAP1', 'table_caption', 4, 'Table caption.'),
    {
      blockId: 'doc-a:T1',
      sourceBlockId: 'T1',
      kind: 'table',
      docOrderIndex: 5,
      headingPath: ['Section one'],
      table: { rows: [['Column A', 'Column B'], ['A1', 'B1']] },
    },
    textBlock('NOTE1', 'table_note', 6, 'Table note.'),
    textBlock('H2', 'heading', 7, 'Nested heading', 2),
    textBlock('P2', 'paragraph', 8, 'Primary evidence.'),
    textBlock('P3', 'paragraph', 9, 'After evidence.'),
    textBlock('H3', 'heading', 10, 'Next section', 1),
    textBlock('P4', 'paragraph', 11, 'Excluded content.'),
  ],
}

describe('SourceSectionReader', () => {
  const sourceWithToc: DocumentView = {
    ...documentView,
    blocks: [
      textBlock('C0006', 'heading', 0, '执行概要', 1),
      textBlock('C0007', 'paragraph', 1, 'Body before evidence.'),
      textBlock('C0009', 'paragraph', 2, 'Primary evidence.'),
      textBlock('C0011', 'paragraph', 3, 'Body after evidence.'),
      textBlock('M0001', 'toc', 4, '目录'),
      textBlock('M0002', 'toc', 5, '1.前言\t4'),
      textBlock('C0012', 'heading', 6, '1.前言', 1),
    ],
  }

  it('projects body evidence before TOC and retains its alias, location and focused highlight', () => {
    const evidence = {
      slotId: 'source', docId: 'doc-a', blockId: 'C0009',
      sentenceId: 'C0009:S1', sentenceAlias: 'T0002',
    }
    const [descriptor] = deriveSourceEvidenceViewportDescriptors({
      findingId: 'L001', slotId: 'source', document: sourceWithToc,
      evidenceLocations: [evidence],
    })
    expect(descriptor).toMatchObject({
      sourceBlockId: 'C0009', sourceBlockIndex: 2,
      evidenceSentenceId: 'C0009:S1', evidenceSentenceIndex: 0,
      sectionHeadingSourceBlockId: 'C0006',
      sectionStartBlockIndex: 0, sectionEndBlockIndexExclusive: 4,
    })
    expect(evidence).toEqual({
      slotId: 'source', docId: 'doc-a', blockId: 'C0009',
      sentenceId: 'C0009:S1', sentenceAlias: 'T0002',
    })

    const root = document.createElement('div')
    root.innerHTML = renderToStaticMarkup(createElement(SourceSectionReader, {
      document: sourceWithToc, slotId: descriptor!.slotId,
      viewportKey: descriptor!.viewportKey,
      sectionStartBlockIndex: descriptor!.sectionStartBlockIndex,
      sectionEndBlockIndexExclusive: descriptor!.sectionEndBlockIndexExclusive,
      primaryEvidenceSentenceId: descriptor!.evidenceSentenceId,
    }))
    expect([...root.querySelectorAll('[data-block-id]')].map((entry) =>
      entry.getAttribute('data-block-id'))).toEqual(['C0006', 'C0007', 'C0009', 'C0011'])
    expect(root.querySelector('nav[aria-label="Table of contents"]')).toBeNull()
    const sentence = root.querySelector<HTMLElement>('[data-sentence-id="C0009:S1"]')
    expect(sentence?.textContent).toBe('Primary evidence.')
    expect(sentence?.dataset.findingTarget).toBe('true')
    expect(sentence?.dataset.focusedFindingTarget).toBe('true')
  })

  it('keeps TOC renderable in Full Document after projecting evidence context', () => {
    deriveSourceEvidenceViewportDescriptors({
      findingId: 'L001', slotId: 'source', document: sourceWithToc,
      evidenceLocations: [{
        slotId: 'source', docId: 'doc-a', blockId: 'C0009',
        sentenceId: 'C0009:S1', sentenceAlias: 'T0002',
      }],
    })
    const root = document.createElement('div')
    root.innerHTML = renderToStaticMarkup(createElement(DocumentReader, {
      document: sourceWithToc, slotId: 'source',
    }))
    const toc = root.querySelector('nav[aria-label="Table of contents"]')
    expect(toc?.textContent).toContain('目录')
    expect(toc?.textContent).toContain('1.前言')
    expect(toc?.querySelector(`[id="${blockDomId('doc-a:M0001')}"]`)).not.toBeNull()
    expect(toc?.querySelector(`[id="${blockDomId('doc-a:M0002')}"]`)).not.toBeNull()
    expect(root.querySelector(`[id="${blockDomId('doc-a:C0012')}"]`)).not.toBeNull()
  })

  it('renders the complete canonical section slice with instance-aware identities', () => {
    const html = renderToStaticMarkup(createElement(SourceSectionReader, {
      document: documentView,
      slotId: 'source',
      viewportKey: 'viewport-a',
      sectionStartBlockIndex: 0,
      sectionEndBlockIndexExclusive: 10,
      primaryEvidenceSentenceId: 'P2:S1',
    }))
    const root = document.createElement('div')
    root.innerHTML = html

    expect(root.textContent).toContain('Section one')
    expect(root.textContent).toContain('Before evidence.')
    expect(root.textContent).toContain('Nested heading')
    expect(root.textContent).toContain('Primary evidence.')
    expect(root.textContent).toContain('After evidence.')
    expect(root.textContent).not.toContain('Next section')
    expect(root.textContent).not.toContain('Excluded content.')

    expect(root.querySelectorAll('ul')).toHaveLength(1)
    expect(root.querySelectorAll('ul > li')).toHaveLength(2)
    expect(root.querySelector('table')).not.toBeNull()
    expect(root.querySelector('table')?.textContent).toContain('A1')

    const caption = root.querySelector('[data-block-id="CAP1"]')
    const table = root.querySelector('[data-block-id="T1"]')
    const note = root.querySelector('[data-block-id="NOTE1"]')
    expect(caption?.compareDocumentPosition(table!)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
    expect(table?.compareDocumentPosition(note!)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)

    const evidenceBlock = root.querySelector<HTMLElement>('[data-block-id="P2"]')
    expect(evidenceBlock?.id).toBe(sourceBlockRenderId('viewport-a', 'P2'))
    expect(evidenceBlock?.dataset.slotId).toBe('source')
    expect(evidenceBlock?.dataset.docId).toBe('doc-a')

    const evidenceSentence = root.querySelector<HTMLElement>('[data-sentence-id="P2:S1"]')
    expect(evidenceSentence?.id).toBe(
      sourceSentenceRenderId('viewport-a', 'doc-a', 'P2:S1'),
    )
    expect(evidenceSentence?.dataset.slotId).toBe('source')
    expect(evidenceSentence?.dataset.docId).toBe('doc-a')
    expect(evidenceSentence?.dataset.findingTarget).toBe('true')
    expect(evidenceSentence?.dataset.focusedFindingTarget).toBe('true')
  })

  it('omits the leading section heading when viewport chrome already shows it', () => {
    const html = renderToStaticMarkup(createElement(SourceSectionReader, {
      document: documentView,
      slotId: 'source',
      viewportKey: 'viewport-a',
      sectionStartBlockIndex: 0,
      sectionEndBlockIndexExclusive: 10,
      primaryEvidenceSentenceId: 'P2:S1',
      omitLeadingSectionHeadingSourceBlockId: 'H1',
      compactViewportPresentation: true,
    }))
    const root = document.createElement('div')
    root.innerHTML = html

    expect(root.querySelector('[data-block-id="H1"]')).toBeNull()
    expect(root.textContent).toContain('Before evidence.')
    expect(root.textContent).toContain('Primary evidence.')
    expect(root.querySelector('[data-source-section-reader="true"]')).not.toBeNull()
  })

  it('renders source annotations and delegates persisted mark interaction', () => {
    const annotation: SourceAnnotation = {
      annotationId: 'highlight-a',
      kind: 'highlight',
      anchor: {
        slotId: 'source',
        docId: 'doc-a',
        blockId: 'P2',
        sentenceId: 'P2:S1',
      },
      range: { startOffset: 0, endOffset: 7 },
      createdAt: '2026-01-01T00:00:00Z',
      updatedAt: '2026-01-01T00:00:00Z',
    }
    const onPersistedMarkClick = vi.fn()
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)

    act(() => root.render(createElement(SourceSectionReader, {
      document: documentView,
      slotId: 'source',
      viewportKey: 'viewport-a',
      sectionStartBlockIndex: 0,
      sectionEndBlockIndexExclusive: 10,
      primaryEvidenceSentenceId: 'P2:S1',
      sourceAnnotations: new Map([[annotation.annotationId, annotation]]),
      interactionHandlers: {
        onPersistedMarkClick,
        onCommentIconClick: vi.fn(),
        onEditInlineClick: vi.fn(),
      },
    })))

    const mark = container.querySelector<HTMLElement>('[data-source-persisted-mark="true"]')
    expect(mark).not.toBeNull()
    act(() => mark?.dispatchEvent(new MouseEvent('mouseup', { bubbles: true })))
    expect(onPersistedMarkClick).toHaveBeenCalledWith('highlight-a', mark)

    act(() => root.unmount())
    container.remove()
  })
})
