'use client'
import { useState } from 'react'

interface Props {
  generatedCode?: string    // empty string = describe path; undefined = not yet received
  reasoningTrace?: string
}

export function CodeTrace({ generatedCode, reasoningTrace }: Props) {
  const [open, setOpen] = useState(false)

  // Not yet received (still streaming) — don't render
  if (generatedCode === undefined) return null

  const isDescribePath = !generatedCode  // empty string = describe path

  if (isDescribePath) {
    return (
      <div className="text-xs text-gray-400 italic">
        Answered from dataset profile — no code ran.
      </div>
    )
  }

  return (
    <div className="text-xs">
      <button
        onClick={() => setOpen(o => !o)}
        className="text-gray-500 hover:text-gray-700 transition font-medium flex items-center gap-1"
      >
        <span className="text-gray-400">{open ? '▾' : '▸'}</span>
        {open ? 'Hide code' : 'Show code'}
      </button>
      {open && (
        <div className="mt-1.5 space-y-1.5">
          {reasoningTrace && (
            <p className="text-gray-500 italic leading-relaxed">{reasoningTrace}</p>
          )}
          <pre className="overflow-x-auto rounded-lg bg-gray-900 px-3 py-2.5 text-green-300 text-[11px] leading-relaxed whitespace-pre">
            {generatedCode}
          </pre>
        </div>
      )}
    </div>
  )
}
