interface Props {
  questions: string[]
  onSelect: (question: string) => void
  disabled?: boolean
}

function ArrowIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="currentColor"
      className="w-3 h-3 shrink-0"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M2.75 8a.75.75 0 0 1 .75-.75h7.44L8.72 5.03a.75.75 0 0 1 1.06-1.06l3.5 3.5a.75.75 0 0 1 0 1.06l-3.5 3.5a.75.75 0 1 1-1.06-1.06l2.22-2.22H3.5A.75.75 0 0 1 2.75 8Z"
        clipRule="evenodd"
      />
    </svg>
  )
}

export function StarterQuestions({ questions, onSelect, disabled }: Props) {
  if (questions.length === 0) return null
  return (
    <div className="space-y-1.5">
      <p className="text-[11px] font-semibold text-gray-400 uppercase tracking-widest">Suggested questions</p>
      <div className="flex flex-col gap-1.5">
        {questions.map((q, i) => (
          <button
            key={i}
            onClick={() => !disabled && onSelect(q)}
            disabled={disabled}
            className="w-full text-left text-xs text-gray-600 hover:text-gray-900 bg-white border border-gray-200 hover:border-blue-300 hover:bg-blue-50/40 rounded-xl px-3 py-2.5 transition-all shadow-sm disabled:opacity-40 flex items-center gap-2"
          >
            <ArrowIcon />
            <span>{q}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
