import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

import { describe, expect, it } from 'vitest'

import { composeDocumentBlockId } from '@/adapters/extract-document'
import { DocumentReader } from '@/components/review/document-reader'
import { blockDomId, sentenceDomId } from '@/lib/document-anchors'
import type { DocumentView } from '@/types/document-review'

function stripHtmlTags(html: string): string {
  return html.replace(/<[^>]+>/g, '')
}

/**
 * Paragraph blocks render inline sentence spans only; for this structure,
 * stripping tags inside the paragraph element equals browser textContent.
 */
function paragraphTextContentFromReaderHtml(html: string, blockId: string): string {
  const sectionId = blockDomId(blockId)
  const sectionMarker = `id="${sectionId}"`
  const sectionStart = html.indexOf(sectionMarker)
  if (sectionStart < 0) {
    throw new Error(`section ${sectionId} not found`)
  }

  const sectionOpenEnd = html.indexOf('>', sectionStart)
  const sectionCloseStart = html.indexOf('</section>', sectionOpenEnd)
  if (sectionOpenEnd < 0 || sectionCloseStart < 0) {
    throw new Error(`section ${sectionId} boundaries not found`)
  }

  const sectionHtml = html.slice(sectionOpenEnd + 1, sectionCloseStart)
  const paragraphOpenStart = sectionHtml.indexOf('<p')
  const paragraphOpenEnd = sectionHtml.indexOf('>', paragraphOpenStart)
  const paragraphCloseStart = sectionHtml.indexOf('</p>', paragraphOpenEnd)
  if (paragraphOpenStart < 0 || paragraphOpenEnd < 0 || paragraphCloseStart < 0) {
    throw new Error(`paragraph inside section ${sectionId} not found`)
  }

  const paragraphInnerHtml = sectionHtml.slice(paragraphOpenEnd + 1, paragraphCloseStart)
  return stripHtmlTags(paragraphInnerHtml)
}

function buildDocument(blocks: DocumentView['blocks']): DocumentView {
  return {
    docId: 'doc_test',
    fileName: 'sample.docx',
    displayName: 'sample.docx',
    blocks,
  }
}

function renderReader(document: DocumentView) {
  return renderToStaticMarkup(
    createElement(DocumentReader, {
      document,
      slotId: 'source',
    }),
  )
}

