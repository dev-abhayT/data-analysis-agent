'use client'
import { useState } from 'react'
import { exportQueryCsv } from '@/lib/api'

interface Props {
  sessionId: string
  queryId: string
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
        className="text-xs text-blue-600 hover:text-blue-800 hover:underline disabled:opacity-50 disabled:cursor-not-allowed transition"
        title="Download result as CSV"
      >
        {loading ? 'Downloading…' : 'Download CSV'}
      </button>
      {error && <span className="text-xs text-red-500">{error}</span>}
    </div>
  )
}
