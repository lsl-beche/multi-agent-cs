<!--
 * ============================================================
 * 模块说明：AI Agent 平台页面
 * 职责：
 *   - 展示 Agent 运行时统计（trace/节点/工具/LLM/错误率/P95）
 *   - 工具市场：展示工具目录、权限/风险，支持启用/停用
 *   - Agent Trace：查看最近运行、节点、工具、LLM 调用明细
 * ============================================================
 -->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getAgentStats,
  getAgentTools,
  getAgentTraces,
  getAgentTraceDetail,
  setAgentToolState,
  type AgentStats,
  type AgentTool,
  type AgentTrace,
  type AgentTraceDetail,
} from '@/api/agents'

const stats = ref<AgentStats | null>(null)
const tools = ref<AgentTool[]>([])
const traces = ref<AgentTrace[]>([])
const selectedTrace = ref<AgentTraceDetail | null>(null)
const loading = ref(false)
const detailVisible = ref(false)

async function loadAll() {
  loading.value = true
  try {
    const [s, t, r] = await Promise.all([
      getAgentStats(),
      getAgentTools(),
      getAgentTraces(50),
    ])
    stats.value = s.data
    tools.value = t.data || []
    traces.value = r.data || []
  } finally {
    loading.value = false
  }
}

async function toggleTool(tool: AgentTool, enabled: boolean) {
  const res = await setAgentToolState(tool.name, enabled)
  if (res.code === 0) {
    tool.enabled = enabled
    ElMessage.success(`工具「${tool.name}」已${enabled ? '启用' : '停用'}`)
  }
}

function handleToolToggle(tool: AgentTool, value: string | number | boolean) {
  return toggleTool(tool, value === true || value === 'true')
}

async function openTrace(runId: string) {
  const res = await getAgentTraceDetail(runId)
  if (res.code === 0) {
    selectedTrace.value = res.data
    detailVisible.value = true
  }
}

function statusType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'success') return 'success'
  if (status === 'running') return 'warning'
  if (status === 'error' || status === 'fallback') return 'danger'
  return 'info'
}

onMounted(loadAll)
</script>

<template>
  <div class="page-container" v-loading="loading">
    <div class="page-head">
      <h3 style="margin: 0">AI Agent 平台</h3>
      <el-button type="primary" plain @click="loadAll">刷新</el-button>
    </div>

    <div class="stat-cards">
      <div class="stat-card"><div class="label">运行 Trace</div><div class="value">{{ stats?.traces || 0 }}</div></div>
      <div class="stat-card"><div class="label">节点执行</div><div class="value">{{ stats?.nodes || 0 }}</div></div>
      <div class="stat-card"><div class="label">工具调用</div><div class="value">{{ stats?.tools || 0 }}</div></div>
      <div class="stat-card"><div class="label">LLM 调用</div><div class="value">{{ stats?.llm_calls_trace || 0 }}</div></div>
      <div class="stat-card"><div class="label">错误率</div><div class="value">{{ stats?.error_rate || 0 }}%</div></div>
      <div class="stat-card"><div class="label">P95(ms)</div><div class="value">{{ stats?.p95_duration_ms || 0 }}</div></div>
    </div>

    <el-card shadow="never" class="block-card">
      <template #header><b>工具市场</b></template>
      <el-table :data="tools" stripe>
        <el-table-column prop="name" label="工具名" min-width="150" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="120" />
        <el-table-column prop="description" label="描述" min-width="260" show-overflow-tooltip />
        <el-table-column label="权限" width="90">
          <template #default="{ row }">
            <el-tag :type="row.read_only ? 'info' : 'warning'">{{ row.read_only ? '只读' : '写操作' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="风险" width="90">
          <template #default="{ row }">
            <el-tag :type="row.risk === 'write' ? 'danger' : 'success'">{{ row.risk }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="100">
          <template #default="{ row }">
            <el-switch :model-value="row.enabled" @change="handleToolToggle(row, $event)" />
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="block-card">
      <template #header><b>Agent 运行 Trace</b></template>
      <el-table :data="traces" stripe>
        <el-table-column prop="run_id" label="Run ID" width="170" show-overflow-tooltip />
        <el-table-column prop="message" label="用户问题" min-width="240" show-overflow-tooltip />
        <el-table-column prop="intent" label="意图" width="130" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="duration_ms" label="耗时(ms)" width="100" />
        <el-table-column prop="nodes" label="节点" width="70" />
        <el-table-column prop="tools" label="工具" width="70" />
        <el-table-column prop="llm_calls" label="LLM" width="70" />
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button link type="primary" @click="openTrace(row.run_id)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="detailVisible" title="Trace 详情" size="55%">
      <template v-if="selectedTrace">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="Run ID">{{ selectedTrace.run_id }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ selectedTrace.status }}</el-descriptions-item>
          <el-descriptions-item label="用户">{{ selectedTrace.user_id }}</el-descriptions-item>
          <el-descriptions-item label="会话">{{ selectedTrace.session_id }}</el-descriptions-item>
          <el-descriptions-item label="问题" :span="2">{{ selectedTrace.message }}</el-descriptions-item>
          <el-descriptions-item label="最终回答" :span="2">{{ selectedTrace.answer }}</el-descriptions-item>
        </el-descriptions>
        <h4>节点执行</h4>
        <pre class="trace-block">{{ JSON.stringify(selectedTrace.nodes, null, 2) }}</pre>
        <h4>工具调用</h4>
        <pre class="trace-block">{{ JSON.stringify(selectedTrace.tools, null, 2) }}</pre>
        <h4>LLM 调用</h4>
        <pre class="trace-block">{{ JSON.stringify(selectedTrace.llm_calls, null, 2) }}</pre>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.stat-cards {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.stat-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}
.stat-card .label { color: #909399; font-size: 13px; }
.stat-card .value { margin-top: 8px; font-size: 24px; font-weight: 700; color: #303133; }
.block-card { margin-bottom: 16px; }
.trace-block {
  max-height: 260px;
  overflow: auto;
  background: #f5f7fa;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  color: #606266;
}
</style>
