import { describe, expect, it } from 'vitest'

import {
  getQcFlowPresentation,
  getTaskDocumentTypeLabel,
  getSlotUploadLabel,
  getTaskTabLabel,
  getTaskTabTooltip,
  LAUNCHER_PRODUCT_TITLE,
  QC_FUNCTION_LABEL,
  sortCatalogByTaskOrder,
} from '@/lib/launcher-presentation'
import type { TaskCatalogEntry } from '@/types/document-consistency-qc'

function makeEntry(taskId: string): TaskCatalogEntry {
  return {
    taskId,
    displayName: taskId,
    description: 'backend description',
    slots: [{ slotId: 'source', expectedDocumentType: null, uploadLabel: 'backend', helpText: '' }],
  }
}

describe('launcher presentation copy', () => {
  it('uses the product title', () => {
    expect(LAUNCHER_PRODUCT_TITLE).toBe('临床研发文档智能质控系统')
  })

  it('exposes qc function label for the configuration page', () => {
    const presentation = getQcFlowPresentation('document_consistency_qc')

    expect(presentation.displayName).toBe('Writing Accuracy & Consistency')
    expect(presentation.localizedName).toBe('撰写准确性与一致性核查')
    expect(QC_FUNCTION_LABEL).toBe(presentation.localizedName)
  })

  it('orders catalog entries for launcher task tabs', () => {
    const ordered = sortCatalogByTaskOrder([
      makeEntry('dsur_updated_ib_qc'),
      makeEntry('internal_ib_qc'),
      makeEntry('internal_csr_qc'),
      makeEntry('internal_dsur_qc'),
    ])

    expect(ordered.map((entry) => entry.taskId)).toEqual([
      'internal_dsur_qc',
      'internal_csr_qc',
      'internal_ib_qc',
      'dsur_updated_ib_qc',
    ])
  })

  it('maps known task ids to confirmed product tab and document type labels', () => {
    const cases = [
      ['internal_dsur_qc', '研发期间安全性更新报告（DSUR）', 'DSUR'],
      ['internal_csr_qc', '临床研究报告（CSR）', 'CSR'],
      ['internal_ib_qc', '研究者手册（IB）', 'IB'],
      ['dsur_updated_ib_qc', 'DSUR↔IB', 'DSUR ↔ IB'],
    ]
    for (const [taskId, tabLabel, documentType] of cases) {
      expect(getTaskTabLabel(taskId, 'catalog')).toBe(tabLabel)
      expect(getTaskDocumentTypeLabel(taskId, 'catalog')).toBe(documentType)
    }
    expect(getTaskTabLabel('unknown_task', 'Fallback Name')).toBe('Fallback Name')
  })

  it('maps all installed QC task upload labels to the shared click-or-drag pattern', () => {
    const cases: Array<[string, string, string]> = [
      ['internal_dsur_qc', 'source', '点击或拖拽上传DSUR'],
      ['internal_csr_qc', 'source', '点击或拖拽上传CSR'],
      ['internal_ib_qc', 'source', '点击或拖拽上传IB'],
      ['dsur_updated_ib_qc', 'source_a', '点击或拖拽上传DSUR'],
      ['dsur_updated_ib_qc', 'source_b', '点击或拖拽上传IB'],
    ]

    for (const [taskId, slotId, expected] of cases) {
      expect(getSlotUploadLabel(taskId, slotId, 'catalog')).toBe(expected)
    }
  })

  it('shows a tab tooltip only for DSUR↔IB', () => {
    expect(getTaskTabTooltip('internal_dsur_qc')).toBeNull()
    expect(getTaskTabTooltip('internal_csr_qc')).toBeNull()
    expect(getTaskTabTooltip('internal_ib_qc')).toBeNull()
    expect(getTaskTabTooltip('dsur_updated_ib_qc')).toBe(
      '文件间质控，适用于IB参考DSUR进行更新的情况',
    )
  })
})
