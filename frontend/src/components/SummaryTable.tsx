interface Props {
  columns: string[]
  rows: (string | number | null)[][]
}

export function SummaryTable({ columns, rows }: Props) {
  return (
    <div className="mt-3 overflow-x-auto rounded-lg border border-gray-200 max-h-64">
      <table className="w-full text-xs">
        <thead className="bg-gray-50 sticky top-0">
          <tr>
            {columns.map(col => (
              <th key={col} className="px-3 py-2 text-left font-semibold text-gray-600 border-b border-gray-200 whitespace-nowrap">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}>
              {row.map((cell, j) => (
                <td key={j} className="px-3 py-1.5 text-gray-700 border-b border-gray-100 whitespace-nowrap">
                  {cell === null || cell === undefined
                    ? <span className="text-gray-300">—</span>
                    : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
