import { describe, expect, it } from 'vitest'

import {
  buildCandidateHeadingTree,
  compareCandidateHeadingDocumentOrder,
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

const flatHierarchyHeadings: CandidateHeading[] = [
  heading('C0010', '1. 执行概要', 1, ['1. 执行概要'], 10),
  heading('C0020', '2. 报告范围与方法', 1, ['2. 报告范围与方法'], 20),
  heading('C0021', '2.1 报告周期与数据截止', 2, ['2. 报告范围与方法', '2.1 报告周期与数据截止'], 30),
  heading('C0022', '2.2 数据来源与处理原则', 2, ['2. 报告范围与方法', '2.2 数据来源与处理原则'], 40),
  heading('C0030', '3. 研究进展与暴露', 1, ['3. 研究进展与暴露'], 50),
  heading('C0031', '3.1 累计受试者暴露', 2, ['3. 研究进展与暴露', '3.1 累计受试者暴露'], 60),
  heading('C0040', '4. 临床安全性', 1, ['4. 临床安全性'], 70),
  heading('C0041', '4.1 总体不良事件概览', 2, ['4. 临床安全性', '4.1 总体不良事件概览'], 80),
  heading('C0042', '4.2 严重不良事件与重要风险', 2, ['4. 临床安全性', '4.2 严重不良事件与重要风险'], 90),
  heading('C0043', '4.3 其他安全性观察', 2, ['4. 临床安全性', '4.3 其他安全性观察'], 100),
  heading('C0044', '4.3.1 安全性参考信息的一致性', 3, [
    '4. 临床安全性',
    '4.3 其他安全性观察',
    '4.3.1 安全性参考信息的一致性',
  ], 110),
  heading('C0050', '5. 疗效探索性结果', 1, ['5. 疗效探索性结果'], 120),
  heading('C0060', '6. 结论', 1, ['6. 结论'], 130),
  heading('C0070', '7. 附录：渲染检查点', 1, ['7. 附录：渲染检查点'], 140),
]

describe('buildCandidateHeadingTree', () => {
  it('orders by docOrderIndex even when anchorBlockId order conflicts', () => {
    const headings = [
      heading('C0900', 'A', 1, ['A'], 10),
      heading('C0002', 'B', 1, ['B'], 20),
      heading('C0500', 'C', 1, ['C'], 30),
      heading('C0001', 'D', 1, ['D'], 40),
    ]

    const tree = buildCandidateHeadingTree(headings)
    expect(tree.map((node) => node.heading.anchorBlockId)).toEqual([
      'C0900',
      'C0002',
      'C0500',
      'C0001',
    ])
  })

  it('nests children under the nearest ancestor in docOrderIndex order', () => {
    const shuffled = [
      flatHierarchyHeadings[6]!,
      flatHierarchyHeadings[0]!,
      flatHierarchyHeadings[3]!,
      flatHierarchyHeadings[1]!,
      flatHierarchyHeadings[9]!,
      flatHierarchyHeadings[8]!,
      flatHierarchyHeadings[7]!,
      flatHierarchyHeadings[10]!,
      flatHierarchyHeadings[2]!,
      flatHierarchyHeadings[4]!,
      flatHierarchyHeadings[5]!,
      flatHierarchyHeadings[11]!,
      flatHierarchyHeadings[12]!,
      flatHierarchyHeadings[13]!,
    ]

    const tree = buildCandidateHeadingTree(shuffled)
    expect(tree.map((node) => node.heading.anchorBlockId)).toEqual([
      'C0010',
      'C0020',
      'C0030',
      'C0040',
      'C0050',
      'C0060',
      'C0070',
    ])

    const section2 = tree.find((node) => node.heading.anchorBlockId === 'C0020')
    expect(section2?.children.map((node) => node.heading.anchorBlockId)).toEqual([
      'C0021',
      'C0022',
    ])

    const section4 = tree.find((node) => node.heading.anchorBlockId === 'C0040')
    expect(section4?.children.map((node) => node.heading.anchorBlockId)).toEqual([
      'C0041',
      'C0042',
      'C0043',
    ])
    expect(section4?.children[2]?.children.map((node) => node.heading.anchorBlockId)).toEqual([
      'C0044',
    ])
  })

  it('builds hierarchy when anchorBlockId order is scrambled', () => {
    const headings = [
      heading('C9999', 'D', 1, ['D'], 40),
      heading('C0001', 'B', 2, ['A', 'B'], 20),
      heading('C8888', 'C', 2, ['A', 'C'], 30),
      heading('C7777', 'A', 1, ['A'], 10),
    ]

    const tree = buildCandidateHeadingTree(headings)
    expect(flattenCandidateHeadingTree(tree).map(({ node }) => node.heading.anchorBlockId)).toEqual([
      'C7777',
      'C0001',
      'C8888',
      'C9999',
    ])
  })

  it('flattens in parent-before-child document order', () => {
    const tree = buildCandidateHeadingTree(flatHierarchyHeadings)
    const flattened = flattenCandidateHeadingTree(tree).map(
      ({ node }) => node.heading.anchorBlockId,
    )

    expect(flattened).toEqual([
      'C0010',
      'C0020',
      'C0021',
      'C0022',
      'C0030',
      'C0031',
      'C0040',
      'C0041',
      'C0042',
      'C0043',
      'C0044',
      'C0050',
      'C0060',
      'C0070',
    ])
  })

  it('uses docOrderIndex for compareCandidateHeadingDocumentOrder', () => {
    const left = heading('C9999', 'later anchor', 1, ['x'], 5)
    const right = heading('C0001', 'earlier anchor', 1, ['y'], 10)
    expect(compareCandidateHeadingDocumentOrder(left, right)).toBeLessThan(0)
  })
})