describe('DocumentReader sentence DOM', () => {
  it.each([
    {
      name: 'inter-sentence whitespace',
      displayText: '第一句。 第二句。',
      sentences: [
        { sentenceId: 'C0002:S001', rawText: '第一句。', normalizedText: '第一句。' },
        { sentenceId: 'C0002:S002', rawText: '第二句。', normalizedText: '第二句。' },
      ],
    },
    {
      name: 'newline between sentences',
      displayText: '上行内容\n下行内容。',
      sentences: [
        { sentenceId: 'C0002:S001', rawText: '上行内容', normalizedText: '上行内容' },
        { sentenceId: 'C0002:S002', rawText: '下行内容。', normalizedText: '下行内容。' },
      ],
    },
    {
      name: 'repeated newline between sentences',
      displayText: 'A\n\nB',
      sentences: [
        { sentenceId: 'C0002:S001', rawText: 'A', normalizedText: 'A' },
        { sentenceId: 'C0002:S002', rawText: 'B', normalizedText: 'B' },
      ],
    },
  ])(
    'preserves exact paragraph textContent after sentence spans ($name)',
    ({ displayText, sentences }) => {
      const blockId = composeDocumentBlockId('doc_test', 'C0002')
      const document = buildDocument([
        {
          blockId,
          sourceBlockId: 'C0002',
          kind: 'paragraph',
          docOrderIndex: 1,
          headingPath: ['Scope'],
          displayText,
          sentences,
        },
      ])

      const html = renderReader(document)
      expect(paragraphTextContentFromReaderHtml(html, blockId)).toBe(displayText)
    },
  )

  it('renders paragraph sentence spans with preserved text content', () => {
    const displayText = '第一句。 第二句。'
    const document = buildDocument([
      {
        blockId: composeDocumentBlockId('doc_test', 'C0002'),
        sourceBlockId: 'C0002',
        kind: 'paragraph',
        docOrderIndex: 1,
        headingPath: ['Scope'],
        displayText,
        sentences: [
          { sentenceId: 'C0002:S001', rawText: '第一句。', normalizedText: '第一句。' },
          { sentenceId: 'C0002:S002', rawText: '第二句。', normalizedText: '第二句。' },
        ],
      },
    ])

    const html = renderReader(document)
    expect(html).toContain('data-sentence-id="C0002:S001"')
    expect(html).toContain(`id="${sentenceDomId('doc_test', 'C0002:S001')}"`)
    expect(html).toContain('data-sentence-id="C0002:S002"')
    expect(paragraphTextContentFromReaderHtml(html, composeDocumentBlockId('doc_test', 'C0002'))).toBe(
      displayText,
    )
  })

  it('wraps heading displayText in a single sentence span', () => {
    const document = buildDocument([
      {
        blockId: composeDocumentBlockId('doc_test', 'C0010'),
        sourceBlockId: 'C0010',
        kind: 'heading',
        docOrderIndex: 1,
        headingLevel: 1,
        headingPath: ['1. 执行概要'],
        displayText: '1. 执行概要',
        sentences: [
          { sentenceId: 'C0010:S001', rawText: '执行概要', normalizedText: '1. 执行概要' },
        ],
      },
    ])

    const html = renderReader(document)
    expect(html).toContain('data-sentence-id="C0010:S001"')
    expect(stripHtmlTags(html)).toContain('1. 执行概要')
  })

  it('wraps list item whole-block sentence span', () => {
    const document = buildDocument([
      {
        blockId: composeDocumentBlockId('doc_test', 'C0020'),
        sourceBlockId: 'C0020',
        kind: 'list_item',
        docOrderIndex: 1,
        headingPath: ['Scope'],
        displayText: '1. 主要不良事件',
        sentences: [
          {
            sentenceId: 'C0020:S001',
            rawText: '1. 主要不良事件',
            normalizedText: '1. 主要不良事件',
          },
        ],
      },
    ])

    const html = renderReader(document)
    expect(html).toContain('data-sentence-id="C0020:S001"')
    expect(stripHtmlTags(html)).toContain('1. 主要不良事件')
  })

  it('does not render table sentence spans', () => {
    const document = buildDocument([
      {
        blockId: composeDocumentBlockId('doc_test', 'T0001'),
        sourceBlockId: 'T0001',
        kind: 'table',
        docOrderIndex: 1,
        headingPath: ['Scope'],
        table: {
          rows: [['A', 'B']],
        },
        sentences: [
          { sentenceId: 'T0001:S001', rawText: 'A | B', normalizedText: 'A | B' },
        ],
      },
    ])

    const html = renderReader(document)
    expect(html).not.toContain('data-sentence-id')
    expect(html).toContain('<table')
  })

  it('keeps toc rendering without sentence spans', () => {
    const document = buildDocument([
      {
        blockId: composeDocumentBlockId('doc_test', 'C0003'),
        sourceBlockId: 'C0003',
        kind: 'toc',
        docOrderIndex: 1,
        headingPath: [],
        displayText: '目录\t1',
        sentences: [{ sentenceId: 'C0003:S001', rawText: '目录\t1', normalizedText: '目录 1' }],
      },
    ])

    const html = renderReader(document)
    expect(html).not.toContain('data-sentence-id')
    expect(html).toContain('Table of contents')
  })

  it('falls back to plain paragraph text when segmentation fails', () => {
    const displayText = '第一句。第二句。'
    const document = buildDocument([
      {
        blockId: composeDocumentBlockId('doc_test', 'C0004'),
        sourceBlockId: 'C0004',
        kind: 'paragraph',
        docOrderIndex: 1,
        headingPath: ['Scope'],
        displayText,
        sentences: [
          { sentenceId: 'C0004:S001', rawText: '第一句。', normalizedText: '第一句。' },
          { sentenceId: 'C0004:S002', rawText: 'missing', normalizedText: 'missing' },
        ],
      },
    ])

    const html = renderReader(document)
    expect(html).not.toContain('data-sentence-id')
    expect(paragraphTextContentFromReaderHtml(html, composeDocumentBlockId('doc_test', 'C0004'))).toBe(
      displayText,
    )
  })
})
