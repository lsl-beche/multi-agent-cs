<!--
  ═══════════════════════════════════════════════════════════
  茗韵茶庄商城 · 收货地址管理页（AddressView.vue）
  ───────────────────────────────────────────────────────────
  职责说明：
    用户收货地址的增删改管理，包含：
      1. 地址列表展示（收货人/电话/详细地址，默认地址高亮 + 标签）；
      2. 新增地址（openDialog(null)）与编辑地址（openDialog(addr)）
         共用同一个 el-dialog 表单（编辑时回填数据）；
      3. 表单校验：收货人/手机号/省市区/详细地址均必填；
      4. 保存时按 editId 判断走 createAddress 或 updateAddress；
      5. 删除地址（handleDelete）带二次确认；
      6. 组件挂载即拉取地址列表（模块顶层直接调用 fetchList）。
  ═══════════════════════════════════════════════════════════
-->
<template>
  <div class="shop-container address-page">
    <h2 class="page-title">收货地址</h2>

    <!-- 地址列表：加载中显示遮罩 -->
    <div v-loading="loading">
      <div class="address-list">
        <!-- 每张地址卡片：默认地址加金色边框高亮 -->
        <div v-for="addr in addresses" :key="addr.id" class="address-card" :class="{ 'is-default': addr.is_default }">
          <div class="addr-main">
            <div class="addr-header">
              <span class="addr-receiver">{{ addr.receiver_name }}</span>
              <span class="addr-phone">{{ addr.receiver_phone }}</span>
              <el-tag v-if="addr.is_default" type="primary" size="small" effect="plain">默认</el-tag>
            </div>
            <p class="addr-text">{{ addr.province }}{{ addr.city }}{{ addr.district }} {{ addr.detail }}</p>
          </div>
          <!-- 操作：编辑（回填表单）/ 删除（二次确认） -->
          <div class="addr-actions">
            <el-button type="primary" link @click="openDialog(addr)">编辑</el-button>
            <el-button type="danger" link @click="handleDelete(addr.id)">删除</el-button>
          </div>
        </div>
        <!-- 空状态：无地址 -->
        <el-empty v-if="addresses.length === 0" description="暂无收货地址" />
      </div>

      <!-- 新增地址入口 -->
      <div class="add-btn-wrap">
        <el-button type="primary" class="add-btn" @click="openDialog(null)">+ 新增地址</el-button>
      </div>
    </div>

    <!-- 新增/编辑共用弹窗：标题按编辑态切换 -->
    <el-dialog v-model="dialogVisible" :title="editId ? '编辑地址' : '新增地址'" width="520px" class="addr-dialog">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <!-- 收货人 -->
        <el-form-item label="收货人" prop="receiver_name">
          <el-input v-model="form.receiver_name" placeholder="请输入收货人姓名" />
        </el-form-item>
        <!-- 手机号 -->
        <el-form-item label="手机号" prop="receiver_phone">
          <el-input v-model="form.receiver_phone" placeholder="请输入手机号" />
        </el-form-item>
        <!-- 所在地区：省 / 市 / 区 三列栅格 -->
        <el-form-item label="所在地区" prop="province">
          <el-row :gutter="8">
            <el-col :span="8"><el-input v-model="form.province" placeholder="省" /></el-col>
            <el-col :span="8"><el-input v-model="form.city" placeholder="市" /></el-col>
            <el-col :span="8"><el-input v-model="form.district" placeholder="区" /></el-col>
          </el-row>
        </el-form-item>
        <!-- 详细地址 -->
        <el-form-item label="详细地址" prop="detail">
          <el-input v-model="form.detail" type="textarea" :rows="2" placeholder="街道、门牌号等" />
        </el-form-item>
        <!-- 默认地址开关 -->
        <el-form-item>
          <el-checkbox v-model="form.is_default">设为默认地址</el-checkbox>
        </el-form-item>
      </el-form>
      <!-- 弹窗底部操作 -->
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
// ── 依赖引入 ──
import { ref, reactive } from 'vue' // Vue 响应式
import { getAddresses, createAddress, updateAddress, deleteAddress, type Address } from '@/api/user' // 地址 CRUD API 与类型
import { ElMessage, ElMessageBox } from 'element-plus' // 消息提示与确认框

// ── 状态定义 ──
const addresses = ref<Address[]>([]) // 地址列表
const loading = ref(false) // 列表加载中标记
const dialogVisible = ref(false) // 新增/编辑弹窗显隐
const submitting = ref(false) // 保存请求中标记
const editId = ref<number | null>(null) // 当前编辑的地址 ID（null 表示新增）
const formRef = ref() // 表单组件引用（用于 validate 校验）

