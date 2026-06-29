interface Props {
  questions: string[]
  onSelect: (question: string) => void
  disabled?: boolean
}

export function StarterQuestions({ questions, onSelect, disabled }: Props) {
  if (questions.length === 0) return null
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Suggested questions</p>
      <div className="flex flex-col gap-1.5">
        {questions.map((q, i) => (
          <button
            key={i}
            onClick={() => !disabled && onSelect(q)}
            disabled={disabled}
            className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-left text-xs text-blue-700 hover:bg-blue-100 hover:border-blue-300 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}
