'use client'
import { useState } from 'react'
import { exportQueryCsv } from '@/lib/api'

interface Props {
  sessionId: string
  queryId: string
}

function DownloadIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="currentColor"
      className="w-3 h-3"
      aria-hidden="true"
    >
      <path d="M8.75 2.75a.75.75 0 0 0-1.5 0v5.69L5.03 6.22a.75.75 0 0 0-1.06 1.06l3.5 3.5a.75.75 0 0 0 1.06 0l3.5-3.5a.75.75 0 0 0-1.06-1.06L8.75 8.44V2.75Z" />
      <path d="M3.5 9.75a.75.75 0 0 0-1.5 0v1.5A2.75 2.75 0 0 0 4.75 14h6.5A2.75 2.75 0 0 0 14 11.25v-1.5a.75.75 0 0 0-1.5 0v1.5c0 .69-.56 1.25-1.25 1.25h-6.5c-.69 0-1.25-.56-1.25-1.25v-1.5Z" />
    </svg>
  )
}

export function ExportButton({ sessionId, queryId }: Props) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleExport() {
    setLoading(true)
    setError(null)
    try {
      await exportQueryCsv(sessionId, queryId)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Export failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="inline-flex flex-col items-start gap-0.5">
      <button
        onClick={handleExport}
        disabled={loading}
        className="inline-flex items-center gap-1 text-xs text-gray-400 hover:text-blue-600 hover:underline transition-colors disabled:opacity-40"
        title="Download result as CSV"
      >
        <DownloadIcon />
        {loading ? 'Downloading…' : 'Export CSV'}
      </button>
      {error && <span className="text-xs text-red-500">{error}</span>}
    </div>
  )
}
