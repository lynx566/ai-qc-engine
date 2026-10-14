import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import type { ExtractBlockDto, ExtractBundleDto } from '@/adapters/extract-bundle.dto'
import {
  ExtractDocumentAdapterError,
  adaptExtractBundleToDocumentView,
  assertCanonicalDocOrderIndexes,
  collectBodyBlocks,
  composeDocumentBlockId,
  mapExtractBlockToDocumentBlock,
  mapPresentation,
  resolveHeadingDisplayText,
  sortBodyBlocksByDocOrderIndex,
} from '@/adapters/extract-document'

function block(
  overrides: Partial<ExtractBlockDto> & Pick<ExtractBlockDto, 'block_id' | 'kind'>,
): ExtractBlockDto {
  return {
    raw_text: overrides.raw_text ?? 'text',
    normalized_text: overrides.normalized_text ?? overrides.raw_text ?? 'text',
    doc_order_index: overrides.doc_order_index ?? 0,
    heading_path: overrides.heading_path ?? [],
    ...overrides,
  }
}

describe('adaptExtractBundleToDocumentView', () => {
  it('merges front_matter, content, and table blocks by doc_order_index', () => {
    const bundle: ExtractBundleDto = {
      doc_id: 'doc_test',
      file_name: 'sample.docx',
      display_name: 'sample',
      front_matter_blocks: [
        block({
          block_id: 'M0001',
          kind: 'toc',
          raw_text: '目录',
          doc_order_index: 2,
          order: 99,
        }),
      ],
      content_blocks: [
        block({
          block_id: 'C0001',
          kind: 'paragraph',
          raw_text: 'cover',
          doc_order_index: 0,
          order: 1,
        }),
        block({
          block_id: 'C0002',
          kind: 'heading',
          raw_text: '执行概要',
          normalized_text: '1. 执行概要',
          heading_path: ['1. 执行概要'],
          doc_order_index: 3,
          order: 2,
          meta: { heading_level: 1 },
        }),
      ],
      table_blocks: [
        block({
          block_id: 'T0001',
          kind: 'table',
          raw_text: 'ignored',
          doc_order_index: 1,
          order: 50,
          meta: {
            raw_rows: [
              ['A', 'B'],
              ['1', '2'],
            ],
          },
        }),
      ],
    }

    const view = adaptExtractBundleToDocumentView(bundle)

    expect(view.blocks.map((item) => item.blockId)).toEqual([
      composeDocumentBlockId('doc_test', 'C0001'),
      composeDocumentBlockId('doc_test', 'T0001'),
      composeDocumentBlockId('doc_test', 'M0001'),
      composeDocumentBlockId('doc_test', 'C0002'),
    ])
  })

  it('does not sort body blocks by collection order field', () => {
    const bundle: ExtractBundleDto = {
      doc_id: 'doc_test',
      file_name: 'sample.docx',
      display_name: 'sample',
      content_blocks: [
        block({
          block_id: 'C0002',
          kind: 'paragraph',
          raw_text: 'second-by-order',
          doc_order_index: 0,
          order: 20,
        }),
        block({
          block_id: 'C0001',
          kind: 'paragraph',
          raw_text: 'first-by-order',
          doc_order_index: 1,
          order: 10,
        }),
      ],
    }

    const sorted = sortBodyBlocksByDocOrderIndex(collectBodyBlocks(bundle))

    expect(sorted.map((item) => item.block_id)).toEqual(['C0002', 'C0001'])
  })

  it('uses raw_text for paragraph displayText', () => {
    const mapped = mapExtractBlockToDocumentBlock(
      'doc_test',
      block({
        block_id: 'C0001',
        kind: 'paragraph',
        raw_text: 'line one\nline two',
        normalized_text: 'line one line two',
        doc_order_index: 0,
      }),
    )

    expect(mapped.displayText).toBe('line one\nline two')
  })

  it('keeps raw_text when only normalization differs from heading_path', () => {
    expect(
      resolveHeadingDisplayText(
        block({
          block_id: 'H0001',
          kind: 'heading',
          raw_text: '获益–风险',
          normalized_text: '获益-风险',
          heading_path: ['获益–风险'],
        }),
      ),
    ).toBe('获益–风险')
  })

  it('uses recovered automatic numbering from heading_path', () => {
    expect(
      resolveHeadingDisplayText(
        block({
          block_id: 'C0010',
          kind: 'heading',
          raw_text: '执行概要',
          normalized_text: '1. 执行概要',
          heading_path: ['1. 执行概要'],
        }),
      ),
    ).toBe('1. 执行概要')
  })

  it('uses raw_text when heading_path matches raw_text', () => {
    expect(
      resolveHeadingDisplayText(
        block({
          block_id: 'C0029',
          kind: 'heading',
          raw_text: '临床安全性',
          normalized_text: '临床安全性',
          heading_path: ['临床安全性'],
        }),
      ),
    ).toBe('临床安全性')
  })

  it('passes through validated presentation metadata', () => {
    const mapped = mapExtractBlockToDocumentBlock(
      'doc_test',
      block({
        block_id: 'C0001',
        kind: 'paragraph',
        raw_text: 'Cover',
        doc_order_index: 0,
        meta: {
          presentation: {
            alignment: 'center',
            font_size_pt: 24,
            bold: true,
            italic: false,
            indent_first_line_pt: 21,
            line_spacing_multiple: 1.45,
            space_before_pt: 36,
            space_after_pt: 6,
            toc_level: 2,
            unknown_field: 'ignored',
          },
        },
      }),
    )

    expect(mapped.presentation).toEqual({
      alignment: 'center',
      font_size_pt: 24,
      bold: true,
      italic: false,
      indent_first_line_pt: 21,
      line_spacing_multiple: 1.45,
      space_before_pt: 36,
      space_after_pt: 6,
      toc_level: 2,
    })
  })

  it('drops invalid presentation values during adapter validation', () => {
    expect(
      mapPresentation({
        alignment: 'middle',
        font_size_pt: Number.NaN,
        toc_level: 0,
      }),
    ).toBeUndefined()
  })

  it('leaves presentation undefined when extract meta omits it', () => {
    const mapped = mapExtractBlockToDocumentBlock(
      'doc_test',
      block({
        block_id: 'C0001',
        kind: 'paragraph',
        raw_text: 'plain',
        doc_order_index: 0,
      }),
    )

    expect(mapped.presentation).toBeUndefined()
  })

  it('maps tables from meta.raw_rows', () => {
    const mapped = mapExtractBlockToDocumentBlock(
      'doc_test',
      block({
        block_id: 'T0001',
        kind: 'table',
        raw_text: 'flattened text should not be used',
        normalized_text: 'flattened text should not be used',
        doc_order_index: 4,
        meta: {
          raw_rows: [
            ['列1', '列2'],
            ['a', 'b'],
          ],
        },
      }),
    )

    expect(mapped.table).toEqual({
      rows: [
        ['列1', '列2'],
        ['a', 'b'],
      ],
    })
    expect(mapped.displayText).toBeUndefined()
  })

  it('excludes format_blocks from DocumentView', () => {
    const bundle: ExtractBundleDto = {
      doc_id: 'doc_test',
      file_name: 'sample.docx',
      display_name: 'sample',
      content_blocks: [
        block({
          block_id: 'C0001',
          kind: 'paragraph',
          raw_text: 'body',
          doc_order_index: 0,
        }),
      ],
      format_blocks: [
        block({
          block_id: 'F0001',
          kind: 'header',
          raw_text: 'header text',
          doc_order_index: null,
        }),
      ],
    }

    const view = adaptExtractBundleToDocumentView(bundle)

    expect(view.blocks).toHaveLength(1)
    expect(view.blocks[0]?.blockId).toBe(
      composeDocumentBlockId('doc_test', 'C0001'),
    )
  })

  it('preserves sentence metadata without using it for displayText', () => {
    const mapped = mapExtractBlockToDocumentBlock(
      'doc_test',
      block({
        block_id: 'C0001',
        kind: 'paragraph',
        raw_text: 'full paragraph text',
        normalized_text: 'full paragraph text',
        doc_order_index: 0,
        sentences: [
          {
            sentence_id: 'C0001:S001',
            raw_text: 'sentence one',
            normalized_text: 'sentence one',
          },
          {
            sentence_id: 'C0001:S002',
            raw_text: 'sentence two',
            normalized_text: 'sentence two',
          },
        ],
      }),
    )

    expect(mapped.displayText).toBe('full paragraph text')
    expect(mapped.sentences).toEqual([
      {
        sentenceId: 'C0001:S001',
        rawText: 'sentence one',
        normalizedText: 'sentence one',
      },
      {
        sentenceId: 'C0001:S002',
        rawText: 'sentence two',
        normalizedText: 'sentence two',
      },
    ])
  })

  it('fails explicitly when doc_order_index is missing or duplicated', () => {
    expect(() =>
      assertCanonicalDocOrderIndexes([
        block({
          block_id: 'C0001',
          kind: 'paragraph',
          doc_order_index: null,
        }),
      ]),
    ).toThrow(ExtractDocumentAdapterError)

    expect(() =>
      assertCanonicalDocOrderIndexes([
        block({
          block_id: 'C0001',
          kind: 'paragraph',
          doc_order_index: 1,
        }),
        block({
          block_id: 'C0002',
          kind: 'paragraph',
          doc_order_index: 1,
        }),
      ]),
    ).toThrow(/Duplicate doc_order_index/)
  })

  it('fails when table blocks omit meta.raw_rows', () => {
    expect(() =>
      mapExtractBlockToDocumentBlock(
        'doc_test',
        block({
          block_id: 'T0001',
          kind: 'table',
          doc_order_index: 0,
        }),
      ),
    ).toThrow(/missing meta.raw_rows/)
  })
})

