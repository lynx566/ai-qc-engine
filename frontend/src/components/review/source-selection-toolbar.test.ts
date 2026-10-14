import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

import { describe, expect, it } from 'vitest'

import { SourceSelectionToolbar } from '@/components/review/source-selection-toolbar'

describe('SourceSelectionToolbar', () => {
  it('renders revision before comment in left-to-right order', () => {
    const html = renderToStaticMarkup(
      createElement(SourceSelectionToolbar, {
        top: 10,
        left: 20,
        onEdit: () => {},
        onComment: () => {},
      }),
    )

    expect(html.indexOf('修订')).toBeLessThan(html.indexOf('批注'))
    expect(html).toContain('修订')
    expect(html).toContain('批注')
    expect(html).not.toContain('标记')
    expect(html).not.toContain('高亮')
    expect(html).not.toContain('修改')
    expect(html).not.toContain('修订建议')
  })
})
