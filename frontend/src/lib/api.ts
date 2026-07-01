import { Dataset, SessionDetail } from '@/lib/types'

const API_BASE = ''  // same origin

export async function createSession(): Promise<{ session_id: string; created_at: string }> {
  const res = await fetch(`${API_BASE}/api/sessions`, { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to create session: ${res.status}`)
  const json = await res.json()
  return json.data
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`)
  if (!res.ok) throw new Error(`Failed to get session: ${res.status}`)
  const json = await res.json()
  return json.data
}

export async function uploadFile(sessionId: string, file: File): Promise<Dataset> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/files`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err?.detail?.message ?? `Upload failed: ${res.status}`)
  }
  const json = await res.json()
  return json.data
}

export async function submitQuery(
  sessionId: string,
  question: string
): Promise<{ query_id: string; status: string }> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err?.detail?.message ?? `Query failed: ${res.status}`)
  }
  const json = await res.json()
  return json.data
}

export function openStream(sessionId: string, queryId: string, datasetIds?: string[]): EventSource {
  let url = `${API_BASE}/api/sessions/${sessionId}/queries/${queryId}/stream`
  if (datasetIds && datasetIds.length > 0) {
    url += `?dataset_ids=${encodeURIComponent(datasetIds.join(','))}`
  }
  return new EventSource(url)
}

export async function deleteDataset(sessionId: string, datasetId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/datasets/${datasetId}`, {
    method: 'DELETE',
  })
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err?.detail?.message ?? `Delete failed: ${res.status}`)
  }
}

export async function exportQueryCsv(sessionId: string, queryId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/queries/${queryId}/export`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err?.detail?.message ?? `Export failed: ${res.status}`)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `query_${queryId.slice(0, 8)}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
