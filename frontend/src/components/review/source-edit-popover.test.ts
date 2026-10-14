import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

import { describe, expect, it } from 'vitest'

import { SourceEditPopover } from '@/components/review/source-edit-popover'

describe('SourceEditPopover', () => {
  it('renders create revision popover copy and actions', () => {
    const html = renderToStaticMarkup(
      createElement(SourceEditPopover, {
        mode: 'create',
        top: 10,
        left: 20,
        onCancel: () => {},
        onSave: () => {},
      }),
    )

    expect(html).toContain('修订为')
    expect(html).not.toContain('>修订</p>')
    expect(html).toContain('取消')
    expect(html).toContain('保存')
    expect(html).not.toContain('修改建议')
  })

  it('disables save when replacement draft is empty', () => {
    const html = renderToStaticMarkup(
      createElement(SourceEditPopover, {
        mode: 'create',
        top: 10,
        left: 20,
        initialReplacementText: '   ',
        onCancel: () => {},
        onSave: () => {},
      }),
    )

    expect(html).toContain('disabled=""')
  })

  it('renders edit actions for persisted revision', () => {
    const html = renderToStaticMarkup(
      createElement(SourceEditPopover, {
        mode: 'edit',
        top: 10,
        left: 20,
        initialReplacementText: '80.0%',
        onCancel: () => {},
        onSave: () => {},
        onDelete: () => {},
      }),
    )

    expect(html).toContain('保存')
    expect(html).toContain('删除')
    expect(html).not.toContain('保存修订')
    expect(html).not.toContain('删除修订')
    expect(html).toContain('text-destructive')
    expect(html).toContain('data-variant="outline"')
    expect(html).not.toContain('justify-between')
  })
})
