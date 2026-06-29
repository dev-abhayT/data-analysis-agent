'use client'
import { useRef, useState, DragEvent } from 'react'
import { Dataset } from '@/lib/types'
import { uploadFile } from '@/lib/api'

interface Props {
  sessionId: string
  onUploadSuccess: (dataset: Dataset) => void
  disabled?: boolean
}

export function FileUploader({ sessionId, onUploadSuccess, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  const MAX_BYTES = 100 * 1024 * 1024

  function validateFile(file: File): string | null {
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!['csv', 'xlsx', 'xls'].includes(ext ?? '')) {
      return 'Unsupported format — upload a .csv or .xlsx file'
    }
    if (file.size > MAX_BYTES) {
      return 'File too large — max 100 MB'
    }
    return null
  }

  async function handleFile(file: File) {
    const err = validateFile(file)
    if (err) { setError(err); return }
    setSelectedFile(file)
    setError(null)
    setUploading(true)
    try {
      const dataset = await uploadFile(sessionId, file)
      onUploadSuccess(dataset)
      setSelectedFile(null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    e.target.value = ''
  }

  return (
    <div className="space-y-2">
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !uploading && !disabled && inputRef.current?.click()}
        className={`
          relative flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-6 text-center transition cursor-pointer
          ${dragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50 hover:border-blue-400 hover:bg-blue-50/50'}
          ${(uploading || disabled) ? 'opacity-60 cursor-not-allowed' : ''}
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          onChange={onInputChange}
          className="hidden"
          disabled={uploading || disabled}
        />
        {uploading ? (
          <>
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
            <p className="text-sm text-gray-500">Uploading {selectedFile?.name}…</p>
          </>
        ) : (
          <>
            <svg className="h-8 w-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
            </svg>
            <p className="text-sm font-medium text-gray-700">Drop CSV or Excel file here</p>
            <p className="text-xs text-gray-400">or click to browse · max 100 MB</p>
          </>
        )}
      </div>
      {error && (
        <p className="text-xs text-red-600 px-1">{error}</p>
      )}
    </div>
  )
}
