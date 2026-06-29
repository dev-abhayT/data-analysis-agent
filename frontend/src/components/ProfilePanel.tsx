import { Dataset } from '@/lib/types'

interface Props {
  dataset: Dataset
  onDelete: (datasetId: string) => void
}

export function ProfilePanel({ dataset, onDelete }: Props) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm space-y-3">
      <div className="flex items-center justify-between">
        <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-semibold text-blue-700 truncate max-w-[60%]">
          {dataset.filename}
        </span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">{dataset.row_count.toLocaleString()} rows</span>
          <button
            onClick={() => onDelete(dataset.dataset_id)}
            title="Remove dataset"
            className="rounded p-1 text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
            aria-label={`Remove ${dataset.filename}`}
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
              <path fillRule="evenodd" d="M5 3.25V4H2.75a.75.75 0 0 0 0 1.5h.3l.815 8.15A1.5 1.5 0 0 0 5.357 15h5.285a1.5 1.5 0 0 0 1.493-1.35l.815-8.15h.3a.75.75 0 0 0 0-1.5H11v-.75A2.25 2.25 0 0 0 8.75 1h-1.5A2.25 2.25 0 0 0 5 3.25Zm2.25-.75a.75.75 0 0 0-.75.75V4h3v-.75a.75.75 0 0 0-.75-.75h-1.5ZM6.05 6a.75.75 0 0 1 .787.713l.275 5.5a.75.75 0 0 1-1.498.075l-.275-5.5A.75.75 0 0 1 6.05 6Zm3.9 0a.75.75 0 0 1 .712.787l-.275 5.5a.75.75 0 0 1-1.498-.075l.275-5.5a.75.75 0 0 1 .786-.711Z" clipRule="evenodd" />
            </svg>
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-gray-100">
              <th className="pb-1 text-left font-medium text-gray-500">Column</th>
              <th className="pb-1 text-left font-medium text-gray-500">Type</th>
              <th className="pb-1 text-right font-medium text-gray-500">Nulls</th>
              <th className="pb-1 text-left font-medium text-gray-500 pl-2">Samples</th>
            </tr>
          </thead>
          <tbody>
            {dataset.column_names.map(col => (
              <tr key={col} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="py-1 font-mono text-gray-800 max-w-[80px] truncate pr-1">{col}</td>
                <td className="py-1 text-gray-500">{dataset.column_types[col] ?? '?'}</td>
                <td className="py-1 text-right text-gray-400">{dataset.null_counts[col] ?? 0}</td>
                <td className="py-1 pl-2 text-gray-400 max-w-[100px] truncate">
                  {(dataset.sample_values[col] ?? []).slice(0, 3).join(', ')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
