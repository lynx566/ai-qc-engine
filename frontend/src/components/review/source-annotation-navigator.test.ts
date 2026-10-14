// @vitest-environment happy-dom

import { act, createElement, type ComponentProps } from 'react'
import { createRoot } from 'react-dom/client'
import { renderToStaticMarkup } from 'react-dom/server'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import {
  SOURCE_ANNOTATION_HELP_USAGE_LEAD,
  SOURCE_ANNOTATION_HELP_USAGE_SENTENCE,
  SOURCE_ANNOTATION_HELP_USAGE_TAIL,
  SOURCE_ANNOTATION_HELP_PERSISTENCE_NOTE,
  SourceAnnotationContext,
  SourceAnnotationNavigator,
} from '@/components/review/source-annotation-navigator'

const navigatorSource = readFileSync(
  resolve(import.meta.dirname, 'source-annotation-navigator.tsx'),
  'utf8',
)

function renderNavigator(
  props: Partial<ComponentProps<typeof SourceAnnotationNavigator>> = {},
) {
  return renderToStaticMarkup(
    createElement(SourceAnnotationNavigator, {
      revisionTotal: 5,
      revisionActiveIndex: null,
      commentTotal: 13,
      commentActiveIndex: null,
      onRevisionPrevious: () => {},
      onRevisionNext: () => {},
      onCommentPrevious: () => {},
      onCommentNext: () => {},
      ...props,
    }),
  )
}

describe('SourceAnnotationContext compact toolbar group', () => {
  it('groups revision, comment, and help in a lightweight status container', () => {
    const html = renderToStaticMarkup(
      createElement(SourceAnnotationContext, { revisionTotal: 2, commentTotal: 5 }),
    )

    expect(html).toContain('data-source-annotation-context="true"')
    expect(html).toContain('data-source-annotation-context-separator="true"')
    expect(html).toContain('修订 2')
    expect(html).toContain('批注 5')
    expect(html).toContain('data-source-annotation-help="true"')
    expect(navigatorSource).toContain('resultReviewContainerBorderClassName')
    expect(navigatorSource).toContain('bg-muted/30')
    expect(navigatorSource).toMatch(
      /data-source-annotation-context="true"[\s\S]*text-foreground/,
    )
    expect(navigatorSource).toContain('data-source-annotation-comment-with-help="true"')
    expect(navigatorSource).toMatch(
      /data-source-annotation-comment-with-help="true"[\s\S]*<SourceAnnotationInfoTrigger/,
    )
    expect(navigatorSource).toContain('data-source-annotation-help="true"')
    expect(navigatorSource).toContain('variant="ghost"')
    expect(navigatorSource).toContain('size="icon-xs"')
  })
})

describe('SourceAnnotationNavigator controls', () => {
  it('disables only empty groups and preserves the shared border, divider and icons', () => {
    const host = document.createElement('div')
    host.innerHTML = renderNavigator({ revisionTotal: 0, commentTotal: 2 })
    expect(host.querySelector('[data-source-annotation-label="revision"]')?.textContent).toBe('修订 0')
    expect(host.querySelector('[data-source-annotation-label="comment"]')?.textContent).toBe('批注 2')
    for (const kind of ['revision', 'comment']) {
      const segment = host.querySelector(`[data-source-annotation-nav="${kind}"]`)!
      expect(segment.className).toContain('border')
      expect(segment.className).toContain('flex-col')
      expect(segment.children).toHaveLength(3)
      const [previous, divider, next] = [...segment.children]
      expect(divider.getAttribute('aria-hidden')).toBe('true')
      expect(divider.className).toContain('h-px')
      for (const button of [previous, next]) {
        expect(button.tagName).toBe('BUTTON')
        expect((button as HTMLButtonElement).disabled).toBe(kind === 'revision')
        expect(button.getAttribute('aria-label')).toBeTruthy()
      }
      expect(previous.querySelector('.lucide-chevron-up')).not.toBeNull()
      expect(next.querySelector('.lucide-chevron-down')).not.toBeNull()
    }
  })

  it('dispatches previous and repeated next clicks independently for each kind', () => {
    const host = document.createElement('div')
    const root = createRoot(host)
    const calls: string[] = []
    try {
      act(() => root.render(createElement(SourceAnnotationNavigator, {
        revisionTotal: 2, revisionActiveIndex: null,
        commentTotal: 3, commentActiveIndex: null,
        onRevisionPrevious: () => calls.push('revision:previous'),
        onRevisionNext: () => calls.push('revision:next'),
        onCommentPrevious: () => calls.push('comment:previous'),
        onCommentNext: () => calls.push('comment:next'),
      })))
      for (const kind of ['revision', 'comment']) {
        act(() => host.querySelector<HTMLButtonElement>(`[data-source-annotation-nav-previous="${kind}"]`)!.click())
        act(() => host.querySelector<HTMLButtonElement>(`[data-source-annotation-nav-next="${kind}"]`)!.click())
        act(() => host.querySelector<HTMLButtonElement>(`[data-source-annotation-nav-next="${kind}"]`)!.click())
      }
      expect(calls).toEqual(['revision:previous', 'revision:next', 'revision:next', 'comment:previous', 'comment:next', 'comment:next'])
    } finally {
      act(() => root.unmount())
    }
  })
})

