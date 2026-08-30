<!--
 * ============================================================
 * 模块说明：客服看板页面（views/reports/ReportsView.vue）
 *
 * 职责：
 *   - 按时间周期（今日/本周/本月）切换展示客服运营数据大屏
 *   - 顶部统计卡片：总会话数、活跃会话、工单总数、待处理工单、
 *     转人工率、CSAT 满意度评分
 *   - 两个 ECharts 图表：
 *       ├─ 仪表盘（gauge）：CSAT 满意度评分（0~5 分）
 *       └─ 柱状图（bar）：会话数/工单数/待处理/转人工率 对比
 *
 * 依赖接口：
 *   - GET /reports/sales-summary （销售汇总）
 *   - GET /reports/cs-dashboard （客服数据大屏）
 * ============================================================
 -->
<script setup lang="ts">
// Vue 响应式工具与生命周期钩子（nextTick 确保 DOM 更新后再初始化图表）
import { ref, onMounted, nextTick } from 'vue'
// ECharts 图表库：初始化仪表盘与柱状图
import * as echarts from 'echarts'
// 报表模块相关 API 及数据类型
import { getSalesSummary, getCsDashboard, type SalesSummary, type CsDashboard } from '@/api/reports'

// 当前统计周期：'today'（今日）/ 'week'（本周）/ 'month'（本月），默认今日
const period = ref('today')
// 销售汇总数据（当前页面仅拉取，未直接渲染字段，预留展示）
const sales = ref<SalesSummary | null>(null)
// 客服大屏数据（驱动统计卡片与图表）
const cs = ref<CsDashboard | null>(null)

// 仪表盘 DOM 容器引用（模板中通过 ref="gaugeRef" 绑定）
const gaugeRef = ref<HTMLDivElement>()
// 柱状图 DOM 容器引用（模板中通过 ref="barRef" 绑定）
const barRef = ref<HTMLDivElement>()

/**
 * 拉取当前周期的数据并渲染图表（异步）
 * 并行请求销售汇总与客服大屏接口；
 * 数据就绪后等待 DOM 更新（nextTick），再分别初始化仪表盘与柱状图
 */
async function fetchData() {
  // 并行请求两个报表接口
  const [sRes, cRes] = await Promise.all([
    getSalesSummary(period.value),
    getCsDashboard(period.value),
  ])
  sales.value = sRes.data
  cs.value = cRes.data

  // 等待模板中图表容器渲染完成
  await nextTick()
  // 初始化 CSAT 满意度仪表盘
  if (gaugeRef.value) {
    const chart = echarts.init(gaugeRef.value)
    chart.setOption({
      series: [{
        // 仪表盘类型：半圆弧（180° ~ 0°），分值范围 0~5
        type: 'gauge',
        startAngle: 180, endAngle: 0,
        min: 0, max: 5, radius: '90%',
        // 仪表盘颜色分段：低分红、中分黄、高分绿
        axisLine: { lineStyle: { width: 16, color: [[0.6, '#f56c6c'], [0.8, '#e6a23c'], [1, '#67c23a']] } },
        // 指针样式
        pointer: { length: '60%', width: 6 },
        // 中心大号数值显示
        detail: { fontSize: 32, formatter: '{value}' },
        // 数据：取客服大屏的 CSAT 平均值（无数据默认 0）
        data: [{ value: cs.value?.csat_avg || 0, name: 'CSAT' }],
      }],
    })
  }

  // 初始化客服数据概览柱状图
  if (barRef.value) {
    const chart2 = echarts.init(barRef.value)
    chart2.setOption({
      // 悬浮提示：坐标轴触发
      tooltip: { trigger: 'axis' },
      // X 轴：四个指标分类
      xAxis: { type: 'category', data: ['会话数', '工单数', '待处理', '转人工率%'] },
      yAxis: { type: 'value' },
      // 柱状图数据系列
      series: [{
        type: 'bar',
        data: [
          cs.value?.total_conversations || 0,
          cs.value?.total_tickets || 0,
          cs.value?.pending_tickets || 0,
          cs.value?.handoff_rate || 0,
        ],
        // 柱子颜色：Element Plus 主色蓝
        itemStyle: { color: '#409eff' },
        barWidth: 32,
      }],
      // 网格留白
      grid: { left: 50, right: 20, top: 20, bottom: 30 },
    })
  }
}

/**
 * 切换统计周期
 * @param p 新的周期值（today/week/month），更新后重新拉取数据
 */
function changePeriod(p: string) { period.value = p; fetchData() }

// 页面挂载：初始化加载数据并渲染图表
onMounted(fetchData)
</script>

<template>
  <!-- 页面容器（通用白底卡片样式） -->
  <div class="page-container">
    <!-- 页面标题 -->
    <h3 style="margin-bottom:16px">CS 客服数据大屏</h3>
    <!-- 统计周期切换：今日 / 本周 / 本月 -->
    <el-radio-group v-model="period" @change="changePeriod" style="margin-bottom:20px">
      <el-radio-button value="today">今日</el-radio-button>
      <el-radio-button value="week">本周</el-radio-button>
      <el-radio-button value="month">本月</el-radio-button>
    </el-radio-group>

    <!-- 顶部统计卡片区：6 个客服核心指标 -->
    <div class="stat-cards">
      <!-- 总会话数 -->
      <div class="stat-card"><div class="label">总会话数</div><div class="value">{{ cs?.total_conversations || 0 }}</div></div>
      <!-- 当前活跃会话数 -->
      <div class="stat-card"><div class="label">活跃会话</div><div class="value">{{ cs?.active_conversations || 0 }}</div></div>
      <!-- 工单总数 -->
      <div class="stat-card"><div class="label">工单总数</div><div class="value">{{ cs?.total_tickets || 0 }}</div></div>
      <!-- 待处理工单数（橙色强调，提示需关注） -->
      <div class="stat-card"><div class="label">待处理工单</div><div class="value" style="color:#e6a23c">{{ cs?.pending_tickets || 0 }}</div></div>
      <!-- 转人工率（百分比展示） -->
      <div class="stat-card"><div class="label">转人工率</div><div class="value">{{ cs?.handoff_rate || 0 }}%</div></div>
      <!-- CSAT 满意度评分（绿色强调） -->
      <div class="stat-card"><div class="label">CSAT评分</div><div class="value" style="color:#67c23a">{{ cs?.csat_avg || 0 }}</div></div>
    </div>

    <!-- 图表区：左仪表盘（满意度）+ 右柱状图（客服数据概览） -->
    <div style="display:grid;grid-template-columns:1fr 2fr;gap:20px">
      <!-- CSAT 满意度仪表盘卡片 -->
      <div class="chart-box">
        <h4 style="text-align:center;margin-bottom:8px;color:#606266">满意度仪表盘</h4>
        <div ref="gaugeRef" style="width:100%;height:280px"></div>
      </div>
      <!-- 客服数据概览柱状图卡片 -->
      <div class="chart-box">
        <h4 style="text-align:center;margin-bottom:8px;color:#606266">客服数据概览</h4>
        <div ref="barRef" style="width:100%;height:280px"></div>
      </div>
    </div>
  </div>
</template>
