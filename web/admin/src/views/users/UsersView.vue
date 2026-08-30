<!--
 * ============================================================
 * 模块说明：用户管理页面（views/users/UsersView.vue）
 *
 * 职责：
 *   - 用户列表：关键词/状态筛选，分页展示
 *   - 新增用户：用户名/密码/邮箱/手机号/角色
 *   - 编辑用户：邮箱/手机号/状态
 *   - 封禁/解封用户（弹窗确认）
 *   - 查看用户收货地址列表
 * ============================================================
 -->
<script setup lang="ts">
// Vue 响应式工具与生命周期钩子
import { ref, reactive, onMounted } from 'vue'
// Element Plus 消息提示与确认框
import { ElMessage, ElMessageBox } from 'element-plus'
// 用户模块相关 API：列表/新增/编辑/封禁/地址及数据类型
import { getUsers, createUser, updateUser, banUser, getAddresses, type UserItem, type AddressItem } from '@/api/users'

// ── 列表 ──
// 列表加载状态（表格 loading 遮罩）
const loading = ref(false)
// 用户列表数据
const list = ref<UserItem[]>([])
// 用户总条数（分页用）
const total = ref(0)
// 列表筛选与分页参数：关键词、状态、页码、每页条数
const search = reactive({ keyword: '', status: '', page: 1, page_size: 20 })

/**
 * 拉取用户列表（异步）
 * 按当前筛选条件请求分页数据，写入 list 与 total
 */
async function fetchList() {
  loading.value = true
  const res = await getUsers(search)
  list.value = res.data || []
  total.value = res.total
  loading.value = false
}

// ── 新建 ──
// 创建用户弹窗显示/隐藏
const createVisible = ref(false)
// 创建用户表单：用户名、密码、邮箱、手机号、角色（默认只读 viewer）
const createForm = reactive({ username: '', password: '', email: '', phone: '', role: 'viewer' })
/**
 * 提交创建用户（异步）
 * 调用创建接口，成功后提示、关闭弹窗并刷新列表
 */
async function handleCreate() {
  await createUser({ ...createForm })
  ElMessage.success('创建成功')
  createVisible.value = false
  fetchList()
}

// ── 封禁/解封 ──
/**
 * 封禁/解封用户（异步）
 * 根据当前状态确定动作文案（banned → 解封，其他 → 封禁），
 * 弹窗确认后调用封禁接口并刷新列表
 * @param id     用户 ID
 * @param status 用户当前状态
 */
async function handleBan(id: number, status: string) {
  // 根据当前状态决定操作文案
  const action = status === 'banned' ? '解封' : '封禁'
  // 弹窗二次确认
  await ElMessageBox.confirm(`确定${action}该用户？`, '提示', { type: 'warning' })
  // 调用封禁/解封接口
  await banUser(id)
  ElMessage.success(`${action}成功`)
  fetchList()
}

// ── 地址 ──
// 地址弹窗显示/隐藏
const addrVisible = ref(false)
// 当前用户的收货地址列表
const addrList = ref<AddressItem[]>([])
/**
 * 打开用户收货地址弹窗（异步）
 * @param userId 用户 ID
 */
async function openAddresses(userId: number) {
  const res = await getAddresses(userId)
  addrList.value = res.data || []
  addrVisible.value = true
}

// ── 编辑 ──
// 编辑用户弹窗显示/隐藏
const editVisible = ref(false)
// 编辑用户表单：用户 ID、邮箱、手机号、状态
const editForm = reactive({ id: 0, email: '', phone: '', status: '' })
/**
 * 打开编辑用户弹窗
 * 将行数据（邮箱/手机号/状态）回填到表单
 * @param row 表格当前行的用户数据
 */
function openEdit(row: UserItem) {
  Object.assign(editForm, { id: row.id, email: row.email || '', phone: row.phone || '', status: row.status })
  editVisible.value = true
}
/**
 * 提交编辑用户（异步）
 * 调用更新接口，成功后提示、关闭弹窗并刷新列表
 */
async function handleEdit() {
  await updateUser(editForm.id, { email: editForm.email, phone: editForm.phone, status: editForm.status })
  ElMessage.success('更新成功')
  editVisible.value = false
  fetchList()
}

// 页面挂载：初始化加载用户列表
onMounted(fetchList)
</script>

