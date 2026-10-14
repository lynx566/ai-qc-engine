import { describe, expect, it } from 'vitest'

import { adaptCandidateScopeState, buildCandidateChapterSections, buildSidebarEntries } from '@/adapters/candidate-scope-view'
import { DocumentConsistencyQcApiError } from '@/api/document-consistency-qc-error'
import type { CandidateScopeContentDomainGroup, CandidateScopeSlotState } from '@/types/candidate-scope'

const internalDsurContentDomainGroups: CandidateScopeContentDomainGroup[] = [
  {
    contentDomainId: 'clinical_safety',
    displayLabel: '临床安全性',
    filterJobIds: ['dsur_clinical_safety', 'dsur_overview'],
  },
]

const slotState: CandidateScopeSlotState = {
  slotId: 'source',
  docId: 'doc_test',
  automaticAnchorBlockIds: ['C0010', 'C0030', 'C0033', 'C0040', 'C0044'],
  currentAnchorBlockIds: ['C0010', 'C0030', 'C0033', 'C0040', 'C0044'],
  headings: [
    {
      docId: 'doc_test',
      filterJobId: 'dsur_overview',
      anchorBlockId: 'C0010',
      title: '1. 执行概要',
      headingPath: ['1. 执行概要'],
      level: 1,
      docOrderIndex: 10,
    },
    {
      docId: 'doc_test',
      filterJobId: 'dsur_clinical_safety',
      anchorBlockId: 'C0030',
      title: '4.1 总体不良事件概览',
      headingPath: ['4. 临床安全性', '4.1 总体不良事件概览'],
      level: 2,
      docOrderIndex: 80,
    },
    {
      docId: 'doc_test',
      filterJobId: 'dsur_clinical_safety',
      anchorBlockId: 'C0033',
      title: '4.2 严重不良事件与重要风险',
      headingPath: ['4. 临床安全性', '4.2 严重不良事件与重要风险'],
      level: 2,
      docOrderIndex: 90,
    },
    {
      docId: 'doc_test',
      filterJobId: 'dsur_clinical_safety',
      anchorBlockId: 'C0040',
      title: '4.3.1 安全性参考信息的一致性',
      headingPath: [
        '4. 临床安全性',
        '4.3 其他安全性观察',
        '4.3.1 安全性参考信息的一致性',
      ],
      level: 3,
      docOrderIndex: 110,
    },
    {
      docId: 'doc_test',
      filterJobId: 'dsur_overview',
      anchorBlockId: 'C0044',
      title: '6. 结论',
      headingPath: ['6. 结论'],
      level: 1,
      docOrderIndex: 130,
    },
  ],
}

