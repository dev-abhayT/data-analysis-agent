export interface Dataset {
  dataset_id: string
  filename: string
  row_count: number
  column_names: string[]
  column_types: Record<string, string>
  null_counts: Record<string, number>
  sample_values: Record<string, string[]>
  starter_questions: string[]
}

export interface QueryResult {
  query_id: string
  question: string
  status: 'pending' | 'running' | 'clarifying' | 'completed' | 'failed'
  answer_text?: string
  summary_table_json?: { columns: string[]; rows: (string | number | null)[][] } | null
  generated_code?: string
  reasoning_trace?: string
  prompt_tokens?: number
  completion_tokens?: number
  cost_usd?: number
  created_at?: string
}

export interface SessionDetail {
  session_id: string
  created_at: string
  datasets: Dataset[]
  queries: QueryResult[]
}

export interface ChartData {
  chart_type: 'bar' | 'line' | 'pie'
  x_key: string
  y_key: string
  data: Record<string, string | number | null>[]
}

export interface ChatMessage {
  id: string
  role: 'user' | 'agent'
  content: string
  streaming?: boolean
  summary_table?: { columns: string[]; rows: (string | number | null)[][] } | null
  chart_data?: ChartData | null
  error?: string
  clarification?: string
  // Phase 2 additions:
  query_id?: string          // for export button
  generated_code?: string    // code that ran (empty string = describe path)
  reasoning_trace?: string   // reasoning from generate_code
  prompt_tokens?: number
  completion_tokens?: number
  cost_usd?: number
}
