import { describe, expect, it } from 'vitest'

import { isAcceptedSlotUploadFile } from '@/lib/slot-upload-file'

describe('isAcceptedSlotUploadFile', () => {
  it('accepts filenames ending in .docx regardless of MIME type', () => {
    const file = new File(['content'], 'report.DOCX', { type: 'application/octet-stream' })
    expect(isAcceptedSlotUploadFile(file)).toBe(true)
  })

  it('rejects non-docx extensions', () => {
    const file = new File(['content'], 'notes.txt', { type: 'text/plain' })
    expect(isAcceptedSlotUploadFile(file)).toBe(false)
  })

  it('rejects bare .docx filename', () => {
    const file = new File(['content'], '.docx', { type: 'application/octet-stream' })
    expect(isAcceptedSlotUploadFile(file)).toBe(false)
  })
})
