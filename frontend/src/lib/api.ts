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

export function openStream(sessionId: string, queryId: string): EventSource {
  return new EventSource(`${API_BASE}/api/sessions/${sessionId}/queries/${queryId}/stream`)
}
