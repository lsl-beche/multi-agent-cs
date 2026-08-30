<!--
 * ============================================================
 * 模块说明：物流管理页面（views/shipments/ShipmentsView.vue）
 *
 * 职责：
 *   - 物流列表：按关键词（物流单号/订单号）/物流状态筛选，分页展示
 *   - 物流详情：收货人、地址、承运商、物流单号等信息描述
 *   - 更新物流轨迹：修改承运商与物流单号
 * ============================================================
 -->
<script setup lang="ts">
// Vue 响应式工具与生命周期钩子
import { ref, reactive, onMounted } from 'vue'
// Element Plus 消息提示
import { ElMessage } from 'element-plus'
// 物流模块相关 API：列表/更新物流信息及数据类型
import { getShipments, updateTracking, type ShipmentItem } from '@/api/shipments'

// ── 物流列表 ──
// 列表加载状态（表格 loading 遮罩）
const loading = ref(false)
// 物流列表数据
const list = ref<ShipmentItem[]>([])
// 物流总条数（分页用）
const total = ref(0)
// 列表筛选与分页参数：关键词、物流状态、页码、每页条数
const search = reactive({ keyword: '', status: '', page: 1, page_size: 20 })

/**
 * 拉取物流列表（异步）
 * 按当前筛选条件请求分页数据，写入 list 与 total
 */
async function fetchList() {
  loading.value = true
  const res = await getShipments(search)
  list.value = res.data || []
  total.value = res.total
  loading.value = false
}

// 物流状态 → 中文文案的映射
const statusMap: Record<string, string> = {
  pending: '待发货',
  shipped: '运输中',
  delivered: '已签收',
  returned: '已退回',
}
// 物流状态 → Element Plus 标签类型的映射（待发货黄/签收绿/退回灰）
const statusTag: Record<string, string> = {
  pending: 'warning',
  shipped: '',
  delivered: 'success',
  returned: 'info',
}

// ── 轨迹编辑弹窗 ──
// 更新物流信息弹窗显示/隐藏
const trackVisible = ref(false)
// 更新物流表单：物流单 ID、物流单号、承运商
const trackForm = reactive({ id: 0, tracking_no: '', carrier: '' })
/**
 * 打开更新物流信息弹窗
 * 将行数据的物流单号与承运商回填到表单
 * @param row 表格当前行的物流数据
 */
function openTrack(row: ShipmentItem) {
  trackForm.id = row.id
  trackForm.tracking_no = row.tracking_no || ''
  trackForm.carrier = row.carrier || ''
  trackVisible.value = true
}
/**
 * 提交更新物流信息（异步）
 * 调用更新接口（承运商为空时传 undefined），成功后提示、关闭弹窗并刷新列表
 */
async function handleTrack() {
  await updateTracking(trackForm.id, { tracking_no: trackForm.tracking_no, carrier: trackForm.carrier || undefined })
  ElMessage.success('物流信息已更新')
  trackVisible.value = false
  fetchList()
}

// ── 详情弹窗 ──
// 物流详情弹窗显示/隐藏
const detailVisible = ref(false)
// 当前查看的物流详情数据（null 表示未选择）
const detail = ref<ShipmentItem | null>(null)
/**
 * 打开物流详情弹窗
 * 直接使用当前行数据展示（无需额外请求）
 * @param row 表格当前行的物流数据
 */
function openDetail(row: ShipmentItem) {
  detail.value = row
  detailVisible.value = true
}

// 页面挂载：初始化加载物流列表
onMounted(fetchList)
</script>

