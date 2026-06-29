import { Dataset } from '@/lib/types'

interface Props {
  dataset: Dataset
}

export function ProfilePanel({ dataset }: Props) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm space-y-3">
      <div className="flex items-center justify-between">
        <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-semibold text-blue-700 truncate max-w-[60%]">
          {dataset.filename}
        </span>
        <span className="text-xs text-gray-500">{dataset.row_count.toLocaleString()} rows</span>
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
