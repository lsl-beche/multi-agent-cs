<!--
 * ============================================================
 * 模块说明：评价管理页面（views/reviews/ReviewsView.vue）
 *
 * 职责：
 *   - 评价列表：按审核状态筛选分页展示
 *   - 评价审核：待审核评价可执行通过 / 驳回操作
 *   - 商家回复：对评价填写并提交商家回复
 * ============================================================
 -->
<script setup lang="ts">
// Vue 响应式工具与生命周期钩子
import { ref, reactive, onMounted } from 'vue'
// Element Plus 消息提示
import { ElMessage } from 'element-plus'
// 评价模块相关 API：列表/审核通过/驳回/回复及数据类型
import { getReviews, approveReview, rejectReview, replyReview, type ReviewItem } from '@/api/reviews'

// 列表加载状态（表格 loading 遮罩）
const loading = ref(false)
// 评价列表数据
const list = ref<ReviewItem[]>([])
// 评价总条数（分页用）
const total = ref(0)
// 列表筛选与分页参数：审核状态、商品 ID（预留）、页码、每页条数
const search = reactive({ status: '', product_id: undefined as number | undefined, page: 1, page_size: 20 })

/**
 * 拉取评价列表（异步）
 * 按当前筛选条件请求分页数据，写入 list 与 total
 */
async function fetchList() {
  loading.value = true
  const res = await getReviews(search)
  list.value = res.data || []
  total.value = res.total
  loading.value = false
}

// 商家回复弹窗显示/隐藏
const replyVisible = ref(false)
// 回复表单：评价 ID、回复内容
const replyForm = reactive({ review_id: 0, reply: '' })
/**
 * 打开商家回复弹窗
 * 将行数据的评价 ID 与已有回复（若有）回填到表单
 * @param row 表格当前行的评价数据
 */
function openReply(row: ReviewItem) { replyForm.review_id = row.id; replyForm.reply = row.reply || ''; replyVisible.value = true }
/**
 * 提交商家回复（异步）
 * 调用回复接口，成功后提示、关闭弹窗并刷新列表
 */
async function handleReply() {
  await replyReview(replyForm.review_id, { reply: replyForm.reply })
  ElMessage.success('回复成功')
  replyVisible.value = false
  fetchList()
}

/**
 * 审核通过评价（异步）：仅待审核评价可操作
 * @param id 评价 ID
 */
async function handleApprove(id: number) { await approveReview(id); ElMessage.success('审核通过'); fetchList() }
/**
 * 驳回评价（异步）：仅待审核评价可操作
 * @param id 评价 ID
 */
async function handleReject(id: number) { await rejectReview(id); ElMessage.success('已驳回'); fetchList() }

// 页面挂载：初始化加载评价列表
onMounted(fetchList)
</script>

<template>
  <!-- 页面容器（通用白底卡片样式） -->
  <div class="page-container">
    <!-- 工具栏：审核状态筛选 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <!-- 审核状态筛选：待审核/已通过/已驳回 -->
        <el-select v-model="search.status" placeholder="审核状态" clearable style="width:130px" @change="fetchList">
          <el-option label="待审核" value="pending" /><el-option label="已通过" value="approved" /><el-option label="已驳回" value="rejected" />
        </el-select>
      </div>
    </div>

    <!-- 评价列表表格：评分/内容/回复/状态/时间 -->
    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="product_id" label="商品ID" width="90" />
      <!-- 星级评分（只读展示，显示分值） -->
      <el-table-column label="评分" width="80"><template #default="{row}"><el-rate :model-value="row.rating" disabled show-score text-color="#ff9900" /></template></el-table-column>
      <!-- 评价内容（过长时省略号展示） -->
      <el-table-column prop="content" label="内容" min-width="200" show-overflow-tooltip />
      <!-- 商家回复内容（未回复显示 -） -->
      <el-table-column prop="reply" label="回复" min-width="140" show-overflow-tooltip><template #default="{row}">{{ row.reply || '-' }}</template></el-table-column>
      <!-- 审核状态标签：已通过绿/已驳回红/待审核黄 -->
      <el-table-column label="状态" width="90"><template #default="{row}"><el-tag :type="row.status==='approved'?'success':row.status==='rejected'?'danger':'warning'">{{ row.status==='approved'?'已通过':row.status==='rejected'?'已驳回':'待审核' }}</el-tag></template></el-table-column>
      <!-- 评价时间（格式化去掉 T） -->
      <el-table-column label="时间" width="170"><template #default="{row}">{{ row.created_at?.slice(0,19).replace('T',' ') }}</template></el-table-column>
      <!-- 行操作：待审核评价可通过/驳回，所有评价可回复 -->
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <!-- 审核通过（仅待审核） -->
          <el-button v-if="row.status==='pending'" text type="success" size="small" @click="handleApprove(row.id)">通过</el-button>
          <!-- 驳回评价（仅待审核） -->
          <el-button v-if="row.status==='pending'" text type="danger" size="small" @click="handleReject(row.id)">驳回</el-button>
          <!-- 商家回复 -->
          <el-button text type="primary" size="small" @click="openReply(row)">回复</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页器：切换页码触发重新查询 -->
    <el-pagination v-model:current-page="search.page" :total="total" :page-size="20" layout="total,prev,pager,next" style="margin-top:16px;justify-content:flex-end" @change="fetchList" />

    <!-- 回复弹窗：填写商家回复内容 -->
    <el-dialog title="商家回复" v-model="replyVisible" width="500px">
      <el-form :model="replyForm" label-width="80px">
        <!-- 回复内容多行输入 -->
        <el-form-item label="回复内容"><el-input v-model="replyForm.reply" type="textarea" :rows="4" /></el-form-item>
      </el-form>
      <!-- 弹窗底部按钮：取消 / 保存 -->
      <template #footer><el-button @click="replyVisible=false">取消</el-button><el-button type="primary" @click="handleReply">保存</el-button></template>
    </el-dialog>
  </div>
</template>
