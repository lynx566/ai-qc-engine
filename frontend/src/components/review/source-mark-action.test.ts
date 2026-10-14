import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

import { describe, expect, it } from 'vitest'

import { SourceMarkAction } from '@/components/review/source-mark-action'

describe('SourceMarkAction', () => {
  it('renders cancel mark label for persisted mark actions', () => {
    const html = renderToStaticMarkup(
      createElement(SourceMarkAction, {
        label: '取消标记',
        top: 10,
        left: 20,
        onClick: () => {},
      }),
    )

    expect(html).toContain('取消标记')
    expect(html).not.toContain('取消高亮')
    expect(html).not.toContain('高亮')
  })
})