describe('candidate scope sidebar view', () => {
  it('groups clinical safety children under parent title', () => {
    const selected = new Set(['C0010', 'C0030', 'C0033', 'C0040', 'C0044'])
    const entries = buildSidebarEntries(slotState, selected)

    const group = entries.find((entry) => entry.kind === 'group')
    expect(group?.kind).toBe('group')
    if (group?.kind === 'group') {
      expect(group.title).toBe('4. 临床安全性')
      expect(group.childCount).toBe(3)
    }

    const labels = entries.map((entry) =>
      entry.kind === 'leaf' ? entry.title : entry.title,
    )
    expect(labels).toContain('1. 执行概要')
    expect(labels).toContain('6. 结论')
    expect(labels).not.toContain('Selected for Clinical Safety')
    expect(labels).not.toContain('primary')
    expect(labels).not.toContain('supporting')
  })

  it('exposes grouped children when expanded', () => {
    const selected = new Set(['C0030', 'C0033', 'C0040'])
    const entries = buildSidebarEntries(slotState, selected)
    const group = entries.find((entry) => entry.kind === 'group')
    expect(group?.kind).toBe('group')
    if (group?.kind === 'group') {
      expect(group.children.map((child) => child.title)).toEqual([
        '4.1 总体不良事件概览',
        '4.2 严重不良事件与重要风险',
        '4.3.1 安全性参考信息的一致性',
      ])
    }
  })

  it('orders sidebar entries by docOrderIndex instead of title', () => {
    const state: CandidateScopeSlotState = {
      ...slotState,
      headings: [
        {
          docId: 'doc_test',
          filterJobId: 'dsur_overview',
          anchorBlockId: 'C0020',
          title: '2. 背景介绍',
          headingPath: ['2. 背景介绍'],
          level: 1,
          docOrderIndex: 20,
        },
        {
          docId: 'doc_test',
          filterJobId: 'dsur_overview',
          anchorBlockId: 'C0100',
          title: '10. 附录',
          headingPath: ['10. 附录'],
          level: 1,
          docOrderIndex: 10,
        },
      ],
    }

    const entries = buildSidebarEntries(state, new Set(['C0020', 'C0100']))
    expect(entries.map((entry) => entry.title)).toEqual(['10. 附录', '2. 背景介绍'])
  })

  it('orders top-level sidebar entries by docOrderIndex for showcase selection', () => {
    const selected = new Set(['C0010', 'C0030', 'C0033', 'C0040', 'C0044'])
    const entries = buildSidebarEntries(slotState, selected)

    expect(entries.map((entry) => entry.title)).toEqual([
      '1. 执行概要',
      '4. 临床安全性',
      '6. 结论',
    ])
  })

  it('merges overview and clinical-safety filter jobs into one content domain section', () => {
    const selected = new Set(['C0010', 'C0030', 'C0033', 'C0040', 'C0044'])
    const sections = buildCandidateChapterSections(
      slotState,
      selected,
      internalDsurContentDomainGroups,
    )

    expect(sections).toHaveLength(1)
    const section = sections[0]
    expect(section?.kind).toBe('domain')
    if (section?.kind !== 'domain') {
      return
    }
    expect(section.contentDomainId).toBe('clinical_safety')
    expect(section.domainLabel).toBe('临床安全性')
    expect(section.chapterCount).toBe(5)
    expect(section.headings.map((heading) => heading.title)).toEqual([
      '1. 执行概要',
      '4.1 总体不良事件概览',
      '4.2 严重不良事件与重要风险',
      '4.3.1 安全性参考信息的一致性',
      '6. 结论',
    ])
    expect(section.candidateAnchorBlockIds).toEqual([
      'C0010',
      'C0030',
      'C0033',
      'C0040',
      'C0044',
    ])
    expect(slotState.headings.find((heading) => heading.anchorBlockId === 'C0010')?.filterJobId).toBe(
      'dsur_overview',
    )
  })

  it('includes the full domain catalog even when only a subset is selected', () => {
    const selected = new Set(['C0010', 'C0044'])
    const sections = buildCandidateChapterSections(
      slotState,
      selected,
      internalDsurContentDomainGroups,
    )

    const section = sections[0]
    expect(section?.chapterCount).toBe(2)
    expect(section?.headings).toHaveLength(5)
    expect(section?.candidateAnchorBlockIds).toEqual(['C0010', 'C0044'])
  })

  it('throws when selected heading filter job is not covered by content domain groups', () => {
    expect(() =>
      buildCandidateChapterSections(
        slotState,
        new Set(['C0010']),
        [
          {
            contentDomainId: 'clinical_safety',
            displayLabel: '临床安全性',
            filterJobIds: ['dsur_clinical_safety'],
          },
        ],
      ),
    ).toThrow(DocumentConsistencyQcApiError)
  })
})

