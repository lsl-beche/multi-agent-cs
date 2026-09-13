/**
 * Agent 平台 API
 *
 * 文件作用：封装后台管理系统「AI Agent 平台」接口：
 *   - 人工智能工具市场：工具目录、启用/停用
 *   - Agent 运行 trace 列表/详情
 *   - Agent 运行时统计
 */
import api, { type ApiResponse } from './index'

/** 工具市场条目 */
export interface AgentTool {
  name: string
  description: string
  category: string
  read_only: boolean
  risk: string
  enabled: boolean
  args: string[]
}

/** Agent trace 概览 */
export interface AgentTrace {
  run_id: string
  session_id: string
  user_id: string
  message: string
  status: string
  intent: string
  need_human: boolean
  duration_ms: number
  started_at?: number
  nodes: number
  tools: number
  llm_calls: number
}

/** Agent trace 详情 */
export interface AgentTraceDetail extends Omit<AgentTrace, 'nodes' | 'tools' | 'llm_calls'> {
  finished_at?: number | null
  answer: string
  error: string
  nodes: Array<{
    node: string
    status: string
    duration_ms: number
    remark: string
    ts: number
  }>
  tools: Array<{
    tool: string
    args_summary: string
    result_summary: string
    status: string
    duration_ms: number
    ts: number
  }>
  llm_calls: Array<{
    task: string
    duration_ms: number
    tokens: number
    tier: string
    ts: number
  }>
}

/** Agent 运行时统计 */
export interface AgentStats {
  llm_calls: number
  tool_calls: number
  handoffs: number
  active_chats: number
  traces: number
  nodes: number
  tools: number
  llm_calls_trace: number
  errors: number
  error_rate: number
  avg_duration_ms: number
  p95_duration_ms: number
}

export const getAgentStats = () =>
  api.get<ApiResponse<AgentStats>>('/admin/agents/stats')

export const getAgentTools = () =>
  api.get<ApiResponse<AgentTool[]>>('/admin/agents/tools')

export const setAgentToolState = (name: string, enabled: boolean) =>
  api.put<ApiResponse<{ name: string; enabled: boolean }>>(
    `/admin/agents/tools/${encodeURIComponent(name)}/state`,
    { enabled },
  )

export const getAgentTraces = (limit = 50) =>
  api.get<ApiResponse<AgentTrace[]>>('/admin/agents/traces', { params: { limit } })

export const getAgentTraceDetail = (runId: string) =>
  api.get<ApiResponse<AgentTraceDetail>>(`/admin/agents/traces/${runId}`)
