import { describe, expect, it } from 'vitest'

import { buildStartTaskFormData } from '@/api/clinical-trial-doc-qc'
import {
  allRequiredSlotsHaveFiles,
  canStartLauncher,
  createEmptySlotFiles,
  hasUnappliedSlotDraft,
  resolveTaskRunDefaultRoutePath,
  taskQcSetupRoutePath,
  taskResultRoutePath,
  toSlotFileUploadMap,
} from '@/lib/launcher-state'
import type { TaskCatalogEntry } from '@/types/document-consistency-qc'
import {
  PAUSED_TASK_STATE,
  SUCCESS_NO_RESULT_TASK_STATE,
  SUCCESS_RESULT_TASK_STATE,
} from '@/test-fixtures/task-run-state'

const singleSlotTask: TaskCatalogEntry = {
  taskId: 'internal_dsur_qc',
  displayName: 'DSUR 核查',
  description: '单文档核查',
  slots: [
    {
      slotId: 'source',
      expectedDocumentType: 'dsur',
      uploadLabel: '上传 DSUR 文档',
      helpText: '请上传 DSUR 文件',
    },
  ],
}

const multiSlotTask: TaskCatalogEntry = {
  taskId: 'dsur_updated_ib_qc',
  displayName: 'DSUR 与更新 IB 一致性',
  description: '双文档核查',
  slots: [
    {
      slotId: 'source_a',
      expectedDocumentType: 'dsur',
      uploadLabel: '上传 DSUR 文档',
      helpText: 'DSUR',
    },
    {
      slotId: 'source_b',
      expectedDocumentType: 'ib',
      uploadLabel: '上传 IB 文档',
      helpText: 'IB',
    },
  ],
}

function makeFile(name: string): File {
  return new File(['content'], name, {
    type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  })
}

describe('launcher slot draft state', () => {
  it('creates one file input slot per catalog slot', () => {
    const single = createEmptySlotFiles(singleSlotTask)
    expect([...single.keys()]).toEqual(['source'])

    const multi = createEmptySlotFiles(multiSlotTask)
    expect([...multi.keys()]).toEqual(['source_a', 'source_b'])
  })

  it('requires all catalog slots before start', () => {
    const files = createEmptySlotFiles(multiSlotTask)
    files.set('source_a', makeFile('a.docx'))
    expect(allRequiredSlotsHaveFiles(multiSlotTask, files)).toBe(false)

    files.set('source_b', makeFile('b.docx'))
    expect(allRequiredSlotsHaveFiles(multiSlotTask, files)).toBe(true)
  })

  it('disables start while submitting', () => {
    const files = createEmptySlotFiles(singleSlotTask)
    files.set('source', makeFile('a.docx'))
    expect(canStartLauncher(singleSlotTask, files, 'idle')).toBe(true)
    expect(canStartLauncher(singleSlotTask, files, 'submitting')).toBe(false)
  })

  it('builds multipart form with task_id and all slot files', () => {
    const files = createEmptySlotFiles(multiSlotTask)
    files.set('source_a', makeFile('a.docx'))
    files.set('source_b', makeFile('b.docx'))

    const formData = buildStartTaskFormData(
      multiSlotTask.taskId,
      toSlotFileUploadMap(files),
    )

    expect(formData.get('task_id')).toBe('dsur_updated_ib_qc')
    expect(formData.get('source_a')).toBeInstanceOf(File)
    expect(formData.get('source_b')).toBeInstanceOf(File)
  })
})

describe('launcher routing helper', () => {
  it('builds task-owned qc setup and result routes from task_run_id', () => {
    expect(taskQcSetupRoutePath('task_run_123')).toBe('/task-runs/task_run_123/qc-setup')
    expect(taskResultRoutePath('task_run_123')).toBe('/task-runs/task_run_123/result')
  })
})

describe('task run default navigation', () => {
  it('routes paused tasks to qc setup', () => {
    expect(
      resolveTaskRunDefaultRoutePath('task_run_paused', PAUSED_TASK_STATE),
    ).toBe('/task-runs/task_run_paused/qc-setup')
  })

  it('routes completed tasks with result to the result page', () => {
    expect(
      resolveTaskRunDefaultRoutePath('task_run_done', SUCCESS_RESULT_TASK_STATE),
    ).toBe('/task-runs/task_run_done/result')
  })

  it('routes in-progress tasks without result back to qc setup', () => {
    expect(
      resolveTaskRunDefaultRoutePath('task_run_pending', SUCCESS_NO_RESULT_TASK_STATE),
    ).toBe('/task-runs/task_run_pending/qc-setup')
  })
})

describe('slot draft detection', () => {
  it('detects unapplied draft selections', () => {
    expect(hasUnappliedSlotDraft(new Set(['a']), new Set(['a']))).toBe(false)
    expect(hasUnappliedSlotDraft(new Set(['a']), new Set(['a', 'b']))).toBe(true)
  })
})
