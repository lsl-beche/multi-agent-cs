<!--
 * ============================================================
 * 模块说明：数据看板页面（views/dashboard/DashboardView.vue）
 *
 * 职责：
 *   - 展示后台核心经营指标（近 7 日订单数、销售额、商品总数、
 *     注册用户、待处理退款、支付笔数）
 *   - 基于 ECharts 绘制两个图表：
 *       ├─ 柱状图：近 7 日各状态订单数概览
 *       └─ 饼图：订单状态占比（环形图）
 *   - 页面挂载时并行请求订单/商品/用户/退款/销售汇总接口获取数据
 *
 * 依赖接口：
 *   - GET /orders （取总数）
 *   - GET /products （取总数）
 *   - GET /users （取总数）
 *   - GET /refunds （取待处理退款数）
 *   - GET /reports/sales-summary （近 7 日销售汇总）
 * ============================================================
 -->
<script setup lang="ts">
// Vue 生命周期钩子：onMounted 初始化加载数据、onUnmounted 销毁图表实例
import { ref, onMounted, onUnmounted } from 'vue'
// ECharts 图表库：用于初始化柱状图/饼图实例
import * as echarts from 'echarts'
// 以下为各业务模块的 API（此处仅使用分页查询能力，用于统计数量）
import { getOrders } from '@/api/orders'
import { getProducts } from '@/api/products'
import { getUsers } from '@/api/users'
import { getRefunds } from '@/api/payments'
import { getSalesSummary } from '@/api/reports'

/**
 * 近 7 日销售汇总数据结构（对应 /reports/sales-summary 接口返回）
 * - period:        统计周期标识（如 week）
 * - total_orders:  订单总数
 * - total_amount:  销售总额
 * - pending/confirmed/shipped/delivered/completed/cancelled: 各状态订单数
 * - paid_count:    已支付笔数
 * - paid_amount:   已支付金额
 */
interface SalesData {
  period: string
  total_orders: number
  total_amount: number
  pending: number
  confirmed: number
  shipped: number
  delivered: number
  completed: number
  cancelled: number
  paid_count: number
  paid_amount: number
}

// 顶部 6 张统计卡片的数值集合（订单数/销售额/用户/退款/商品/支付笔数）
const stats = ref({ orders: 0, amount: 0, users: 0, refunds: 0, products: 0, payments: 0 })
// 柱状图 DOM 容器引用（模板中通过 ref="barRef" 绑定）
const barRef = ref<HTMLDivElement>()
// 饼图 DOM 容器引用（模板中通过 ref="pieRef" 绑定）
const pieRef = ref<HTMLDivElement>()
// 柱状图实例（非响应式，用普通变量保存，便于销毁与 resize）
let barInstance: echarts.ECharts | null = null
// 饼图实例（非响应式，用普通变量保存，便于销毁与 resize）
let pieInstance: echarts.ECharts | null = null

/**
 * 页面挂载后的初始化逻辑（生命周期钩子 onMounted）
 * 并行请求 5 个接口获取统计数据，并初始化两个 ECharts 图表；
 * 任一步出错时打印错误日志，不影响页面其他区域展示
 */
