<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getOpenApiKeys,
  getTenants,
  createOpenApiKey,
  createTenant,
  revokeOpenApiKey,
  type ApiKeyItem,
  type TenantItem,
} from '@/api/openapi'

const keys = ref<ApiKeyItem[]>([])
const tenants = ref<TenantItem[]>([])
const loading = ref(false)
const keyDialog = ref(false)
const tenantDialog = ref(false)
const keyForm = ref({ tenant_id: 1, name: '', scopes: ['read', 'chat'], expires_days: 90 })
const tenantForm = ref({ name: '', slug: '', contact_email: '' })

async function load() {
  loading.value = true
  try {
    const [k, t] = await Promise.all([getOpenApiKeys(), getTenants()])
    keys.value = k.data || []
    tenants.value = t.data || []
  } finally {
    loading.value = false
  }
}

async function doCreateKey() {
  const res = await createOpenApiKey(keyForm.value)
  if (res.code === 0) {
    ElMessage.success('API Key 创建成功，明文只显示一次')
    await load()
    keyDialog.value = false
  }
}

async function doCreateTenant() {
  const res = await createTenant(tenantForm.value)
  if (res.code === 0) {
    ElMessage.success('商户已创建')
    tenantDialog.value = false
    await load()
  }
}

async function doRevoke(row: ApiKeyItem) {
  const res = await revokeOpenApiKey(row.id)
  if (res.code === 0) {
    ElMessage.success('API Key 已撤销')
    await load()
  }
}

onMounted(load)
</script>

<template>
  <div class="page-container" v-loading="loading">
    <div class="page-head">
      <h3 style="margin: 0">开放平台 / ISV</h3>
      <div>
        <el-button @click="tenantDialog = true">新增商户</el-button>
        <el-button type="primary" @click="keyDialog = true">创建 API Key</el-button>
      </div>
    </div>

    <el-card shadow="never" style="margin-bottom:16px">
      <template #header><b>商户</b></template>
      <el-table :data="tenants" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="商户" min-width="160" />
        <el-table-column prop="slug" label="Slug" min-width="130" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="contact_email" label="邮箱" min-width="180" />
      </el-table>
    </el-card>

    <el-card shadow="never">
      <template #header><b>API Keys</b></template>
      <el-table :data="keys" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="tenant_id" label="商户ID" width="90" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="last_used_at" label="最后使用" min-width="180" />
        <el-table-column label="操作" width="110">
          <template #default="{ row }">
            <el-button link type="danger" v-if="row.status === 'active'" @click="doRevoke(row)">撤销</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="keyDialog" title="创建 API Key" width="520px">
      <el-form label-width="100px">
        <el-form-item label="名称"><el-input v-model="keyForm.name" /></el-form-item>
        <el-form-item label="商户"><el-input-number v-model="keyForm.tenant_id" :min="1" /></el-form-item>
        <el-form-item label="有效期(天)"><el-input-number v-model="keyForm.expires_days" :min="1" :max="365" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="keyDialog = false">取消</el-button>
        <el-button type="primary" @click="doCreateKey">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="tenantDialog" title="新增商户" width="520px">
      <el-form label-width="100px">
        <el-form-item label="名称"><el-input v-model="tenantForm.name" /></el-form-item>
        <el-form-item label="Slug"><el-input v-model="tenantForm.slug" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="tenantForm.contact_email" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="tenantDialog = false">取消</el-button>
        <el-button type="primary" @click="doCreateTenant">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
</style>
