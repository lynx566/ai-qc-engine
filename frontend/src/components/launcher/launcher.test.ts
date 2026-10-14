import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

describe('launcher component boundaries', () => {
  it('loads catalog on init and renders slots from catalog entries', () => {
    const source = readFileSync(resolve(import.meta.dirname, 'launcher.tsx'), 'utf8')

    expect(source).toContain('fetchTaskCatalog')
    expect(source).not.toContain('internal_dsur')
    expect(source).not.toContain('source_a')
    expect(source).not.toContain('source_b')
    expect(source).toContain('selectedTask.slots.map')
    expect(source).toContain('sortCatalogByTaskOrder')
    expect(source).toContain('SlotFileUpload')
    expect(source).toContain("from '@/components/launcher/launcher-page-shell'")
    expect(source).toContain('LauncherPageShell')
    expect(source).toContain('LauncherPageCard')
    expect(source).toContain('若您上传的文件中存在修订痕迹，系统会自动接受所有修订再进行质控。')
    expect(source).toContain('text-[#94A3B8]')
    expect(source).toContain('bg-[#F1F5F9]')
    expect(source).not.toContain('capability-select')
    expect(source).not.toContain('selectedTask.description')
    expect(source).toContain('getTaskTabLabel')
    expect(source).toContain('getTaskTabTooltip')
  })

  it('only starts Product Task on start click', () => {
    const source = readFileSync(resolve(import.meta.dirname, 'launcher.tsx'), 'utf8')

    expect(source).toContain('startClinicalTrialDocQcTask')
    expect(source).not.toMatch(/onChange[\s\S]*startClinicalTrialDocQcTask/)
    expect(source).toContain('resolveLauncherStartAttempt')
    expect(source).toContain('功能准备中…')
    expect(source).toContain("'开始'")
    expect(source).toContain('showLauncherUploadRequiredHint')
    expect(source).not.toContain('role="status"')
    expect(source).not.toContain('cursor-not-allowed')
    expect(source).toContain("disabled={startSubmitting}")
    expect(source).not.toContain('disabled={startDisabled}')
    expect(source).toContain('taskQcSetupRoutePath')
    expect(source).toContain('result.taskRunId')
  })
})
