'use client'
import { useState, useEffect, useRef } from 'react'
import { ChatMessage, Dataset } from '@/lib/types'
import { SummaryTable } from './SummaryTable'
import { CodeTrace } from './CodeTrace'
import { TokenCost } from './TokenCost'
import { ExportButton } from './ExportButton'
import { ChartView } from './ChartView'

const THINKING_PHRASES = [
  'Analyzing your data…',
  'Running the numbers…',
  'Looking through the dataset…',
  'Computing insights…',
  'Thinking…',
  'Preparing your answer…',
]

function ThinkingPlaceholder() {
  const [idx, setIdx] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setIdx(i => (i + 1) % THINKING_PHRASES.length), 1800)
    return () => clearInterval(t)
  }, [])
  return (
    <div className="flex items-center gap-2">
      <span className="flex gap-0.5">
        {[0, 1, 2].map(i => (
          <span
            key={i}
            className="inline-block h-2 w-2 rounded-full bg-gray-200 animate-bounce"
            style={{ animationDelay: `${i * 150}ms` }}
          />
        ))}
      </span>
      <span className="text-gray-400 text-sm italic transition-opacity duration-300">{THINKING_PHRASES[idx]}</span>
    </div>
  )
}

// ---- Inline markdown renderer ----

type Segment =
  | { kind: 'text'; value: string }
  | { kind: 'bold'; value: string }
  | { kind: 'italic'; value: string }

function parseInline(text: string): Segment[] {
  const segments: Segment[] = []
  // Match **bold** first (must come before *italic* to avoid consuming leading *)
  const re = /(\*\*(.+?)\*\*|\*(.+?)\*)/g
  let last = 0
  let match: RegExpExecArray | null
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) {
      // Strip any stray * or ** that weren't consumed
      const raw = text.slice(last, match.index).replace(/\*+/g, '')
      if (raw) segments.push({ kind: 'text', value: raw })
    }
    if (match[0].startsWith('**')) {
      segments.push({ kind: 'bold', value: match[2] })
    } else {
      segments.push({ kind: 'italic', value: match[3] })
    }
    last = match.index + match[0].length
  }
  if (last < text.length) {
    const raw = text.slice(last).replace(/\*+/g, '')
    if (raw) segments.push({ kind: 'text', value: raw })
  }
  return segments
}

function InlineContent({ text }: { text: string }) {
  const segments = parseInline(text)
  return (
    <>
      {segments.map((s, i) => {
        if (s.kind === 'bold') return <strong key={i} className="font-semibold text-gray-900">{s.value}</strong>
        if (s.kind === 'italic') return <em key={i}>{s.value}</em>
        return <span key={i}>{s.value}</span>
      })}
    </>
  )
}

