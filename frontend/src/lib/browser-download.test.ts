// @vitest-environment happy-dom
import { afterEach, expect, it, vi } from 'vitest'
import { downloadBlob } from '@/lib/browser-download'

afterEach(() => vi.restoreAllMocks())

it('starts the filename download and releases its object URL and temporary anchor', () => {
  const blob = new Blob(['%PDF-test'], { type: 'application/pdf' })
  const create = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:report')
  const revoke = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () {
    expect(this.download).toBe('中文_质控审查报告.pdf')
    expect(this.href).toBe('blob:report')
    expect(this.isConnected).toBe(true)
  })
  downloadBlob(blob, '中文_质控审查报告.pdf')
  expect(create).toHaveBeenCalledWith(blob)
  expect(click).toHaveBeenCalledOnce()
  expect(revoke).toHaveBeenCalledWith('blob:report')
  expect(document.querySelector('a[download]')).toBeNull()
})
