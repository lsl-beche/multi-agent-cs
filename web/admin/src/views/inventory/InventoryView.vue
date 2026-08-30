<!--
 * ============================================================
 * 模块说明：库存管理页面（views/inventory/InventoryView.vue）
 *
 * 职责：
 *   - 库存列表：关键词（SKU/商品名）搜索、仅看预警开关、分页展示
 *   - 库存调整：通过弹窗录入变动数量（正为入库、负为出库）与原因
 *   - 库存流水：以时间线形式展示某个 SKU 的历史变动记录
 *
 * 说明：可用库存 quantity 小于等于安全库存 safety_stock 时标记为「库存不足」
 * ============================================================
 -->
<script setup lang="ts">
// Vue 响应式工具与生命周期钩子
import { ref, reactive, onMounted } from 'vue'
// Element Plus 消息提示
import { ElMessage } from 'element-plus'
// 库存模块相关 API：列表/调整/流水及数据类型
import { getInventory, adjustInventory, getInventoryLogs, type InventoryItem, type InventoryLog } from '@/api/inventory'

// ── 库存列表 ──
// 列表加载状态（表格 loading 遮罩）
const loading = ref(false)
// 库存列表数据
const list = ref<InventoryItem[]>([])
// 库存总条数（分页用）
const total = ref(0)
// 列表筛选与分页参数：关键词、仅看预警开关、页码、每页条数
const search = reactive({ keyword: '', low_stock_only: false, page: 1, page_size: 20 })

/**
 * 拉取库存列表（异步）
 * 按当前筛选条件请求分页数据，写入 list 与 total
 */
async function fetchList() {
  loading.value = true
  const res = await getInventory(search)
  list.value = res.data || []
  total.value = res.total
  loading.value = false
}

// ── 调整弹窗 ──
// 库存调整弹窗显示/隐藏
const adjustVisible = ref(false)
// 调整表单：SKU ID、变动数量（正入库/负出库）、原因（默认「手动调整」）
const adjustForm = reactive({ sku_id: 0, change_qty: 0, reason: '手动调整' })
/**
 * 打开库存调整弹窗
 * 将行数据的 SKU ID 写入表单并重置变动数量为 0
 * @param row 表格当前行的库存数据
 */
function openAdjust(row: InventoryItem) { adjustForm.sku_id = row.sku_id; adjustForm.change_qty = 0; adjustVisible.value = true }
/**
 * 提交库存调整（异步）
 * 调用调整接口，成功后提示、关闭弹窗并刷新列表
 */
async function handleAdjust() {
  await adjustInventory({ ...adjustForm })
  ElMessage.success('库存已调整')
  adjustVisible.value = false
  fetchList()
}

// ── 流水弹窗 ──
// 流水弹窗显示/隐藏
const logVisible = ref(false)
// 当前 SKU 的库存流水记录
const logs = ref<InventoryLog[]>([])
// 流水总条数（当前弹窗内固定取第一页，预留分页扩展）
const logTotal = ref(0)
// 流水页码（当前固定第 1 页）
const logPage = ref(1)
/**
 * 打开库存流水弹窗（异步）
 * 按 SKU ID 拉取最新 20 条流水记录并以时间线展示
 * @param skuId SKU ID
 */
async function openLogs(skuId: number) {
  logPage.value = 1
  const res = await getInventoryLogs({ sku_id: skuId, page: 1, page_size: 20 })
  logs.value = res.data || []
  logTotal.value = res.total
  logVisible.value = true
}

// 页面挂载：初始化加载库存列表
onMounted(fetchList)
</script>

<template>
  <!-- 页面容器（通用白底卡片样式） -->
  <div class="page-container">
    <!-- 工具栏：关键词搜索 + 仅看预警开关 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <!-- 关键词搜索：SKU/商品名，输入后回车或失焦触发查询 -->
        <el-input v-model="search.keyword" placeholder="SKU/商品名" clearable style="width:200px" @change="fetchList" />
        <!-- 仅看预警开关：开启后只展示库存不足的 SKU -->
        <el-switch v-model="search.low_stock_only" active-text="仅看预警" @change="fetchList" />
      </div>
    </div>

    <!-- 库存列表表格：SKU/可用库存/锁定库存/安全库存/状态 -->
    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="sku_id" label="SKU ID" width="80" />
      <el-table-column prop="sku_code" label="SKU编码" width="140" />
      <el-table-column prop="product_name" label="商品" min-width="140" />
      <!-- 可用库存（可售数量） -->
      <el-table-column prop="quantity" label="可用库存" width="100" />
      <!-- 锁定库存（下单未支付/待发货占用的数量） -->
      <el-table-column prop="locked_quantity" label="锁定库存" width="100" />
      <!-- 安全库存（低于该值触发预警） -->
      <el-table-column prop="safety_stock" label="安全库存" width="100" />
      <!-- 库存状态：可用库存 ≤ 安全库存 → 库存不足（红），否则正常（绿） -->
      <el-table-column label="状态" width="100">
        <template #default="{row}">
          <el-tag :type="row.quantity <= row.safety_stock ? 'danger' : 'success'">
            {{ row.quantity <= row.safety_stock ? '库存不足' : '正常' }}
          </el-tag>
        </template>
      </el-table-column>
      <!-- 行操作：调整库存 / 查看流水 -->
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <!-- 打开库存调整弹窗 -->
          <el-button text type="primary" size="small" @click="openAdjust(row)">调整</el-button>
          <!-- 打开库存流水弹窗 -->
          <el-button text type="warning" size="small" @click="openLogs(row.sku_id)">流水</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页器：切换页码触发重新查询 -->
    <el-pagination v-model:current-page="search.page" :total="total" :page-size="20" layout="total,prev,pager,next" style="margin-top:16px;justify-content:flex-end" @change="fetchList" />

    <!-- 调整库存弹窗：变动数量（正入库/负出库）+ 原因 -->
    <el-dialog title="调整库存" v-model="adjustVisible" width="400px">
      <el-form :model="adjustForm" label-width="80px">
        <!-- 目标 SKU ID（只读展示） -->
        <el-form-item label="SKU"><el-tag>{{ adjustForm.sku_id }}</el-tag></el-form-item>
        <!-- 变动数量：支持 -9999 ~ 9999，正数入库、负数出库 -->
        <el-form-item label="变动数量"><el-input-number v-model="adjustForm.change_qty" :min="-9999" :max="9999" /></el-form-item>
        <!-- 调整原因 -->
        <el-form-item label="原因"><el-input v-model="adjustForm.reason" /></el-form-item>
      </el-form>
      <!-- 弹窗底部按钮：取消 / 确认调整 -->
      <template #footer><el-button @click="adjustVisible=false">取消</el-button><el-button type="primary" @click="handleAdjust">确认调整</el-button></template>
    </el-dialog>

    <!-- 流水弹窗：时间线展示库存变动记录（入库绿/出库红） -->
    <el-dialog title="库存流水" v-model="logVisible" width="650px">
      <el-timeline>
        <!-- 每条流水：原因 + 变动数量 + 变动前后库存 -->
        <el-timeline-item
          v-for="log in logs" :key="log.id"
          :timestamp="log.reason"
          :time="log.created_at?.slice(0,19)"
          :color="log.change_qty>0?'#67c23a':'#f56c6c'"
        >
          <!-- 变动数量展示：正数带 + 号；括号内为变动前后库存 -->
          {{ log.change_qty > 0 ? '+' : '' }}{{ log.change_qty }} ({{ log.before_qty }} → {{ log.after_qty }})
        </el-timeline-item>
      </el-timeline>
    </el-dialog>
  </div>
</template>
