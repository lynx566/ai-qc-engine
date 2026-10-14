import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

import { describe, expect, it } from 'vitest'

import { SourceCommentPopover } from '@/components/review/source-comment-popover'

describe('SourceCommentPopover', () => {
  it('starts empty in create mode', () => {
    const html = renderToStaticMarkup(
      createElement(SourceCommentPopover, {
        mode: 'create',
        top: 10,
        left: 20,
        onCancel: () => {},
        onSave: () => {},
      }),
    )

    expect(html).toContain('批注')
    expect(html).toContain('保存')
    expect(html).not.toContain('删除批注')
    expect(html).toContain('disabled=""')
  })

  it('loads existing content in edit mode', () => {
    const html = renderToStaticMarkup(
      createElement(SourceCommentPopover, {
        mode: 'edit',
        top: 10,
        left: 20,
        initialContent: 'existing content',
        onCancel: () => {},
        onSave: () => {},
        onDelete: () => {},
      }),
    )

    expect(html).toContain('existing content')
    expect(html).toContain('保存')
    expect(html).toContain('删除')
    expect(html).not.toContain('保存修改')
    expect(html).not.toContain('删除批注')
    expect(html).toContain('text-xs text-muted-foreground')
    expect(html).toContain('text-destructive')
    expect(html).toContain('data-variant="outline"')
    expect(html).not.toContain('justify-between')
  })
})
