import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

import { describe, expect, it } from 'vitest'

import {
  SourceCommentMarker,
  resolveSourceCommentMarkerClassName,
  sourceCommentActiveBadgeClassName,
  sourceCommentBadgeClassName,
} from '@/components/review/source-comment-marker'

describe('SourceCommentMarker', () => {
  it('renders non-active comment as blue icon only', () => {
    const html = renderToStaticMarkup(
      createElement(SourceCommentMarker, {
        annotationId: 'ann_comment',
      }),
    )

    expect(html).toContain(sourceCommentBadgeClassName)
    expect(html).not.toContain(sourceCommentActiveBadgeClassName)
    expect(html).not.toContain('bg-blue-100')
  })

  it('adds compact light-blue background when active', () => {
    const html = renderToStaticMarkup(
      createElement(SourceCommentMarker, {
        annotationId: 'ann_comment',
        isActive: true,
      }),
    )

    expect(html).toContain('text-blue-600')
    expect(html).toContain('bg-blue-100')
    expect(html).toContain('rounded-sm')
    expect(html).not.toContain('border')
  })

  it('resolves class names from active state', () => {
    expect(resolveSourceCommentMarkerClassName(false)).toBe(sourceCommentBadgeClassName)
    expect(resolveSourceCommentMarkerClassName(true)).toContain(sourceCommentActiveBadgeClassName)
  })
})
