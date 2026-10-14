import { useRef, useState, type DragEvent } from 'react'
import { FileText, Upload, X } from 'lucide-react'

import { cn } from 'cn'
import { showSlotUploadInvalidFileHint } from '@/lib/launcher-start-guard'
import { isAcceptedSlotUploadFile } from '@/lib/slot-upload-file'

type SlotFileUploadProps = {
  inputId: string
  title: string
  helpText?: string | null
  expectedDocumentType?: string | null
  file: File | null
  disabled?: boolean
  className?: string
  onFileChange: (file: File | null) => void
}

export function SlotFileUpload({
  inputId,
  title,
  helpText: _helpText,
  expectedDocumentType: _expectedDocumentType,
  file,
  disabled = false,
  className,
  onFileChange,
}: SlotFileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const dragDepthRef = useRef(0)
  const [isDragOver, setIsDragOver] = useState(false)

  const commitSelectedFile = (nextFile: File | null) => {
    if (nextFile === null) {
      return
    }
    if (!isAcceptedSlotUploadFile(nextFile)) {
      if (inputRef.current) {
        inputRef.current.value = ''
      }
      showSlotUploadInvalidFileHint()
      return
    }
    onFileChange(nextFile)
  }

  const openFilePicker = () => {
    if (disabled) {
      return
    }
    inputRef.current?.click()
  }

  const clearFile = () => {
    if (disabled) {
      return
    }
    if (inputRef.current) {
      inputRef.current.value = ''
    }
    onFileChange(null)
  }

  const endDragOver = () => {
    dragDepthRef.current = 0
    setIsDragOver(false)
  }

  const handleDragEnter = (event: DragEvent<HTMLButtonElement>) => {
    if (disabled) {
      return
    }
    event.preventDefault()
    event.stopPropagation()
    dragDepthRef.current += 1
    setIsDragOver(true)
  }

  const handleDragOver = (event: DragEvent<HTMLButtonElement>) => {
    if (disabled) {
      return
    }
    event.preventDefault()
    event.stopPropagation()
  }

  const handleDragLeave = (event: DragEvent<HTMLButtonElement>) => {
    if (disabled) {
      return
    }
    event.preventDefault()
    event.stopPropagation()
    dragDepthRef.current -= 1
    if (dragDepthRef.current <= 0) {
      endDragOver()
    }
  }

  const handleDrop = (event: DragEvent<HTMLButtonElement>) => {
    if (disabled) {
      return
    }
    event.preventDefault()
    event.stopPropagation()
    endDragOver()
    const nextFile = event.dataTransfer?.files?.[0] ?? null
    commitSelectedFile(nextFile)
  }

  return (
    <div className={cn('relative mx-auto w-full max-w-xl', className)}>
      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept=".docx"
        disabled={disabled}
        className="sr-only"
        onChange={(event) => {
          const nextFile = event.target.files?.[0] ?? null
          commitSelectedFile(nextFile)
        }}
      />

      {file ? (
        <div
          className={cn(
            'relative flex min-h-64 flex-col items-center justify-center gap-5 rounded-xl border border-[#BFDBFE] bg-[#EFF6FF] px-10 py-12 text-center',
            disabled && 'opacity-60',
          )}
        >
          <button
            type="button"
            className={cn(
              'absolute top-3 right-3 inline-flex size-7 items-center justify-center rounded-md text-[#64748B] transition-colors',
              'hover:bg-white hover:text-[#1E293B]',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400/50',
              disabled && 'pointer-events-none',
            )}
            aria-label="移除文件"
            disabled={disabled}
            onClick={clearFile}
          >
            <X className="size-4" aria-hidden="true" />
          </button>
          <div className="flex size-14 items-center justify-center rounded-full bg-[#DBEAFE]">
            <FileText className="size-7 text-[#2563EB]" aria-hidden="true" />
          </div>
          <p className="max-w-full break-all text-[15px] font-semibold text-[#1E293B]">
            {file.name}
          </p>
        </div>
      ) : (
        <button
          type="button"
          data-slot="slot-file-upload-target"
          data-drag-over={isDragOver ? 'true' : undefined}
          disabled={disabled}
          onClick={openFilePicker}
          onDragEnter={handleDragEnter}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={cn(
            'group flex min-h-64 w-full flex-col items-center justify-center gap-5 rounded-xl border-[1.5px] border-dashed border-[#93C5FD] bg-white px-10 py-12 text-center transition-colors',
            'hover:border-[#60A5FA] hover:bg-[#EFF6FF]',
            isDragOver && 'border-[#60A5FA] bg-[#EFF6FF]',
            'focus-visible:border-[#2563EB] focus-visible:ring-4 focus-visible:ring-blue-100 focus-visible:outline-none',
            disabled && 'pointer-events-none opacity-60',
          )}
        >
          <div
            className={cn(
              'flex size-14 items-center justify-center rounded-full bg-[#EFF6FF] transition-colors group-hover:bg-[#DBEAFE]',
              isDragOver && 'bg-[#DBEAFE]',
            )}
          >
            <Upload className="size-7 text-[#2563EB]" aria-hidden="true" />
          </div>
          <div className="space-y-2.5">
            <p className="text-[15px] font-semibold text-[#1E293B]">{title}</p>
            <p className="text-[13px] text-[#334155]">目前仅支持中文 .docx 文件</p>
          </div>
        </button>
      )}
    </div>
  )
}
