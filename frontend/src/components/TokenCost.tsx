'use client'

interface Props {
  promptTokens?: number
  completionTokens?: number
  costUsd?: number
}

function BoltIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="currentColor"
      className="w-3 h-3 text-amber-400"
      aria-hidden="true"
    >
      <path d="M8.75 2.5a.75.75 0 0 0-1.408-.36L4.342 8H2.75a.75.75 0 0 0-.6 1.2l5 6.75A.75.75 0 0 0 8.5 15.5V10h1.75a.75.75 0 0 0 .6-1.2l-2-2.7V2.5Z" />
    </svg>
  )
}

export function TokenCost({ promptTokens, completionTokens, costUsd }: Props) {
  // Don't render if we have no token data at all
  if (promptTokens === undefined && completionTokens === undefined) return null

  const total = (promptTokens ?? 0) + (completionTokens ?? 0)

  // Format cost display
  let costStr: string
  if (costUsd !== undefined && costUsd !== null) {
    if (costUsd === 0) {
      costStr = '$0.00'
    } else if (costUsd < 0.0001) {
      costStr = '<$0.0001'
    } else {
      costStr = `~$${costUsd.toFixed(4)}`
    }
  } else {
    // Compute from tokens using Gemini 2.5 Flash pricing
    const computed = ((promptTokens ?? 0) * 0.075 + (completionTokens ?? 0) * 0.30) / 1_000_000
    if (computed === 0) {
      costStr = '$0.00'
    } else if (computed < 0.0001) {
      costStr = '<$0.0001'
    } else {
      costStr = `~$${computed.toFixed(4)}`
    }
  }

  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs text-gray-400"
      title={`Input: ${promptTokens ?? 0} tokens · Output: ${completionTokens ?? 0} tokens`}
    >
      <BoltIcon />
      {total.toLocaleString()} tokens · {costStr}
    </span>
  )
}