describe('SourceAnnotationNavigator compact layout', () => {
  it('stacks arrow controls vertically in a narrow column', () => {
    expect(navigatorSource).toContain('inline-flex w-5 shrink-0 flex-col overflow-hidden rounded-[3px] border')
    expect(navigatorSource).toContain('h-3 min-h-3 w-full min-w-0')
    expect(navigatorSource).toContain('[&_svg]:size-3')
    expect(navigatorSource).not.toContain('ChevronLeft')
    expect(navigatorSource).not.toContain('ChevronRight')
  })

  it('keeps annotation groups on one toolbar row with segmented spacing', () => {
    expect(navigatorSource).toContain('data-source-annotation-navigator="true"')
    expect(navigatorSource).toContain('flex flex-wrap items-center gap-2')
    expect(navigatorSource).toContain('data-source-annotation-group-controls={kind}')
    expect(navigatorSource).toContain('data-source-annotation-label={kind}')
    expect(navigatorSource).toContain('data-source-annotation-nav={kind}')
    expect(navigatorSource).toContain('resultReviewContainerBorderClassName')
    expect(navigatorSource).toContain('resultReviewInternalSeparatorSurfaceClassName')
    expect(navigatorSource).toContain('className="inline-flex items-center gap-1.5 text-sm text-foreground"')
    expect(navigatorSource).toContain(
      'className="shrink-0 tabular-nums whitespace-nowrap text-[13px] text-foreground"',
    )
    expect(navigatorSource).toContain('text-foreground [&_svg]:size-3')
  })

  it('does not render legacy navigation labels', () => {
    const html = renderNavigator()

    expect(html).not.toContain('aria-label="上一个修订"')
    expect(html).not.toContain('aria-label="下一个修订"')
    expect(html).not.toContain('aria-label="上一个批注"')
    expect(html).not.toContain('aria-label="下一个批注"')
    expect(html).not.toContain('查看原文标注说明')
  })

  it('does not render annotation help in the Full Document navigator', () => {
    const html = renderNavigator()
    const navigatorComponentSource =
      navigatorSource.match(/export function SourceAnnotationNavigator[\s\S]*/)?.[0] ?? ''

    expect(navigatorComponentSource).not.toContain('SourceAnnotationInfoTrigger')
    expect(html).not.toContain('data-source-annotation-help="true"')
    expect(html).not.toContain('aria-label="原文标注说明"')
  })
})

describe('SourceAnnotationNavigator invariants', () => {
  it('exposes only the four navigation buttons without management menus', () => {
    const html = renderNavigator()
    expect(html.match(/<button\b/g)).toHaveLength(4)
    expect(html).not.toContain('aria-haspopup="menu"')
    expect(html).not.toContain('data-source-annotation-menu-trigger')
  })

  it('shows split revision and comment counts without mixed 标注 navigator', () => {
    const html = renderNavigator({
      revisionTotal: 3,
      commentTotal: 5,
    })

    expect(html).toContain('data-source-annotation-navigator="true"')
    expect(html).toContain('data-source-annotation-group="revision"')
    expect(html).toContain('data-source-annotation-group="comment"')
    expect(html).toContain('修订 3')
    expect(html).toContain('批注 5')
    expect(html).not.toContain('标注 8')
    expect(html).not.toContain('>标注<')
  })

  it('shows active position only in matching group label', () => {
    const html = renderNavigator({
      revisionTotal: 12,
      revisionActiveIndex: 2,
      commentTotal: 23,
      commentActiveIndex: null,
    })

    expect(html).toContain('修订 3/12')
    expect(html).toContain('批注 23')
    expect(html).not.toContain('批注 3/23')
  })

  it('shows the active comment position without changing the revision count', () => {
    const html = renderNavigator({
      revisionTotal: 5,
      revisionActiveIndex: null,
      commentTotal: 13,
      commentActiveIndex: 1,
    })
    expect(html).toContain('修订 5')
    expect(html).toContain('批注 2/13')
  })

  it('sizes the help tooltip to its copy instead of the default max-w-56 shell', () => {
    expect(navigatorSource).toContain('data-source-annotation-help-content="true"')
    expect(navigatorSource).toContain('max-w-none w-max')
    expect(navigatorSource).toContain('sourceAnnotationHelpSentenceClassName')
    expect(navigatorSource).toContain('max-w-[16em]')
    expect(navigatorSource).toContain('space-y-1.5')
  })

  it('defines shared help tooltip copy for revisions and comments', () => {
    const tooltipCopy = [
      SOURCE_ANNOTATION_HELP_USAGE_SENTENCE,
      SOURCE_ANNOTATION_HELP_PERSISTENCE_NOTE,
    ].join('\n')

    expect(navigatorSource).not.toContain('SOURCE_ANNOTATION_HELP_TITLE')
    expect(tooltipCopy).toContain(SOURCE_ANNOTATION_HELP_USAGE_SENTENCE)
    expect(tooltipCopy).toContain('目前仅支持单句内选中。')
    expect(tooltipCopy).toContain(SOURCE_ANNOTATION_HELP_PERSISTENCE_NOTE)
    expect(navigatorSource).toContain('SOURCE_ANNOTATION_HELP_USAGE_LEAD')
    expect(navigatorSource).toContain('SOURCE_ANNOTATION_HELP_USAGE_TAIL')
    expect(navigatorSource).toContain('className="block"')
    expect(navigatorSource).toContain('font-semibold')
    expect(navigatorSource).toContain('SOURCE_ANNOTATION_HELP_PERSISTENCE_NOTE')
    expect(tooltipCopy).not.toContain('标注 35')
  })
})