<template>
  <!-- 页面容器（通用白底卡片样式） -->
  <div class="page-container">
    <!-- 工具栏：左侧为筛选条件，右侧为新增用户按钮 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <!-- 关键词搜索：用户名/手机/邮箱 -->
        <el-input v-model="search.keyword" placeholder="用户名/手机/邮箱" clearable style="width:200px" @change="fetchList" />
        <!-- 状态筛选：正常/禁用/封禁 -->
        <el-select v-model="search.status" placeholder="状态" clearable style="width:110px" @change="fetchList">
          <el-option label="正常" value="active" /><el-option label="禁用" value="disabled" /><el-option label="封禁" value="banned" />
        </el-select>
      </div>
      <!-- 打开新增用户弹窗 -->
      <el-button type="primary" @click="createVisible = true">新增用户</el-button>
    </div>

    <!-- 用户列表表格：用户名/邮箱/手机号/角色/状态/注册时间 -->
    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column prop="email" label="邮箱" min-width="160" />
      <el-table-column prop="phone" label="手机号" width="130" />
      <el-table-column prop="role" label="角色" width="100" />
      <!-- 用户状态标签：正常绿/封禁红/禁用灰 -->
      <el-table-column label="状态" width="90">
        <template #default="{row}">
          <el-tag :type="row.status==='active'?'success':row.status==='banned'?'danger':'info'">{{ row.status === 'active' ? '正常' : row.status === 'banned' ? '封禁' : '禁用' }}</el-tag>
        </template>
      </el-table-column>
      <!-- 注册时间（格式化去掉 T） -->
      <el-table-column prop="created_at" label="注册时间" width="170">
        <template #default="{row}">{{ row.created_at?.slice(0,19).replace('T',' ') }}</template>
      </el-table-column>
      <!-- 行操作：编辑 / 地址 / 封禁或解封 -->
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <!-- 编辑用户信息 -->
          <el-button text type="primary" size="small" @click="openEdit(row)">编辑</el-button>
          <!-- 查看收货地址 -->
          <el-button text type="warning" size="small" @click="openAddresses(row.id)">地址</el-button>
          <!-- 封禁（红色）/ 解封（绿色），按当前状态切换 -->
          <el-button text :type="row.status==='banned'?'success':'danger'" size="small" @click="handleBan(row.id, row.status)">
            {{ row.status === 'banned' ? '解封' : '封禁' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页器：切换页码触发重新查询 -->
    <el-pagination v-model:current-page="search.page" :total="total" :page-size="20" layout="total,prev,pager,next" style="margin-top:16px;justify-content:flex-end" @change="fetchList" />

    <!-- 创建用户弹窗：用户名/密码/邮箱/手机号/角色 -->
    <el-dialog title="新增用户" v-model="createVisible" width="450px">
      <el-form :model="createForm" label-width="80px">
        <el-form-item label="用户名"><el-input v-model="createForm.username" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="createForm.password" type="password" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="createForm.email" /></el-form-item>
        <el-form-item label="手机号"><el-input v-model="createForm.phone" /></el-form-item>
        <!-- 角色选择：超级管理员/管理员/运营/只读 -->
        <el-form-item label="角色">
          <el-select v-model="createForm.role" style="width:100%">
            <el-option label="超级管理员" value="super_admin" /><el-option label="管理员" value="admin" />
            <el-option label="运营" value="operator" /><el-option label="只读" value="viewer" />
          </el-select>
        </el-form-item>
      </el-form>
      <!-- 弹窗底部按钮：取消 / 创建 -->
      <template #footer><el-button @click="createVisible=false">取消</el-button><el-button type="primary" @click="handleCreate">创建</el-button></template>
    </el-dialog>

    <!-- 编辑用户弹窗：邮箱/手机号/状态 -->
    <el-dialog title="编辑用户" v-model="editVisible" width="400px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="邮箱"><el-input v-model="editForm.email" /></el-form-item>
        <el-form-item label="手机号"><el-input v-model="editForm.phone" /></el-form-item>
        <!-- 状态选择：正常/禁用 -->
        <el-form-item label="状态"><el-select v-model="editForm.status" style="width:100%"><el-option label="正常" value="active" /><el-option label="禁用" value="disabled" /></el-select></el-form-item>
      </el-form>
      <!-- 弹窗底部按钮：取消 / 保存 -->
      <template #footer><el-button @click="editVisible=false">取消</el-button><el-button type="primary" @click="handleEdit">保存</el-button></template>
    </el-dialog>

    <!-- 地址弹窗：展示用户全部收货地址 -->
    <el-dialog title="收货地址" v-model="addrVisible" width="550px">
      <el-table :data="addrList" size="small">
        <el-table-column prop="receiver" label="收货人" width="80" />
        <el-table-column prop="phone" label="电话" width="120" />
        <!-- 完整地址：省市区 + 详细地址 -->
        <el-table-column label="地址"><template #default="{row}">{{ row.province }}{{ row.city }}{{ row.district }} {{ row.detail }}</template></el-table-column>
        <!-- 默认地址标识 -->
        <el-table-column label="默认" width="60"><template #default="{row}"><el-tag v-if="row.is_default" type="success" size="small">默认</el-tag></template></el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>