onMounted(async () => {
  try {
    // 并行获取基础统计数据
    // 使用 Promise.all 同时发起 5 个请求：订单/商品/用户/退款/销售汇总（均只取 1 条用于获取 total）
    const [oRes, pRes, uRes, rRes, salesRes] = await Promise.all([
      getOrders({ page_size: 1 }),
      getProducts({ page_size: 1 }),
      getUsers({ page_size: 1 }),
      getRefunds({ status: 'pending', page_size: 1 }),
      getSalesSummary({ period: 'week' }),
    ])

    // 销售汇总数据（接口未返回时降级为空对象）
    const salesData: SalesData = (salesRes as any).data || {}
    // 汇总写入顶部统计卡片：优先取销售汇总字段，缺省取分页接口的 total
    stats.value = {
      orders: salesData.total_orders || oRes.total || 0,
      amount: salesData.total_amount || 0,
      users: uRes.total || 0,
      refunds: rRes.total || 0,
      products: pRes.total || 0,
      payments: salesData.paid_count || 0,
    }

    // 柱状图：各状态订单数
    // 仅当 DOM 容器已渲染时初始化，避免空引用报错
    if (barRef.value) {
      // 初始化 ECharts 实例（绑定到柱状图容器 DOM）
      barInstance = echarts.init(barRef.value)
      // 设置柱状图配置项
      barInstance.setOption({
        // 图表标题：顶部居中，小号灰字
        title: { text: '近7日订单概览', left: 'center', textStyle: { fontSize: 14, color: '#606266' } },
        // 悬浮提示：坐标轴触发（鼠标悬停显示该柱数值）
        tooltip: { trigger: 'axis' },
        // 图例：底部居中
        legend: { data: ['订单数'], bottom: 0 },
        // X 轴：订单状态分类（标签旋转 30°，防止文字重叠）
        xAxis: {
          type: 'category',
          data: ['待处理', '已确认', '已发货', '已送达', '已完成', '已取消'],
          axisLabel: { rotate: 30 },
        },
        // Y 轴：订单数量
        yAxis: { type: 'value', name: '订单数' },
        // 柱状图数据系列：取各状态订单数（无数据默认 0）
        series: [{
          name: '订单数',
          type: 'bar',
          data: [
            salesData.pending || 0,
            salesData.confirmed || 0,
            salesData.shipped || 0,
            salesData.delivered || 0,
            salesData.completed || 0,
            salesData.cancelled || 0,
          ],
          // 柱子颜色：Element Plus 主色蓝
          itemStyle: { color: '#409eff' },
          // 柱子宽度
          barWidth: 36,
        }],
        // 网格留白：左右上下边距
        grid: { left: 50, right: 30, top: 50, bottom: 60 },
      })
      // 监听窗口尺寸变化，图表自动自适应（resize）
      window.addEventListener('resize', () => barInstance?.resize())
    }

    // 饼图：订单状态占比
    // 仅当 DOM 容器已渲染时初始化
    if (pieRef.value) {
      // 初始化 ECharts 实例（绑定到饼图容器 DOM）
      pieInstance = echarts.init(pieRef.value)
      // 组装饼图数据：各状态订单数 + 对应颜色，过滤掉数量为 0 的状态
      const pieData = [
        { value: salesData.pending || 0, name: '待处理', itemStyle: { color: '#f56c6c' } },
        { value: salesData.confirmed || 0, name: '已确认', itemStyle: { color: '#409eff' } },
        { value: salesData.shipped || 0, name: '已发货', itemStyle: { color: '#e6a23c' } },
        { value: salesData.delivered || 0, name: '已送达', itemStyle: { color: '#909399' } },
        { value: salesData.completed || 0, name: '已完成', itemStyle: { color: '#67c23a' } },
        { value: salesData.cancelled || 0, name: '已取消', itemStyle: { color: '#c0c4cc' } },
      ].filter(d => d.value > 0)

      // 若所有状态订单数都为 0，添加占位项「暂无数据」，避免图表空白
      if (pieData.length === 0) {
        pieData.push({ value: 1, name: '暂无数据', itemStyle: { color: '#e4e7ed' } })
      }

      // 设置饼图配置项
      pieInstance.setOption({
        // 图表标题：顶部居中
        title: { text: '订单状态占比', left: 'center', textStyle: { fontSize: 14, color: '#606266' } },
        // 悬浮提示：显示名称、数量与百分比（{d} 为百分比）
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        // 图例：底部居中
        legend: { bottom: 0 },
        // 环形饼图系列：内半径 45%、外半径 70%，标签显示名称与百分比
        series: [{
          type: 'pie',
          radius: ['45%', '70%'],
          center: ['50%', '50%'],
          data: pieData,
          label: { show: true, formatter: '{b}\n{d}%' },
          // 高亮强调：投影效果
          emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.3)' } },
        }],
      })
      // 监听窗口尺寸变化，图表自动自适应（resize）
      window.addEventListener('resize', () => pieInstance?.resize())
    }
  } catch (e) {
    // 整体兜底：数据加载/图表初始化失败时打印错误日志，不影响页面渲染
    console.error('Dashboard load error:', e)
  }
})

/**
 * 组件卸载前的清理逻辑（生命周期钩子 onUnmounted）
 * 销毁两个 ECharts 实例，释放 DOM 与事件监听，避免内存泄漏
 */
onUnmounted(() => {
  barInstance?.dispose()
  pieInstance?.dispose()
})
</script>

<template>
  <!-- 页面容器（通用白底卡片样式） -->
  <div class="page-container">
    <!-- 顶部统计卡片区：6 个核心经营指标 -->
    <div class="stat-cards">
      <!-- 近 7 日订单数 -->
      <div class="stat-card">
        <div class="label">近7日订单数</div>
        <div class="value">{{ stats.orders }}</div>
      </div>
      <!-- 近 7 日销售额（千分位格式化显示） -->
      <div class="stat-card">
        <div class="label">近7日销售额</div>
        <div class="value">¥{{ stats.amount.toLocaleString() }}</div>
      </div>
      <!-- 商品总数 -->
      <div class="stat-card">
        <div class="label">商品总数</div>
        <div class="value">{{ stats.products }}</div>
      </div>
      <!-- 注册用户数 -->
      <div class="stat-card">
        <div class="label">注册用户</div>
        <div class="value">{{ stats.users }}</div>
      </div>
      <!-- 待处理退款数（橙色强调，提示需关注） -->
      <div class="stat-card">
        <div class="label">待处理退款</div>
        <div class="value" style="color:#e6a23c">{{ stats.refunds }}</div>
      </div>
      <!-- 支付笔数（绿色强调） -->
      <div class="stat-card">
        <div class="label">支付笔数</div>
        <div class="value" style="color:#67c23a">{{ stats.payments }}</div>
      </div>
    </div>

    <!-- 图表区：左侧柱状图（自适应宽度）+ 右侧饼图（固定 360px） -->
    <div style="display:flex;gap:20px;margin-top:16px">
      <!-- 柱状图卡片：近 7 日各状态订单数概览 -->
      <div class="chart-box" style="flex:1">
        <div ref="barRef" style="width:100%;height:360px"></div>
      </div>
      <!-- 饼图卡片：订单状态占比 -->
      <div class="chart-box" style="width:360px">
        <div ref="pieRef" style="width:100%;height:360px"></div>
      </div>
    </div>
  </div>
</template>