// 地址表单数据（新增/编辑共用）
const form = reactive({
  receiver_name: '', receiver_phone: '',
  province: '', city: '', district: '', detail: '',
  is_default: false,
})

// 表单校验规则：收货人/手机号/省/市/区/详细地址均必填（失焦校验）
const rules = {
  receiver_name: [{ required: true, message: '请输入收货人', trigger: 'blur' }],
  receiver_phone: [{ required: true, message: '请输入手机号', trigger: 'blur' }],
  province: [{ required: true, message: '请输入省份', trigger: 'blur' }],
  city: [{ required: true, message: '请输入城市', trigger: 'blur' }],
  district: [{ required: true, message: '请输入区/县', trigger: 'blur' }],
  detail: [{ required: true, message: '请输入详细地址', trigger: 'blur' }],
}

// ── 拉取地址列表 ──
// 作用：请求用户地址列表并写入响应式数据
// 参数：无；返回值：Promise<void>
async function fetchList() {
  loading.value = true
  try {
    const res = await getAddresses() // 请求地址列表
    addresses.value = res.data.data || []
  } catch { addresses.value = [] } finally { loading.value = false } // 失败置空；最终复位 loading
}

// ── 打开新增/编辑弹窗 ──
// 作用：编辑时回填选中地址到表单并记录 editId；新增时清空表单；
//       最后打开弹窗
// 参数：addr —— 要编辑的地址对象，传 null 表示新增；返回值：无
function openDialog(addr: Address | null) {
  if (addr) { // 编辑：回填数据
    editId.value = addr.id
    Object.assign(form, {
      receiver_name: addr.receiver_name,
      receiver_phone: addr.receiver_phone,
      province: addr.province,
      city: addr.city,
      district: addr.district,
      detail: addr.detail,
      is_default: addr.is_default,
    })
  } else { // 新增：清空表单
    editId.value = null
    Object.assign(form, { receiver_name: '', receiver_phone: '', province: '', city: '', district: '', detail: '', is_default: false })
  }
  dialogVisible.value = true // 打开弹窗
}

// ── 保存地址 ──
// 作用：校验表单 → 按 editId 判断调用 updateAddress（编辑）或
//       createAddress（新增）→ 成功后关闭弹窗并刷新列表
// 参数：无；返回值：Promise<void>
async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false) // 校验失败返回 false
  if (!valid) return
  submitting.value = true // 进入提交中状态
  try {
    if (editId.value) { // 编辑：调用更新接口
      await updateAddress(editId.value, { ...form })
      ElMessage.success('更新成功')
    } else { // 新增：调用创建接口
      await createAddress({ ...form })
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false // 关闭弹窗
    await fetchList() // 刷新列表
  } catch { /* */ } finally { submitting.value = false } // 失败提示由拦截器统一处理；最终复位 submitting
}

// ── 删除地址 ──
// 作用：弹出二次确认框，确认后调用 deleteAddress 删除并刷新列表
// 参数：id —— 地址 ID；返回值：Promise<void>
async function handleDelete(id: number) {
  await ElMessageBox.confirm('确定删除该地址？', '提示', { type: 'warning' }) // 二次确认（取消则抛错中止）
  await deleteAddress(id) // 调用删除接口
  ElMessage.success('已删除')
  fetchList() // 刷新列表
}

// ── 组件初始化：挂载即拉取地址列表 ──
fetchList()
</script>

<style scoped>
/* ── 页面容器 ── */
.address-page { padding: 30px 20px 50px; }

/* ── 地址卡片：左右分布，默认地址金色边框高亮 ── */
.address-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
  padding: 18px 24px;
  border-radius: 12px;
  margin-bottom: 12px;
  border: 2px solid transparent;
  transition: border-color 0.2s;
  box-shadow: 0 2px 12px rgba(61, 50, 39, 0.04);
}

/* 默认地址：金色边框 + 浅金底 */
.address-card.is-default { border-color: #b08d57; background: #fdfaf5; }

/* 地址头部：姓名 + 电话 + 默认标签 */
.addr-header { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; }
.addr-receiver { font-weight: 600; font-size: 16px; color: #2c2a26; }
.addr-phone { color: #6b6257; }
.addr-text { color: #6b6257; font-size: 13px; }

/* 右侧操作按钮区 */
.addr-actions { display: flex; gap: 8px; flex-shrink: 0; }

/* ── 新增地址按钮 ── */
.add-btn-wrap { margin-top: 16px; }
.add-btn { background: #3f5d4a !important; border-color: #3f5d4a !important; border-radius: 8px !important; font-size: 14px !important; }
</style>
