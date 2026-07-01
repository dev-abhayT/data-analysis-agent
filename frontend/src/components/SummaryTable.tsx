interface Props {
  columns: string[]
  rows: (string | number | null)[][]
}

export function SummaryTable({ columns, rows }: Props) {
  return (
    <div className="overflow-hidden rounded-xl border border-gray-200">
      <div className="overflow-x-auto max-h-56 overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0">
            <tr className="bg-gray-800 text-gray-100">
              {columns.map(col => (
                <th
                  key={col}
                  className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide whitespace-nowrap"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr
                key={i}
                className={`${i % 2 === 0 ? 'bg-white' : 'bg-gray-50/60'} hover:bg-blue-50/40 transition-colors`}
              >
                {row.map((cell, j) => {
                  const isNum = typeof cell === 'number'
                  return (
                    <td
                      key={j}
                      className={`px-3 py-1.5 border-b border-gray-100 whitespace-nowrap ${isNum ? 'text-right tabular-nums text-gray-700' : 'text-gray-700'}`}
                    >
                      {cell === null || cell === undefined ? (
                        <span className="text-gray-300 text-xs">—</span>
                      ) : isNum ? (
                        (cell as number).toLocaleString()
                      ) : (
                        String(cell)
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