function MarkdownText({ text, streaming }: { text: string; streaming?: boolean }) {
  const lines = text.split('\n')

  // Group consecutive lines into blocks
  type Block =
    | { type: 'ul'; items: string[] }
    | { type: 'ol'; items: string[] }
    | { type: 'p'; value: string }
    | { type: 'heading'; level: 1 | 2 | 3; value: string }
    | { type: 'hr' }
    | { type: 'blank' }

  const blocks: Block[] = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]

    // Horizontal rule: --- or *** on its own line
    if (/^(-{3,}|\*{3,})$/.test(line.trim())) {
      blocks.push({ type: 'hr' })
      i++
      continue
    }
    // Headings: # / ## / ###
    const headingMatch = line.match(/^(#{1,3}) (.+)/)
    if (headingMatch) {
      const level = Math.min(headingMatch[1].length, 3) as 1 | 2 | 3
      blocks.push({ type: 'heading', level, value: headingMatch[2] })
      i++
      continue
    }
    // Unordered list item (•, -, * followed by space — but not *** which is hr)
    if (/^[•\-] /.test(line) || /^\* /.test(line)) {
      const items: string[] = []
      while (i < lines.length && (/^[•\-] /.test(lines[i]) || /^\* /.test(lines[i]))) {
        items.push(lines[i].replace(/^[•\-\*] /, ''))
        i++
      }
      blocks.push({ type: 'ul', items })
      continue
    }
    // Ordered list item
    if (/^\d+\. /.test(line)) {
      const items: string[] = []
      while (i < lines.length && /^\d+\. /.test(lines[i])) {
        items.push(lines[i].replace(/^\d+\. /, ''))
        i++
      }
      blocks.push({ type: 'ol', items })
      continue
    }
    // Blank line
    if (line.trim() === '') {
      blocks.push({ type: 'blank' })
      i++
      continue
    }
    // Paragraph (em-dash separator replacement: ` — ` → ` · `)
    const normalised = line.replace(/ [—–] /g, ' · ')
    blocks.push({ type: 'p', value: normalised })
    i++
  }

  // Streaming cursor goes inside the last rendered element
  const cursor = streaming ? (
    <span className="inline-block w-0.5 h-3.5 bg-gray-500 ml-0.5 animate-pulse align-text-bottom" />
  ) : null

  return (
    <>
      {blocks.map((block, bi) => {
        const isLast = bi === blocks.length - 1

        if (block.type === 'blank') {
          return <div key={bi} className="h-2" />
        }
        if (block.type === 'hr') {
          return <hr key={bi} className="my-2 border-gray-100" />
        }
        if (block.type === 'heading') {
          return (
            <p key={bi} className="font-semibold text-gray-800 text-sm mt-2 mb-0.5">
              <InlineContent text={block.value} />
              {isLast && cursor}
            </p>
          )
        }
        if (block.type === 'ul') {
          return (
            <ul key={bi} className="my-2 pl-5 list-disc space-y-0.5">
              {block.items.map((item, ii) => {
                const itemIsLast = isLast && ii === block.items.length - 1
                return (
                  <li key={ii} className="text-sm text-gray-700 leading-relaxed">
                    <InlineContent text={item} />
                    {itemIsLast && cursor}
                  </li>
                )
              })}
            </ul>
          )
        }
        if (block.type === 'ol') {
          return (
            <ol key={bi} className="my-2 pl-5 list-decimal space-y-0.5">
              {block.items.map((item, ii) => {
                const itemIsLast = isLast && ii === block.items.length - 1
                return (
                  <li key={ii} className="text-sm text-gray-700 leading-relaxed">
                    <InlineContent text={item} />
                    {itemIsLast && cursor}
                  </li>
                )
              })}
            </ol>
          )
        }
        // paragraph
        return (
          <p key={bi} className="text-sm text-gray-700 leading-relaxed">
            <InlineContent text={block.value} />
            {isLast && cursor}
          </p>
        )
      })}
    </>
  )
}

// ---- Agent avatar ----
function AgentAvatar() {
  return (
    <div className="w-7 h-7 rounded-full bg-linear-to-br from-violet-500 to-blue-500 flex items-center justify-center shrink-0">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 16 16"
        fill="white"
        className="w-3.5 h-3.5"
        aria-hidden="true"
      >
        {/* sparkle / star shape */}
        <path d="M8 1l1.5 4.5L14 7l-4.5 1.5L8 13l-1.5-4.5L2 7l4.5-1.5z" />
      </svg>
    </div>
  )
}

// ---- Paper-plane send icon ----
function SendIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="currentColor"
      className="w-4 h-4"
      aria-hidden="true"
    >
      <path d="M3.105 2.288a.75.75 0 0 0-.826.95l1.414 4.926A1.5 1.5 0 0 0 5.135 9.25h6.115a.75.75 0 0 1 0 1.5H5.135a1.5 1.5 0 0 0-1.442 1.086l-1.414 4.926a.75.75 0 0 0 .826.95 28.897 28.897 0 0 0 15.293-7.154.75.75 0 0 0 0-1.115A28.897 28.897 0 0 0 3.105 2.288Z" />
    </svg>
  )
}

// ---- Empty state icon ----
function DataIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 48 48"
      fill="none"
      className="w-12 h-12 text-gray-300"
      aria-hidden="true"
    >
      <rect x="6" y="10" width="36" height="28" rx="4" stroke="currentColor" strokeWidth="2" />
      <line x1="6" y1="18" x2="42" y2="18" stroke="currentColor" strokeWidth="2" />
      <line x1="6" y1="26" x2="42" y2="26" stroke="currentColor" strokeWidth="2" />
      <line x1="18" y1="10" x2="18" y2="38" stroke="currentColor" strokeWidth="2" />
    </svg>
  )
}

interface Props {
  messages: ChatMessage[]
  onSendMessage: (question: string) => void
  streaming: boolean
  pendingInput?: string
  onPendingInputClear?: () => void
  sessionId: string | null
  datasets?: Dataset[]
  selectedDatasetIds?: Set<string>
  onDatasetToggle?: (id: string) => void
  onSuggestionSelect?: (q: string) => void
}

