'use client'
import { CSSProperties } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  LineChart, Line,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import { ChartData } from '@/lib/types'

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16']

const LEGEND_STYLE: CSSProperties = {
  border: '1px solid #e5e7eb',
  borderRadius: '8px',
  padding: '6px 10px',
  background: '#fff',
  fontSize: 11,
}

interface Props {
  chart: ChartData
}

export function ChartView({ chart }: Props) {
  const { chart_type, x_key, y_key, data } = chart

  // Truncate long labels for axis display
  const tickFormatter = (val: string) =>
    typeof val === 'string' && val.length > 14 ? val.slice(0, 13) + '…' : val

  if (chart_type === 'pie') {
    return (
      <div className="w-full">
        <p className="text-[11px] font-medium text-gray-400 uppercase tracking-wide mb-1 px-3 pt-3">
          {chart_type} chart
        </p>
        <div className="w-full h-64">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey={y_key}
                nameKey={x_key}
                cx="50%"
                cy="50%"
                outerRadius={88}
              >
                {data.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(val) => [val, y_key]} />
              <Legend
                formatter={(val) => tickFormatter(String(val))}
                wrapperStyle={LEGEND_STYLE}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    )
  }

  if (chart_type === 'line') {
    return (
      <div className="w-full">
        <p className="text-[11px] font-medium text-gray-400 uppercase tracking-wide mb-1 px-3 pt-3">
          {chart_type} chart
        </p>
        <div className="w-full h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey={x_key} tick={{ fontSize: 11 }} tickFormatter={tickFormatter} />
              <YAxis tick={{ fontSize: 11 }} width={48} />
              <Tooltip />
              <Legend wrapperStyle={LEGEND_STYLE} />
              <Line type="monotone" dataKey={y_key} stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    )
  }

  // Default: bar
  return (
    <div className="w-full">
      <p className="text-[11px] font-medium text-gray-400 uppercase tracking-wide mb-1 px-3 pt-3">
        {chart_type} chart
      </p>
      <div className="w-full h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey={x_key} tick={{ fontSize: 11 }} tickFormatter={tickFormatter} />
            <YAxis tick={{ fontSize: 11 }} width={48} />
            <Tooltip />
            <Legend wrapperStyle={LEGEND_STYLE} />
            <Bar dataKey={y_key} radius={[3, 3, 0, 0]}>
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