describe('canonical showcase fixture', () => {
  it('adapts the checked-in extract bundle snapshot', () => {
    const fixtureDir = dirname(fileURLToPath(import.meta.url))
    const bundlePath = join(
      fixtureDir,
      '../../fixtures/extract/canonical-showcase-bundle.json',
    )
    const bundle = JSON.parse(readFileSync(bundlePath, 'utf8')) as ExtractBundleDto
    const view = adaptExtractBundleToDocumentView(bundle)

    expect(view.docId).toBe('doc_edd6938b-94af-4099-bbcf-3fa025319923')
    expect(view.blocks.length).toBeGreaterThan(60)
    expect(view.blocks[0]?.kind).toBe('paragraph')
    expect(view.blocks.some((item) => item.kind === 'table')).toBe(true)
    expect(view.blocks.some((item) => item.kind === 'toc')).toBe(true)
    expect(
      view.blocks.find(
        (item) => item.blockId === composeDocumentBlockId(view.docId, 'C0006'),
      )?.displayText,
    ).toBe('执行概要')

    const coverBlock = view.blocks.find(
      (item) => item.blockId === composeDocumentBlockId(view.docId, 'C0001'),
    )
    expect(coverBlock?.presentation?.alignment).toBe('center')

    const tocEntry = view.blocks.find(
      (item) => item.kind === 'toc' && item.presentation?.toc_level !== undefined,
    )
    expect(tocEntry?.kind).toBe('toc')

    const bodyParagraph = view.blocks.find(
      (item) =>
        item.kind === 'paragraph' &&
        item.presentation?.indent_first_line_pt !== undefined,
    )
    expect(bodyParagraph?.presentation?.line_spacing_multiple).toBe(1.45)

    const tableBlock = view.blocks.find((item) => item.kind === 'table')
    expect(tableBlock?.table?.rows.length).toBeGreaterThan(0)
    expect(tableBlock?.presentation).toBeUndefined()
  })
})
