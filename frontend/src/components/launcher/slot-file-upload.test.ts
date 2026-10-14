// @vitest-environment happy-dom

import { act, createElement, useState } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { SlotFileUpload } from '@/components/launcher/slot-file-upload'
import { showSlotUploadInvalidFileHint } from '@/lib/launcher-start-guard'

vi.mock('@/lib/launcher-start-guard', async () => {
  const actual = await vi.importActual<typeof import('@/lib/launcher-start-guard')>(
    '@/lib/launcher-start-guard',
  )
  return {
    ...actual,
    showSlotUploadInvalidFileHint: vi.fn(actual.showSlotUploadInvalidFileHint),
  }
})

const mockShowSlotUploadInvalidFileHint = vi.mocked(showSlotUploadInvalidFileHint)

function makeFile(name: string): File {
  return new File(['content'], name, {
    type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  })
}

function TwoSlotHarness({
  onSlotAChange,
  onSlotBChange,
}: {
  onSlotAChange: (file: File | null) => void
  onSlotBChange: (file: File | null) => void
}) {
  const [slotAFile, setSlotAFile] = useState<File | null>(null)
  const [slotBFile, setSlotBFile] = useState<File | null>(null)

  return createElement(
    'div',
    null,
    createElement(SlotFileUpload, {
      inputId: 'slot-upload-a',
      title: '点击上传 DSUR',
      file: slotAFile,
      onFileChange: (file) => {
        setSlotAFile(file)
        onSlotAChange(file)
      },
    }),
    createElement(SlotFileUpload, {
      inputId: 'slot-upload-b',
      title: '点击上传 IB',
      file: slotBFile,
      onFileChange: (file) => {
        setSlotBFile(file)
        onSlotBChange(file)
      },
    }),
  )
}