<template>
  <!-- 页面容器（通用白底卡片样式） -->
  <div class="page-container">
    <!-- 工具栏：关键词搜索 + 物流状态筛选 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <!-- 关键词搜索：物流单号/订单号 -->
        <el-input v-model="search.keyword" placeholder="物流单号/订单号" clearable style="width:220px" @change="fetchList" />
        <!-- 物流状态筛选：待发货/运输中/已签收/已退回 -->
        <el-select v-model="search.status" placeholder="物流状态" clearable style="width:130px" @change="fetchList">
          <el-option label="待发货" value="pending" />
          <el-option label="运输中" value="shipped" />
          <el-option label="已签收" value="delivered" />
          <el-option label="已退回" value="returned" />
        </el-select>
      </div>
    </div>

    <!-- 物流列表表格：编号/订单/承运商/单号/收货信息/状态/发货时间 -->
    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="shipment_no" label="物流编号" width="160" />
      <el-table-column prop="order_id" label="订单ID" width="90" />
      <el-table-column prop="carrier" label="承运商" width="100" />
      <!-- 物流单号（未填写时展示占位文案） -->
      <el-table-column prop="tracking_no" label="物流单号" width="180">
        <template #default="{ row }">{{ row.tracking_no || '未填写' }}</template>
      </el-table-column>
      <el-table-column prop="receiver" label="收货人" width="100" />
      <el-table-column prop="receiver_phone" label="联系电话" width="130" />
      <!-- 收货地址（过长时省略号展示） -->
      <el-table-column prop="address" label="收货地址" min-width="180" show-overflow-tooltip />
      <!-- 物流状态标签 -->
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTag[row.status]">{{ statusMap[row.status] || row.status }}</el-tag>
        </template>
      </el-table-column>
      <!-- 发货时间（格式化去掉 T，无则显示 -） -->
      <el-table-column prop="shipped_at" label="发货时间" width="170">
        <template #default="{ row }">{{ row.shipped_at?.slice(0, 19).replace('T', ' ') || '-' }}</template>
      </el-table-column>
      <!-- 行操作：详情 / 更新轨迹 -->
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <!-- 查看物流详情 -->
          <el-button text type="primary" size="small" @click="openDetail(row)">详情</el-button>
          <!-- 更新承运商与物流单号 -->
          <el-button text type="warning" size="small" @click="openTrack(row)">更新轨迹</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页器：切换页码触发重新查询 -->
    <el-pagination
      v-model:current-page="search.page" :total="total" :page-size="20"
      layout="total,prev,pager,next" style="margin-top:16px;justify-content:flex-end"
      @change="fetchList"
    />

    <!-- 详情弹窗：收货人/地址/承运商/单号/状态等信息描述 -->
    <el-dialog title="物流详情" v-model="detailVisible" width="550px">
      <template v-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="物流编号">{{ detail.shipment_no }}</el-descriptions-item>
          <el-descriptions-item label="订单ID">{{ detail.order_id }}</el-descriptions-item>
          <el-descriptions-item label="承运商">{{ detail.carrier }}</el-descriptions-item>
          <el-descriptions-item label="物流单号">{{ detail.tracking_no || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTag[detail.status]">{{ statusMap[detail.status] }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="发货时间">{{ detail.shipped_at?.slice(0, 19).replace('T', ' ') || '-' }}</el-descriptions-item>
          <el-descriptions-item label="收货人">{{ detail.receiver }}</el-descriptions-item>
          <el-descriptions-item label="联系电话">{{ detail.receiver_phone }}</el-descriptions-item>
          <!-- 收货地址：跨两列展示 -->
          <el-descriptions-item label="收货地址" :span="2">{{ detail.address }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-dialog>

    <!-- 更新轨迹弹窗：选择物流公司 + 填写物流单号 -->
    <el-dialog title="更新物流信息" v-model="trackVisible" width="400px">
      <el-form :model="trackForm" label-width="80px">
        <!-- 物流公司下拉：常见快递公司 -->
        <el-form-item label="物流公司">
          <el-select v-model="trackForm.carrier" style="width:100%">
            <el-option label="顺丰速运" value="顺丰速运" />
            <el-option label="中通快递" value="中通快递" />
            <el-option label="圆通速递" value="圆通速递" />
            <el-option label="韵达快递" value="韵达快递" />
            <el-option label="京东物流" value="京东物流" />
            <el-option label="EMS" value="EMS" />
          </el-select>
        </el-form-item>
        <!-- 物流单号输入 -->
        <el-form-item label="物流单号">
          <el-input v-model="trackForm.tracking_no" placeholder="请输入物流单号" />
        </el-form-item>
      </el-form>
      <!-- 弹窗底部按钮：取消 / 确认更新 -->
      <template #footer>
        <el-button @click="trackVisible = false">取消</el-button>
        <el-button type="primary" @click="handleTrack">确认更新</el-button>
      </template>
    </el-dialog>
  </div>
</template>
