'use client'

interface Props {
  promptTokens?: number
  completionTokens?: number
  costUsd?: number
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
      className="inline-flex items-center gap-1 rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-[11px] text-gray-500"
      title={`Input: ${promptTokens ?? 0} tokens · Output: ${completionTokens ?? 0} tokens`}
    >
      <span className="text-gray-400">⚡</span>
      {total.toLocaleString()} tokens · {costStr}
    </span>
  )
}
