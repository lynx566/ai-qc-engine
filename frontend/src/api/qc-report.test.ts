import { afterEach, describe, expect, it, vi } from 'vitest'
import { downloadQcReport } from '@/api/qc-report'

afterEach(() => vi.unstubAllGlobals())

describe('QC report download client', () => {
  it.each([
    ["attachment; filename=\"fallback.pdf\"; filename*=UTF-8''%E4%B8%AD%E6%96%87.pdf", '中文.pdf'],
    ['attachment; filename="report.pdf"', 'report.pdf'],
    [null, '质控审查报告.pdf'],
    ["attachment; filename*=UTF-8''%broken; filename=\"fallback.pdf\"", 'fallback.pdf'],
  ])('returns a PDF blob and the response filename (%s)', async (header, filename) => {
    const headers = new Headers({ 'Content-Type': 'application/pdf' })
    if (header) headers.set('Content-Disposition', header)
    const fetcher = vi.fn().mockResolvedValue(new Response('%PDF-report', { headers }))
    vi.stubGlobal('fetch', fetcher)
    const result = await downloadQcReport('task run/1')
    expect(fetcher).toHaveBeenCalledWith('/api/clinical-trial-doc-qc/task-runs/task%20run%2F1/qc-report')
    expect(result.filename).toBe(filename)
    expect(result.blob.type).toBe('application/pdf')
    expect(await result.blob.text()).toBe('%PDF-report')
  })

  it.each([
    [404, '任务不存在或无法访问。'],
    [409, '报告状态正在更新，请稍后重试。'],
    [400, '当前质控结果暂无法生成报告。'],
    [500, '报告生成失败，请稍后重试。'],
  ])('sanitizes HTTP %s failures', async (status, message) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      status: 'failed', message: 'SECRET C:/private/task_run_internal traceback',
    }), { status, headers: { 'Content-Type': 'application/json' } })))
    await expect(downloadQcReport('task_run_1')).rejects.toThrow(message)
  })

  it('sanitizes network failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('SECRET network address')))
    await expect(downloadQcReport('task_run_1')).rejects.toThrow('报告生成失败，请稍后重试。')
  })
})