describe('candidate scope state adapter', () => {
  it('preserves independent slot diagnostics and accepts absent or null diagnostics', () => {
    const state = adaptCandidateScopeState({
      flow_id: 'document_consistency_qc', flow_run_id: 'flow_run_test',
      capability_id: 'dsur_updated_ib', capability_title: 'DSUR × IB',
      flow_status: 'paused_at_candidate_scope', can_resume: true,
      content_domain_groups: [],
      slots: [
        { slot_id: 'source_a', doc_id: 'doc_a', automatic_anchor_block_ids: [],
          current_anchor_block_ids: [], headings: [],
          document_type_diagnostic: { status: 'mismatch', expected_document_type: 'DSUR', reason: 'observed_differs_from_expected' } },
        { slot_id: 'source_b', doc_id: 'doc_b', automatic_anchor_block_ids: [],
          current_anchor_block_ids: [], headings: [],
          document_type_diagnostic: { status: 'match', expected_document_type: 'IB' } },
        { slot_id: 'old', doc_id: 'old', automatic_anchor_block_ids: [],
          current_anchor_block_ids: [], headings: [] },
        { slot_id: 'unavailable', doc_id: 'unavailable', automatic_anchor_block_ids: [],
          current_anchor_block_ids: [], headings: [], document_type_diagnostic: null },
      ],
    })
    expect(state.slots[0]?.documentTypeDiagnostic).toEqual({
      status: 'mismatch', expectedDocumentType: 'DSUR', reason: 'observed_differs_from_expected',
    })
    expect(state.slots[1]?.documentTypeDiagnostic).toMatchObject({ status: 'match', expectedDocumentType: 'IB' })
    expect(state.slots[2]?.documentTypeDiagnostic).toBeUndefined()
    expect(state.slots[3]?.documentTypeDiagnostic).toBeUndefined()
  })

  it('preserves uncertain status and its slot expected type', () => {
    const state = adaptCandidateScopeState({
      flow_id: 'document_consistency_qc', flow_run_id: 'flow_run_test',
      capability_id: 'internal_csr', capability_title: 'CSR',
      flow_status: 'paused_at_candidate_scope', can_resume: true, content_domain_groups: [],
      slots: [{ slot_id: 'source', doc_id: 'doc', automatic_anchor_block_ids: [],
        current_anchor_block_ids: [], headings: [], document_type_diagnostic: {
          status: 'uncertain', expected_document_type: 'CSR', reason: 'doc_type_conflict',
        } }],
    })
    expect(state.slots[0]?.documentTypeDiagnostic).toEqual({
      status: 'uncertain', expectedDocumentType: 'CSR', reason: 'doc_type_conflict',
    })
  })

  it('maps flow-level slots[] response', () => {
    const state = adaptCandidateScopeState({
      flow_id: 'document_consistency_qc',
      flow_run_id: 'flow_run_test',
      capability_id: 'internal_dsur',
      capability_title: '试验药临床安全性核查',
      flow_status: 'paused_at_candidate_scope',
      can_resume: true,
      content_domain_groups: [
        {
          content_domain_id: 'clinical_safety',
          display_label: '临床安全性',
          filter_job_ids: ['dsur_clinical_safety', 'dsur_overview'],
        },
      ],
      slots: [
        {
          slot_id: 'source',
          doc_id: 'doc_test',
          automatic_anchor_block_ids: ['C0010'],
          current_anchor_block_ids: ['C0010'],
          headings: [
            {
              doc_id: 'doc_test',
              filter_job_id: 'dsur_overview',
              anchor_block_id: 'C0010',
              title: '1. 执行概要',
              heading_path: ['1. 执行概要'],
              level: 1,
              doc_order_index: 42,
            },
          ],
        },
      ],
    })

    expect(state.flowId).toBe('document_consistency_qc')
    expect(state.flowRunId).toBe('flow_run_test')
    expect(state.slots).toHaveLength(1)
    expect(state.slots[0]?.slotId).toBe('source')
    expect(state.slots[0]?.headings[0]?.docOrderIndex).toBe(42)
    expect(state.canResume).toBe(true)
    expect(state.contentDomainGroups[0]?.contentDomainId).toBe('clinical_safety')
  })

  it('fails when doc_order_index is missing or invalid', () => {
    expect(() =>
      adaptCandidateScopeState({
        flow_id: 'document_consistency_qc',
        flow_run_id: 'flow_run_test',
        capability_id: 'internal_dsur',
        capability_title: '试验药临床安全性核查',
        flow_status: 'paused_at_candidate_scope',
        can_resume: true,
        slots: [
          {
            slot_id: 'source',
            doc_id: 'doc_test',
            automatic_anchor_block_ids: [],
            current_anchor_block_ids: [],
            headings: [
              {
                doc_id: 'doc_test',
                filter_job_id: 'dsur_overview',
                anchor_block_id: 'C0010',
                title: '1. 执行概要',
                heading_path: ['1. 执行概要'],
                level: 1,
                doc_order_index: -1,
              },
            ],
          },
        ],
      }),
    ).toThrow(DocumentConsistencyQcApiError)
  })
})
