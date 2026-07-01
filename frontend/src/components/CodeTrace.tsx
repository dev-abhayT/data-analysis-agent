'use client'
import { useState } from 'react'

interface Props {
  generatedCode?: string    // empty string = describe path; undefined = not yet received
  reasoningTrace?: string
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="currentColor"
      className={`w-3 h-3 transition-transform duration-150 ${open ? 'rotate-90' : ''}`}
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M6.22 4.22a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1 0 1.06l-3.25 3.25a.75.75 0 0 1-1.06-1.06L9.19 8 6.22 5.03a.75.75 0 0 1 0-1.06Z"
        clipRule="evenodd"
      />
    </svg>
  )
}

function InfoIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="currentColor"
      className="w-3 h-3"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M15 8A7 7 0 1 1 1 8a7 7 0 0 1 14 0ZM9 5a1 1 0 1 1-2 0 1 1 0 0 1 2 0ZM6.75 8a.75.75 0 0 0 0 1.5h.75v1.75a.75.75 0 0 0 1.5 0V8.75A.75.75 0 0 0 8.25 8h-1.5Z"
        clipRule="evenodd"
      />
    </svg>
  )
}

export function CodeTrace({ generatedCode, reasoningTrace }: Props) {
  const [open, setOpen] = useState(false)

  // Not yet received (still streaming) — don't render
  if (generatedCode === undefined) return null

  const isDescribePath = !generatedCode  // empty string = describe path

  if (isDescribePath) {
    return (
      <span className="text-xs text-gray-400 italic flex items-center gap-1">
        <InfoIcon />
        Answered from dataset profile — no code ran.
      </span>
    )
  }

  return (
    <div className="text-xs w-full">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors"
      >
        <ChevronIcon open={open} />
        {open ? 'Hide code' : 'Show code'}
      </button>
      {open && (
        <div className="mt-1.5 space-y-1.5">
          {reasoningTrace && (
            <p className="text-xs text-gray-500 italic bg-gray-50 rounded-lg px-3 py-2 border border-gray-100 leading-relaxed">
              {reasoningTrace}
            </p>
          )}
          <pre className="overflow-x-auto rounded-xl bg-gray-950 px-3 py-2.5 text-emerald-300 text-[11.5px] leading-5 whitespace-pre">
            {generatedCode}
          </pre>
        </div>
      )}
    </div>
  )
}
