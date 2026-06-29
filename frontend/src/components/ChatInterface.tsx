'use client'
import { useState, useEffect, useRef } from 'react'
import { ChatMessage } from '@/lib/types'
import { SummaryTable } from './SummaryTable'

interface Props {
  messages: ChatMessage[]
  onSendMessage: (question: string) => void
  streaming: boolean
  pendingInput?: string
  onPendingInputClear?: () => void
}

export function ChatInterface({ messages, onSendMessage, streaming, pendingInput, onPendingInputClear }: Props) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Fill input from starter question chip click
  useEffect(() => {
    if (pendingInput) {
      setInput(pendingInput)
      onPendingInputClear?.()
      // Focus after state update
      setTimeout(() => inputRef.current?.focus(), 0)
    }
  }, [pendingInput, onPendingInputClear])

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function handleSend() {
    const q = input.trim()
    if (!q || streaming) return
    onSendMessage(q)
    setInput('')
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Message list */}
      <div className="flex-1 overflow-y-auto space-y-4 p-4">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm text-gray-400 text-center px-4">
              Upload a CSV or Excel file, then ask a question to get started.
            </p>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'user' ? (
              <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-blue-600 px-4 py-2.5 text-sm text-white">
                {msg.content}
              </div>
            ) : (
              <div className="max-w-[90%] w-full rounded-2xl rounded-tl-sm border border-gray-200 bg-white px-4 py-3 shadow-sm space-y-2">
                {msg.error ? (
                  <div className="text-sm text-red-600">
                    <span className="font-medium">Error: </span>{msg.error}
                  </div>
                ) : msg.clarification ? (
                  <div className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                    <p className="font-medium text-amber-900 mb-0.5">Could you clarify?</p>
                    <p>{msg.clarification}</p>
                  </div>
                ) : (
                  <>
                    <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
                      {msg.content}
                      {msg.streaming && (
                        <span className="inline-block w-0.5 h-4 bg-gray-700 ml-0.5 animate-pulse align-text-bottom" />
                      )}
                    </p>
                    {msg.summary_table && (
                      <SummaryTable
                        columns={msg.summary_table.columns}
                        rows={msg.summary_table.rows}
                      />
                    )}
                  </>
                )}

                {/* Phase 2 stubs — always visible, never hidden */}
                <div className="pt-2 border-t border-gray-100 flex items-center gap-4 flex-wrap">
                  <span
                    title="Coming in Phase 2"
                    className="text-xs text-gray-300 cursor-default select-none"
                  >
                    Code it ran (Phase 2)
                  </span>
                  <span
                    title="Coming in Phase 2"
                    className="text-xs text-gray-300 cursor-default select-none"
                  >
                    Token cost (Phase 2)
                  </span>
                  <span
                    title="Coming in Phase 2"
                    className="text-xs text-gray-300 cursor-default select-none"
                  >
                    Download CSV (Phase 2)
                  </span>
                </div>
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="shrink-0 border-t border-gray-200 bg-white p-3">
        <div className="flex gap-2 items-end">
          <textarea
            ref={inputRef}
            rows={2}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={streaming}
            placeholder={streaming ? 'Waiting for answer…' : 'Ask a question about your data…'}
            className="flex-1 resize-none rounded-xl border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50 disabled:bg-gray-50"
          />
          <button
            onClick={handleSend}
            disabled={streaming || !input.trim()}
            className="shrink-0 h-10 px-4 rounded-xl bg-blue-600 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center justify-center gap-2"
          >
            {streaming ? (
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              'Ask'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
