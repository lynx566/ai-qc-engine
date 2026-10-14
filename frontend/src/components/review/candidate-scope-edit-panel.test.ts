import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import { CandidateScopeEditPanel } from '@/components/review/candidate-scope-edit-panel'

import { canonicalizeDraftSelection } from '@/lib/candidate-scope-selection'
import {
  buildCandidateHeadingTree,
  flattenCandidateHeadingTree,
} from '@/lib/candidate-scope-heading-tree'
import type { CandidateHeading } from '@/types/candidate-scope'

function heading(
  anchorBlockId: string,
  title: string,
  level: number,
  headingPath: string[],
  docOrderIndex: number,
): CandidateHeading {
  return {
    docId: 'doc_test',
    filterJobId: 'dsur_clinical_safety',
    anchorBlockId,
    title,
    headingPath,
    level,
    docOrderIndex,
  }
}

describe('candidate scope edit panel hierarchy', () => {
  it('renders parent headings before their children in source order', () => {
    const source = readFileSync(
      resolve(import.meta.dirname, 'candidate-scope-edit-panel.tsx'),
      'utf8',
    )

    expect(source).toContain('flattenCandidateHeadingTree')
    expect(source).toContain('onToggle(heading')
    expect(source).not.toContain('buildHeadingTree')
  })

  it('keeps checkbox toggle bound to the original CandidateHeading', () => {
    const headings = [
      heading('C0020', '2. 报告范围与方法', 1, ['2. 报告范围与方法'], 20),
      heading('C0021', '2.1 报告周期与数据截止', 2, [
        '2. 报告范围与方法',
        '2.1 报告周期与数据截止',
      ], 30),
    ]
    const order = flattenCandidateHeadingTree(buildCandidateHeadingTree(headings)).map(
      ({ node }) => node.heading.anchorBlockId,
    )

    expect(order).toEqual(['C0020', 'C0021'])
  })

  it('uses the full sidebar scroll region instead of a capped strip height', () => {
    const html = renderToStaticMarkup(
      createElement(CandidateScopeEditPanel, {
        headings: [
          heading('C0010', '1. 执行概要', 1, ['1. 执行概要'], 10),
          heading('C0020', '2. 报告范围与方法', 1, ['2. 报告范围与方法'], 20),
        ],
        draftSelected: new Set(['C0010']),
        onToggle: () => {},
      }),
    )

    expect(html).toContain('min-h-0 flex-1')
    expect(html).not.toContain('max-h-56')
  })

  it('preserves inherited selection semantics after tree rendering', () => {
    const headings = [
      heading('C0043', '4.3 其他安全性观察', 2, ['4. 临床安全性', '4.3 其他安全性观察'], 100),
      heading('C0044', '4.3.1 安全性参考信息的一致性', 3, [
        '4. 临床安全性',
        '4.3 其他安全性观察',
        '4.3.1 安全性参考信息的一致性',
      ], 110),
    ]
    const headingsByAnchor = new Map(headings.map((item) => [item.anchorBlockId, item]))
    const canonical = canonicalizeDraftSelection(new Set(['C0043', 'C0044']), headingsByAnchor)

    expect([...canonical]).toEqual(['C0043'])
  })
})