export function ChatInterface({ messages, onSendMessage, streaming, pendingInput, onPendingInputClear, sessionId, datasets, selectedDatasetIds, onDatasetToggle, onSuggestionSelect }: Props) {
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
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-6">
            <DataIcon />
            <h3 className="text-base font-semibold text-gray-700">Ask about your data</h3>
            <p className="text-sm text-gray-400 max-w-xs">
              Upload a file on the left, then ask anything in plain English.
            </p>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'user' ? (
              <div className="max-w-[75%] rounded-2xl rounded-tr-sm bg-blue-600 px-4 py-2.5 text-sm text-white">
                {msg.content}
              </div>
            ) : (
              <div className="flex items-start gap-2.5 max-w-[92%] w-full">
                <AgentAvatar />
                <div className="flex-1 rounded-2xl rounded-tl-sm bg-white shadow-sm border border-gray-100">
                  <div className="px-4 py-3 space-y-3">
                    {msg.error ? (
                      <div className="text-sm text-red-600">
                        <span className="font-medium">Error: </span>{msg.error}
                      </div>
                    ) : (
                      <>
                        {msg.streaming && !msg.content ? (
                          <ThinkingPlaceholder />
                        ) : (
                          <MarkdownText text={msg.content} streaming={msg.streaming} />
                        )}
                        {msg.chart_data && !msg.streaming && (
                          <div className="rounded-xl border border-gray-100 bg-gray-50/60 overflow-hidden">
                            <ChartView chart={msg.chart_data} />
                          </div>
                        )}
                        {msg.summary_table && !msg.streaming && !msg.chart_data && (
                          <div className="rounded-xl border border-gray-100 bg-gray-50/60 overflow-hidden">
                            <SummaryTable
                              columns={msg.summary_table.columns}
                              rows={msg.summary_table.rows}
                            />
                          </div>
                        )}
                        {!msg.streaming && (
                          <div className="border-t border-gray-100 pt-2.5 flex flex-wrap items-center gap-3">
                            {msg.generated_code !== undefined && (
                              <CodeTrace
                                generatedCode={msg.generated_code}
                                reasoningTrace={msg.reasoning_trace}
                              />
                            )}
                            {(msg.prompt_tokens !== undefined || msg.completion_tokens !== undefined) && (
                              <TokenCost
                                promptTokens={msg.prompt_tokens}
                                completionTokens={msg.completion_tokens}
                                costUsd={msg.cost_usd}
                              />
                            )}
                            {msg.query_id && sessionId && (
                              <ExportButton sessionId={sessionId} queryId={msg.query_id} />
                            )}
                          </div>
                        )}
                        {!msg.streaming && msg.suggestions && msg.suggestions.length > 0 && (
                          <div className="pt-2 flex flex-col gap-1.5">
                            <p className="text-[11px] font-medium text-gray-400 uppercase tracking-wide">Suggested follow-ups</p>
                            <div className="flex flex-wrap gap-1.5">
                              {msg.suggestions.map((q, i) => (
                                <button
                                  key={i}
                                  onClick={() => onSuggestionSelect?.(q)}
                                  disabled={streaming}
                                  className="text-xs px-3 py-1.5 rounded-full border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 hover:border-blue-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-left"
                                >
                                  {q}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="shrink-0 bg-white border-t border-gray-200 p-4 space-y-2">
        {datasets && datasets.length > 1 && (
          <div className="flex flex-wrap gap-1.5 items-center">
            <span className="text-[11px] font-medium text-gray-400 uppercase tracking-wide mr-1">Datasets:</span>
            {datasets.map(d => {
              const active = selectedDatasetIds?.has(d.dataset_id) ?? true
              return (
                <button
                  key={d.dataset_id}
                  onClick={() => onDatasetToggle?.(d.dataset_id)}
                  className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                    active
                      ? 'bg-violet-600 text-white border-violet-600 hover:bg-violet-700'
                      : 'bg-white text-gray-500 border-gray-300 hover:border-gray-400'
                  }`}
                >
                  {d.filename}
                </button>
              )
            })}
          </div>
        )}
        <div className="flex gap-2 items-end">
          <textarea
            ref={inputRef}
            rows={2}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={streaming}
            placeholder={streaming ? 'Waiting for answer…' : 'Ask a question about your data…'}
            className="flex-1 resize-none rounded-2xl border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50 disabled:bg-gray-50"
          />
          <button
            onClick={handleSend}
            disabled={streaming || !input.trim()}
            className="shrink-0 h-10 px-4 rounded-xl bg-blue-600 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center justify-center gap-2"
          >
            {streaming ? (
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              <SendIcon />
            )}
          </button>
        </div>
      </div>  {/* end input area */}
    </div>
  )
}