describe('SlotFileUpload', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    mockShowSlotUploadInvalidFileHint.mockClear()
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
    vi.restoreAllMocks()
  })

  function getClearButton(): HTMLButtonElement {
    const button = container.querySelector('button[aria-label="移除文件"]')
    if (!(button instanceof HTMLButtonElement)) {
      throw new Error('clear button not found')
    }
    return button
  }

  function getUploadTarget(): HTMLButtonElement {
    const uploadButton = container.querySelector('[data-slot="slot-file-upload-target"]')
    if (!(uploadButton instanceof HTMLButtonElement)) {
      throw new Error('upload target not found')
    }
    return uploadButton
  }

  function makeDataTransferWithFiles(files: File[]): DataTransfer {
    const dataTransfer = new DataTransfer()
    for (const file of files) {
      dataTransfer.items.add(file)
    }
    return dataTransfer
  }

  function dispatchPickerFile(inputId: string, file: File): void {
    const fileInput = getHiddenFileInput(inputId)
    act(() => {
      Object.defineProperty(fileInput, 'files', {
        configurable: true,
        value: [file],
      })
      fileInput.dispatchEvent(new Event('change', { bubbles: true }))
    })
  }

  function dispatchDragEvent(
    target: HTMLElement,
    type: 'dragenter' | 'dragleave' | 'drop',
    files: File[] = [],
  ): DragEvent {
    const event = new DragEvent(type, { bubbles: true, cancelable: true })
    if (files.length > 0) {
      Object.defineProperty(event, 'dataTransfer', {
        configurable: true,
        value: makeDataTransferWithFiles(files),
      })
    }
    act(() => {
      target.dispatchEvent(event)
    })
    return event
  }

  function getHiddenFileInput(inputId = 'slot-upload-source'): HTMLInputElement {
    const input = container.querySelector(`#${inputId}`)
    if (!(input instanceof HTMLInputElement)) {
      throw new Error(`file input #${inputId} not found`)
    }
    return input
  }

  it('shows clear icon when a file is selected and hides replace-file copy', () => {
    act(() => {
      root.render(
        createElement(SlotFileUpload, {
          inputId: 'slot-upload-source',
          title: '点击上传 DSUR',
          helpText: '请上传 DSUR 文件',
          expectedDocumentType: 'DSUR',
          file: makeFile('dsur.docx'),
          onFileChange: () => {},
        }),
      )
    })

    expect(container.querySelector('button[aria-label="移除文件"]')).not.toBeNull()
    expect(container.textContent).toContain('dsur.docx')
    expect(container.textContent).not.toContain('更换文件')
    expect(container.textContent).not.toContain('移除文件')
  })

  it('clears the current slot when the clear icon is clicked', () => {
    const onFileChange = vi.fn()

    act(() => {
      root.render(
        createElement(SlotFileUpload, {
          inputId: 'slot-upload-source',
          title: '点击上传 DSUR',
          file: makeFile('dsur.docx'),
          onFileChange,
        }),
      )
    })

    act(() => {
      getClearButton().click()
    })

    expect(onFileChange).toHaveBeenCalledTimes(1)
    expect(onFileChange).toHaveBeenCalledWith(null)
  })

  it('restores the initial upload UI after clearing', () => {
    const onFileChange = vi.fn()

    act(() => {
      root.render(
        createElement(SlotFileUpload, {
          inputId: 'slot-upload-source',
          title: '点击上传 DSUR',
          file: makeFile('dsur.docx'),
          onFileChange,
        }),
      )
    })

    act(() => {
      getClearButton().click()
    })

    act(() => {
      root.render(
        createElement(SlotFileUpload, {
          inputId: 'slot-upload-source',
          title: '点击上传 DSUR',
          helpText: '请上传 DSUR 文件',
          expectedDocumentType: 'DSUR',
          file: null,
          onFileChange,
        }),
      )
    })

    expect(container.textContent).toContain('点击上传 DSUR')
    expect(container.textContent).toContain('目前仅支持中文 .docx 文件')
    expect(container.querySelector('button[aria-label="移除文件"]')).toBeNull()
    expect(getUploadTarget()).not.toBeNull()
  })

  it('does not clear sibling slots in a multi-slot layout', () => {
    const onSlotAChange = vi.fn()
    const onSlotBChange = vi.fn()

    act(() => {
      root.render(
        createElement(TwoSlotHarness, {
          onSlotAChange,
          onSlotBChange,
        }),
      )
    })

    const slotBInput = getHiddenFileInput('slot-upload-b')
    act(() => {
      Object.defineProperty(slotBInput, 'files', {
        configurable: true,
        value: [makeFile('ib.docx')],
      })
      slotBInput.dispatchEvent(new Event('change', { bubbles: true }))
    })

    const clearButtons = [...container.querySelectorAll('button[aria-label="移除文件"]')]
    expect(clearButtons).toHaveLength(1)

    act(() => {
      clearButtons[0]?.click()
    })

    expect(onSlotAChange).not.toHaveBeenCalled()
    expect(onSlotBChange).toHaveBeenCalledWith(null)
    expect(container.textContent).toContain('点击上传 IB')
    expect(container.textContent).toContain('点击上传 DSUR')
  })

  it('allows re-selecting the same file after clearing by resetting the hidden input', () => {
    const onFileChange = vi.fn()
    const sameFile = makeFile('dsur.docx')

    act(() => {
      root.render(
        createElement(SlotFileUpload, {
          inputId: 'slot-upload-source',
          title: '点击上传 DSUR',
          file: null,
          onFileChange,
        }),
      )
    })

    const fileInput = getHiddenFileInput()
    act(() => {
      Object.defineProperty(fileInput, 'files', {
        configurable: true,
        value: [sameFile],
      })
      fileInput.dispatchEvent(new Event('change', { bubbles: true }))
    })

    act(() => {
      root.render(
        createElement(SlotFileUpload, {
          inputId: 'slot-upload-source',
          title: '点击上传 DSUR',
          file: sameFile,
          onFileChange,
        }),
      )
    })

    act(() => {
      getClearButton().click()
    })

    expect(fileInput.value).toBe('')
    expect(onFileChange).toHaveBeenCalledWith(null)

    act(() => {
      root.render(
        createElement(SlotFileUpload, {
          inputId: 'slot-upload-source',
          title: '点击上传 DSUR',
          file: null,
          onFileChange,
        }),
      )
    })

    act(() => {
      Object.defineProperty(fileInput, 'files', {
        configurable: true,
        value: [sameFile],
      })
      fileInput.dispatchEvent(new Event('change', { bubbles: true }))
    })

    expect(onFileChange).toHaveBeenLastCalledWith(sameFile)
  })

  it('does not open the file picker or call backend when clearing', () => {
    const onFileChange = vi.fn()
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click')

    act(() => {
      root.render(
        createElement(SlotFileUpload, {
          inputId: 'slot-upload-source',
          title: '点击上传 DSUR',
          file: makeFile('dsur.docx'),
          onFileChange,
        }),
      )
    })

    act(() => {
      getClearButton().click()
    })

    expect(clickSpy).not.toHaveBeenCalled()
    expect(onFileChange).toHaveBeenCalledWith(null)
  })

  it('opens the hidden file input when the upload target is clicked', () => {
    const clickSpy = vi.spyOn(HTMLInputElement.prototype, 'click')

    act(() => {
      root.render(
        createElement(SlotFileUpload, {
          inputId: 'slot-upload-source',
          title: 'Fixture upload title',
          file: null,
          onFileChange: () => {},
        }),
      )
    })

    act(() => {
      getUploadTarget().click()
    })

    expect(clickSpy).toHaveBeenCalled()
  })

  it('accepts a valid docx selected through the file input', () => {
    const onFileChange = vi.fn()
    const selectedFile = makeFile('picked.docx')

    act(() => {
      root.render(
        createElement(SlotFileUpload, {
          inputId: 'slot-upload-source',
          title: 'Fixture upload title',
          file: null,
          onFileChange,
        }),
      )
    })

    dispatchPickerFile('slot-upload-source', selectedFile)

    expect(onFileChange).toHaveBeenCalledTimes(1)
    expect(onFileChange).toHaveBeenCalledWith(selectedFile)
    expect(mockShowSlotUploadInvalidFileHint).not.toHaveBeenCalled()
  })

  it('rejects an invalid file selected through the file input', () => {
    const onFileChange = vi.fn()
    const invalidFile = new File(['content'], 'notes.txt', { type: 'text/plain' })

    act(() => {
      root.render(
        createElement(SlotFileUpload, {
          inputId: 'slot-upload-source',
          title: 'Fixture upload title',
          file: null,
          onFileChange,
        }),
      )
    })

    dispatchPickerFile('slot-upload-source', invalidFile)

    expect(onFileChange).not.toHaveBeenCalled()
    expect(mockShowSlotUploadInvalidFileHint).toHaveBeenCalledTimes(1)
  })

  it('selects a dropped file through the same commit path as the file input', () => {
    const onFileChange = vi.fn()
    const droppedFile = makeFile('dropped.docx')

    act(() => {
      root.render(
        createElement(SlotFileUpload, {
          inputId: 'slot-upload-source',
          title: 'Fixture upload title',
          file: null,
          onFileChange,
        }),
      )
    })

    const uploadTarget = getUploadTarget()
    dispatchDragEvent(uploadTarget, 'drop', [droppedFile])

    expect(onFileChange).toHaveBeenCalledTimes(1)
    expect(onFileChange).toHaveBeenCalledWith(droppedFile)
    expect(mockShowSlotUploadInvalidFileHint).not.toHaveBeenCalled()
  })

  it('rejects invalid dropped files through the same validation path as the picker', () => {
    const onFileChange = vi.fn()
    const invalidFile = new File(['content'], 'notes.txt', { type: 'text/plain' })

    act(() => {
      root.render(
        createElement(SlotFileUpload, {
          inputId: 'slot-upload-source',
          title: 'Fixture upload title',
          file: null,
          onFileChange,
        }),
      )
    })

    dispatchDragEvent(getUploadTarget(), 'drop', [invalidFile])

    expect(onFileChange).not.toHaveBeenCalled()
    expect(mockShowSlotUploadInvalidFileHint).toHaveBeenCalledTimes(1)
  })

  it('clears drag-over state after an invalid drop', () => {
    const onFileChange = vi.fn()
    const invalidFile = new File(['content'], 'notes.txt', { type: 'text/plain' })

    act(() => {
      root.render(
        createElement(SlotFileUpload, {
          inputId: 'slot-upload-source',
          title: 'Fixture upload title',
          file: null,
          onFileChange,
        }),
      )
    })

    const uploadTarget = getUploadTarget()
    dispatchDragEvent(uploadTarget, 'dragenter')
    expect(uploadTarget.getAttribute('data-drag-over')).toBe('true')

    dispatchDragEvent(uploadTarget, 'drop', [invalidFile])

    expect(uploadTarget.getAttribute('data-drag-over')).toBeNull()
    expect(onFileChange).not.toHaveBeenCalled()
  })

  it('uses only the first file when multiple files are dropped', () => {
    const onFileChange = vi.fn()
    const firstFile = makeFile('first.docx')
    const secondFile = makeFile('second.docx')

    act(() => {
      root.render(
        createElement(SlotFileUpload, {
          inputId: 'slot-upload-source',
          title: 'Fixture upload title',
          file: null,
          onFileChange,
        }),
      )
    })

    dispatchDragEvent(getUploadTarget(), 'drop', [firstFile, secondFile])

    expect(onFileChange).toHaveBeenCalledWith(firstFile)
  })

  it('shows and clears drag-over affordance on enter, leave, and drop', () => {
    act(() => {
      root.render(
        createElement(SlotFileUpload, {
          inputId: 'slot-upload-source',
          title: 'Fixture upload title',
          file: null,
          onFileChange: () => {},
        }),
      )
    })

    const uploadTarget = getUploadTarget()

    dispatchDragEvent(uploadTarget, 'dragenter')
    expect(uploadTarget.getAttribute('data-drag-over')).toBe('true')
    expect(uploadTarget.className).toContain('border-[#60A5FA]')

    dispatchDragEvent(uploadTarget, 'dragleave')
    expect(uploadTarget.getAttribute('data-drag-over')).toBeNull()

    const dropEvent = new DragEvent('drop', { bubbles: true, cancelable: true })
    Object.defineProperty(dropEvent, 'dataTransfer', {
      configurable: true,
      value: makeDataTransferWithFiles([makeFile('after-drag.docx')]),
    })
    const preventDefault = vi.spyOn(dropEvent, 'preventDefault')

    act(() => {
      uploadTarget.dispatchEvent(dropEvent)
    })

    expect(preventDefault).toHaveBeenCalled()
    expect(uploadTarget.getAttribute('data-drag-over')).toBeNull()
  })
})
