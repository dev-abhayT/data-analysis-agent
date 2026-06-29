'use client'
import { useState, useEffect, useRef, useCallback } from 'react'
import { FileUploader } from '@/components/FileUploader'
import { ProfilePanel } from '@/components/ProfilePanel'
import { StarterQuestions } from '@/components/StarterQuestions'
import { ChatInterface } from '@/components/ChatInterface'
import { Dataset, ChatMessage } from '@/lib/types'
import { createSession, getSession, submitQuery, openStream, deleteDataset } from '@/lib/api'

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [sessionError, setSessionError] = useState<string | null>(null)
  const [initLoading, setInitLoading] = useState(true)
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streaming, setStreaming] = useState(false)
  const [pendingInput, setPendingInput] = useState('')
  const esRef = useRef<EventSource | null>(null)

  // ── Session init ─────────────────────────────────────────────────────────
  useEffect(() => {
    async function init() {
      setInitLoading(true)
      const storedId = localStorage.getItem('session_id')
      if (storedId) {
        try {
          const detail = await getSession(storedId)
          setSessionId(detail.session_id)
          setDatasets(detail.datasets)
          // Restore completed queries as chat messages
          const restored: ChatMessage[] = []
          for (const q of detail.queries) {
            if (q.status === 'completed' && q.answer_text) {
              restored.push({
                id: `u-${q.query_id}`,
                role: 'user',
                content: q.question,
              })
              restored.push({
                id: `a-${q.query_id}`,
                role: 'agent',
                content: q.answer_text,
                query_id: q.query_id,
                summary_table: q.summary_table_json ?? null,
                generated_code: q.generated_code ?? '',
                reasoning_trace: q.reasoning_trace ?? '',
                prompt_tokens: q.prompt_tokens,
                completion_tokens: q.completion_tokens,
                cost_usd: q.cost_usd,
              })
            }
          }
          setMessages(restored)
          setInitLoading(false)
          return
        } catch {
          // Session not found or server error — create a new one
          localStorage.removeItem('session_id')
        }
      }

      try {
        const s = await createSession()
        localStorage.setItem('session_id', s.session_id)
        setSessionId(s.session_id)
      } catch {
        setSessionError('Could not connect to the server. Make sure it is running on port 8001.')
      } finally {
        setInitLoading(false)
      }
    }
    init()
  }, [])

  // Clean up EventSource on unmount
  useEffect(() => {
    return () => {
      esRef.current?.close()
    }
  }, [])

  // ── Upload success ────────────────────────────────────────────────────────
  function handleUploadSuccess(dataset: Dataset) {
    setDatasets(prev => [...prev, dataset])
  }

  // ── Send message & stream answer ─────────────────────────────────────────
  const handleSendMessage = useCallback(async (question: string) => {
    if (!sessionId || streaming) return

    const userMsgId = `u-${Date.now()}`
    const agentMsgId = `a-${Date.now()}`

    // Submit query to get a query_id first (before setting messages, so we have the id)
    let queryId: string
    try {
      const result = await submitQuery(sessionId, question)
      queryId = result.query_id
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to submit question'
      setMessages(prev => [
        ...prev,
        { id: userMsgId, role: 'user', content: question },
        { id: agentMsgId, role: 'agent', content: '', error: msg, streaming: false },
      ])
      return
    }

    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: 'user', content: question },
      { id: agentMsgId, role: 'agent', content: '', streaming: true, query_id: queryId },
    ])
    setStreaming(true)

    // Open SSE stream
    const es = openStream(sessionId, queryId)
    esRef.current = es

    es.onmessage = (event: MessageEvent) => {
      let data: Record<string, unknown>
      try {
        data = JSON.parse(event.data)
      } catch {
        return
      }

      const type = data.type as string

      if (type === 'token') {
        const chunk = (data.content as string) ?? ''
        setMessages(prev => prev.map(m =>
          m.id === agentMsgId ? { ...m, content: m.content + chunk } : m
        ))
      } else if (type === 'table') {
        setMessages(prev => prev.map(m =>
          m.id === agentMsgId
            ? {
                ...m,
                summary_table: {
                  columns: data.columns as string[],
                  rows: data.rows as (string | number | null)[][],
                },
              }
            : m
        ))
      } else if (type === 'code') {
        setMessages(prev => prev.map(m =>
          m.id === agentMsgId
            ? {
                ...m,
                generated_code: (data.generated_code as string) ?? '',
                reasoning_trace: (data.reasoning_trace as string) ?? '',
              }
            : m
        ))
      } else if (type === 'usage') {
        setMessages(prev => prev.map(m =>
          m.id === agentMsgId
            ? {
                ...m,
                prompt_tokens: data.prompt_tokens as number,
                completion_tokens: data.completion_tokens as number,
                cost_usd: data.cost_usd as number,
              }
            : m
        ))
      } else if (type === 'clarification') {
        setMessages(prev => prev.map(m =>
          m.id === agentMsgId
            ? { ...m, clarification: data.question as string, streaming: false }
            : m
        ))
        setStreaming(false)
        es.close()
      } else if (type === 'done') {
        setMessages(prev => prev.map(m =>
          m.id === agentMsgId ? { ...m, streaming: false } : m
        ))
        setStreaming(false)
        es.close()
      } else if (type === 'error') {
        setMessages(prev => prev.map(m =>
          m.id === agentMsgId
            ? { ...m, error: (data.message as string) ?? 'An error occurred', content: '', streaming: false }
            : m
        ))
        setStreaming(false)
        es.close()
      }
    }

    es.onerror = () => {
      // Only show error if we haven't received any content yet
      setMessages(prev => prev.map(m => {
        if (m.id !== agentMsgId) return m
        if (m.content || m.error) return { ...m, streaming: false }
        return { ...m, error: 'Stream disconnected — please try again', streaming: false }
      }))
      setStreaming(false)
      es.close()
    }
  }, [sessionId, streaming])

  // ── Dataset delete ────────────────────────────────────────────────────────
  async function handleDeleteDataset(datasetId: string) {
    if (!sessionId) return
    try {
      await deleteDataset(sessionId, datasetId)
      setDatasets(prev => prev.filter(d => d.dataset_id !== datasetId))
    } catch (e) {
      console.error('Failed to delete dataset', e)
    }
  }

  // ── Starter question chip clicked ─────────────────────────────────────────
  function handleStarterSelect(question: string) {
    setPendingInput(question)
  }

  // ── New session (on session-not-found error) ──────────────────────────────
  async function handleNewSession() {
    setSessionError(null)
    localStorage.removeItem('session_id')
    setInitLoading(true)
    try {
      const s = await createSession()
      localStorage.setItem('session_id', s.session_id)
      setSessionId(s.session_id)
      setDatasets([])
      setMessages([])
    } catch {
      setSessionError('Could not create a new session. Is the server running?')
    } finally {
      setInitLoading(false)
    }
  }

  // ── Collect all starter questions from all datasets (max 3) ──────────────
  const allStarterQuestions = datasets
    .flatMap(d => d.starter_questions ?? [])
    .slice(0, 3)

  // ── Render states ─────────────────────────────────────────────────────────
  if (initLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
      </div>
    )
  }

  if (sessionError) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50 p-8">
        <div className="text-center space-y-4 max-w-sm">
          <p className="text-red-600 font-medium">{sessionError}</p>
          <button
            onClick={handleNewSession}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Try again
          </button>
        </div>
      </div>
    )
  }

  // ── Main layout ───────────────────────────────────────────────────────────
  return (
    <div className="flex h-screen flex-col bg-gray-50">
      {/* Header */}
      <header className="shrink-0 border-b border-gray-200 bg-white px-6 py-3 flex items-center justify-between shadow-sm">
        <h1 className="text-lg font-semibold text-gray-900">Data Analysis Agent</h1>
        <span className="text-xs text-gray-400 font-mono hidden sm:block">
          Session {sessionId?.slice(0, 8)}…
        </span>
      </header>

      {/* Two-panel body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel — file upload + profile + starter questions */}
        <div className="w-72 shrink-0 overflow-y-auto border-r border-gray-200 bg-white p-4 space-y-4">
          <div>
            <p className="mb-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">Data files</p>
            <FileUploader
              sessionId={sessionId!}
              onUploadSuccess={handleUploadSuccess}
              disabled={streaming || datasets.length >= 3}
            />
            {datasets.length >= 3 && (
              <p className="mt-1.5 text-xs text-gray-400 text-center">Max 3 files per session</p>
            )}
          </div>

          {datasets.map(d => (
            <ProfilePanel key={d.dataset_id} dataset={d} onDelete={handleDeleteDataset} />
          ))}

          {allStarterQuestions.length > 0 && (
            <StarterQuestions
              questions={allStarterQuestions}
              onSelect={handleStarterSelect}
              disabled={streaming}
            />
          )}
        </div>

        {/* Right panel — chat */}
        <div className="flex flex-1 flex-col overflow-hidden">
          <ChatInterface
            messages={messages}
            onSendMessage={handleSendMessage}
            streaming={streaming}
            pendingInput={pendingInput}
            onPendingInputClear={() => setPendingInput('')}
            sessionId={sessionId}
          />
        </div>
      </div>
    </div>
  )
}
