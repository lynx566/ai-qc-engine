import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

import { describe, expect, it } from 'vitest'

import {
  FINDING_VERDICT_TITLE_HANG_INDENT_PX,
  FindingVerdictIcon,
  FindingVerdictLegendContent,
  FindingVerdictTitle,
  findingVerdictAccessibleLabel,
} from '@/lib/finding-verdict-presentation'

describe('finding verdict presentation', () => {
  it('uses distinct outline icons for fail and need_review', () => {
    const failHtml = renderToStaticMarkup(
      createElement(FindingVerdictIcon, { label: 'fail' }),
    )
    const reviewHtml = renderToStaticMarkup(
      createElement(FindingVerdictIcon, { label: 'need_review' }),
    )

    expect(failHtml).toContain('data-finding-verdict="fail"')
    expect(failHtml).toContain('lucide-circle-x')
    expect(reviewHtml).toContain('data-finding-verdict="need_review"')
    expect(reviewHtml).toContain('lucide-triangle-alert')
    expect(failHtml).not.toContain('radial-gradient')
  })

  it('renders only fail and need_review legend rows', () => {
    const html = renderToStaticMarkup(createElement(FindingVerdictLegendContent))

    expect(html).toContain('发现错误')
    expect(html).toContain('可能有误')
    expect(html).toContain('data-finding-verdict="fail"')
    expect(html).toContain('data-finding-verdict="need_review"')
    expect(html).not.toContain('data-finding-verdict="pass"')
    expect(html).not.toContain('核查通过')
  })

  it('indents only the first title line for the verdict icon', () => {
    const html = renderToStaticMarkup(
      createElement(FindingVerdictTitle, { label: 'fail' }, '发现错误项'),
    )

    expect(html).toContain('data-finding-verdict-title="true"')
    expect(html).toContain(`text-indent:${FINDING_VERDICT_TITLE_HANG_INDENT_PX}px`)
    expect(html).toContain('width="14"')
    expect(html).toContain('top-[calc(0.5lh-7px)]')
    expect(html).toContain('data-finding-verdict="fail"')
    expect(html).not.toContain('flex items-start gap-1.5')
  })

  it('exposes accessible verdict labels', () => {
    expect(findingVerdictAccessibleLabel('fail')).toBe('发现错误')
    expect(findingVerdictAccessibleLabel('need_review')).toBe('可能有误')
  })
})
