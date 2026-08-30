<!--
 * ============================================================
 * 模块说明：商品管理页面（views/products/ProductsView.vue）
 *
 * 职责：
 *   - 商品列表：关键词/类目/状态筛选、分页展示
 *   - 商品新增/编辑：基本信息、商品图片（URL 输入 + 本地上传）、
 *     规格与 SKU（按规格值笛卡尔积自动生成 SKU）、上下架
 *   - 类目管理：新增商品类目（可指定上级类目）
 *   - 商品上下架操作
 *
 * 依赖接口：
 *   - GET/POST/PUT/DELETE /products、POST /products/{id}/online|offline
 *   - GET/POST /categories、POST /products/upload-image
 * ============================================================
 -->
<script setup lang="ts">
// Vue 响应式工具与生命周期钩子（computed 预留，当前版本未直接使用）
import { ref, reactive, onMounted, computed } from 'vue'
// Element Plus 消息提示与确认框
import { ElMessage, ElMessageBox } from 'element-plus'
// 商品模块相关 API：列表/增删改/上下架/类目/图片上传及数据类型
import {
  getProducts, createProduct, updateProduct, deleteProduct, onlineProduct, offlineProduct,
  getCategories, createCategory, uploadProductImage, type ProductItem, type CategoryItem,
} from '@/api/products'

// ── 商品列表 ──
// 列表加载状态（表格 loading 遮罩）
const loading = ref(false)
// 商品列表数据
const list = ref<ProductItem[]>([])
// 商品总条数（分页用）
const total = ref(0)
// 列表筛选与分页参数：关键词、类目 ID、状态、页码、每页条数
const search = reactive({ keyword: '', category_id: undefined as number | undefined, status: '', page: 1, page_size: 20 })

// 类目下拉选项数据（供列表筛选与商品表单选择类目）
const categories = ref<CategoryItem[]>([])

/**
 * 拉取商品列表（异步）
 * 按当前筛选条件请求分页数据，写入 list 与 total
 */
async function fetchList() {
  loading.value = true
  const res = await getProducts(search)
  list.value = res.data || []
  total.value = res.total
  loading.value = false
}

/**
 * 拉取类目列表（异步）
 * 用于列表筛选下拉与商品表单的类目选择
 */
async function fetchCategories() {
  const res = await getCategories()
  categories.value = res.data || []
}

// 商品状态 → Element Plus 标签类型的映射（上架绿/下架灰/草稿黄）
const statusTag: Record<string, string> = { online: 'success', offline: 'info', draft: 'warning' }
// 商品状态 → 中文文案的映射
const statusText: Record<string, string> = { online: '已上架', offline: '已下架', draft: '草稿' }

// ── 类目弹窗 ──
// 类目弹窗显示/隐藏
const cateVisible = ref(false)
// 类目表单：名称、上级类目 ID（可空）、层级（默认 1 级）
const cateForm = reactive({ name: '', parent_id: undefined as number | undefined, level: 1 })
/**
 * 提交创建类目（异步）
 * 调用创建类目接口，成功后刷新类目下拉并关闭弹窗
 */
async function submitCategory() {
  await createCategory(cateForm)
  ElMessage.success('类目创建成功')
  cateVisible.value = false
  fetchCategories()
}

// ── 商品编辑弹窗 ──
// 商品编辑弹窗显示/隐藏
const dialogVisible = ref(false)
// 是否为编辑模式（true 编辑 / false 新增）
const isEdit = ref(false)
// 商品编辑表单数据（含基础信息、图片列表、SKU 列表；any 以便灵活赋值接口返回字段）
const editForm = reactive({
  id: undefined as number | undefined,
  spu_code: '', name: '', subtitle: '', category_id: undefined, brand: '', main_image: '', description: '',
  images: [] as { url: string; sort_order: number; is_main: boolean }[],
  skus: [] as { sku_code: string; spec_info: Record<string, string>; price: number; original_price?: number; barcode?: string; stock: number }[],
})
// 规格名列表（如 ['颜色', '尺寸']，仅新增模式用于生成 SKU）
const specKeys = ref<string[]>([])
// 规格名 → 规格值数组的映射（如 { 颜色: ['红','蓝'] }）
const specTemplate = ref<Record<string, string[]>>({})

/**
 * 新增一个规格项（添加一行规格名输入）
 * 同时初始化该规格的值为空数组
 */
function addSpecKey() { specKeys.value.push(''); specTemplate.value[''] = [] }
/**
 * 删除指定下标的规格项
 * @param i 规格项在 specKeys 中的下标
 */
function removeSpecKey(i: number) { specKeys.value.splice(i, 1) }

/**
 * 依据规格组合自动生成 SKU 列表
 * 逻辑：取所有非空规格名及其规格值，做笛卡尔积得到全部组合，
 * 为每个组合生成一个 SKU（随机编码、规格信息、默认价格/库存为 0）
 */
function generateSkus() {
  // 过滤出已填写的规格名
  const keys = specKeys.value.filter(Boolean)
  // 无有效规格名时直接返回
  if (!keys.length) return
  // 对每个规格的取值做笛卡尔积，得到所有组合
  const combos = cartesian(keys.map((k) => specTemplate.value[k] || []))
  // 为每个组合生成一条 SKU 记录
  editForm.skus = combos.map((c) => ({
    // 生成随机 SKU 编码：时间戳 + 4 位随机字符串
    sku_code: `SKU-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    // 规格信息：规格名 → 该组合对应的规格值
    spec_info: Object.fromEntries(keys.map((k, i) => [k, c[i]])),
    // 初始价格/库存为 0，由管理员后续填写
    price: 0, original_price: undefined, barcode: '', stock: 0,
  }))
}

/**
 * 笛卡尔积工具函数
 * 将多个字符串数组组合成所有可能的组合
 * @param arrays 规格值数组列表（每个数组对应一个规格）
 * @returns 所有组合的二维数组，如 [['红','S'], ['红','L'], ...]
 */
function cartesian(arrays: string[][]): string[][] {
  // 从 [[]] 开始逐个数组展开组合
  return arrays.reduce<string[][]>((acc, cur) => acc.flatMap((a) => cur.map((c) => [...a, c])), [[]])
}

/**
 * 添加一条空图片记录
 * 默认第 0 张图为主图（is_main = true）
 */
function addImage() { editForm.images.push({ url: '', sort_order: editForm.images.length, is_main: editForm.images.length === 0 }) }

/**
 * 商品图片上传处理（异步）
 * 调用上传接口获取图片 URL，回填到对应图片记录中
 * @param file  待上传的图片文件（由 el-upload 提供）
 * @param index 目标图片记录在 images 数组中的下标
 * @returns {false} 返回 false 阻止 el-upload 的默认上传行为
 */
async function handleImageUpload(file: File, index: number) {
  // 调用后端上传接口，返回图片 URL
  const res = await uploadProductImage(file)
  // 将 URL 回填到对应图片记录
  editForm.images[index].url = res.data.url
  ElMessage.success('上传成功')
  return false // prevent default upload（阻止默认上传）
}

/**
 * 打开「新增商品」弹窗
 * 重置编辑表单、规格数据为初始状态，切换到新增模式
 */
function openCreate() {
  isEdit.value = false
  Object.assign(editForm, { spu_code: '', name: '', subtitle: '', category_id: undefined, brand: '', main_image: '', description: '', images: [], skus: [] })
  specKeys.value = []
  specTemplate.value = {}
  dialogVisible.value = true
}

/**
 * 打开「编辑商品」弹窗
 * 将行数据（含图片、SKU）回填到编辑表单，切换到编辑模式
 * @param row 表格当前行的商品数据
 */
function openEdit(row: ProductItem) {
  isEdit.value = true
  Object.assign(editForm, { ...row, images: row.images || [], skus: row.skus || [] })
  dialogVisible.value = true
}

/**
 * 提交商品表单（异步）
 * 编辑模式调用更新接口（仅提交可编辑字段）；新增模式调用创建接口
 * 成功后提示并刷新列表
 */
async function submitForm() {
  if (isEdit.value) {
    // 编辑模式：只提交允许修改的字段
    await updateProduct(editForm.id!, {
      name: editForm.name,
      subtitle: editForm.subtitle,
      category_id: editForm.category_id,
      brand: editForm.brand,
      main_image: editForm.main_image,
      description: editForm.description,
      images: editForm.images,
      skus: editForm.skus,
    })
  } else {
    // 新增模式：整体提交表单数据
    await createProduct(editForm)
  }
  ElMessage.success(isEdit.value ? '更新成功' : '创建成功')
  dialogVisible.value = false
  fetchList()
}

/**
 * 下架/删除商品（异步）
 * 弹窗确认后调用删除接口（业务上下架即删除），成功后刷新列表
 * @param id 商品 ID
 */
async function handleDelete(id: number) {
  await ElMessageBox.confirm('确定下架该商品？', '提示', { type: 'warning' })
  await deleteProduct(id)
  ElMessage.success('已下架')
  fetchList()
}

/**
 * 上架商品（异步）
 * @param id 商品 ID
 */
async function handleOnline(id: number) { await onlineProduct(id); fetchList() }
/**
 * 下架商品（异步）
 * @param id 商品 ID
 */
async function handleOffline(id: number) { await offlineProduct(id); fetchList() }

// 页面挂载：并行初始化商品列表与类目下拉数据
onMounted(() => { fetchList(); fetchCategories() })
</script>

<template>
  <!-- 页面容器（通用白底卡片样式） -->
  <div class="page-container">
    <!-- 工具栏：左侧为筛选条件，右侧为操作按钮 -->
    <div class="toolbar">
      <!-- 左侧筛选区：关键词 / 类目 / 状态 -->
      <div class="toolbar-left">
        <!-- 关键词搜索：商品名称/编码，输入后回车或失焦触发查询 -->
        <el-input v-model="search.keyword" placeholder="商品名称/编码" clearable style="width:200px" @change="fetchList" />
        <!-- 类目筛选下拉：选项来自类目接口 -->
        <el-select v-model="search.category_id" placeholder="类目" clearable style="width:140px" @change="fetchList">
          <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
        <!-- 状态筛选下拉：已上架/已下架/草稿 -->
        <el-select v-model="search.status" placeholder="状态" clearable style="width:110px" @change="fetchList">
          <el-option label="已上架" value="online" /><el-option label="已下架" value="offline" /><el-option label="草稿" value="draft" />
        </el-select>
      </div>
      <!-- 右侧操作按钮：类目管理 + 新增商品 -->
      <div style="display:flex;gap:8px">
        <!-- 打开类目创建弹窗 -->
        <el-button @click="cateVisible = true">类目管理</el-button>
        <!-- 打开新增商品弹窗 -->
        <el-button type="primary" @click="openCreate">新增商品</el-button>
      </div>
    </div>

    <!-- 商品列表表格：展示编码/图片/名称/价格区间/状态/销量 -->
    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="spu_code" label="编码" width="120" />
      <!-- 商品主图缩略图（无主图则不展示） -->
      <el-table-column label="商品图" width="80"><template #default="{row}"><el-image v-if="row.main_image" :src="row.main_image" style="width:48px;height:48px" fit="cover" /></template></el-table-column>
      <el-table-column prop="name" label="商品名称" min-width="160" />
      <!-- 价格区间：最低价-最高价 -->
      <el-table-column label="价格" width="120"><template #default="{row}">¥{{ row.min_price }}-{{ row.max_price }}</template></el-table-column>
      <!-- 商品状态标签 -->
      <el-table-column label="状态" width="90"><template #default="{row}"><el-tag :type="statusTag[row.status]">{{ statusText[row.status] }}</el-tag></template></el-table-column>
      <el-table-column prop="total_sales" label="销量" width="80" />
      <!-- 行操作：编辑 / 上架 / 下架（按当前状态条件渲染） -->
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <!-- 编辑商品 -->
          <el-button text type="primary" size="small" @click="openEdit(row)">编辑</el-button>
          <!-- 非上架状态显示「上架」按钮 -->
          <el-button v-if="row.status!=='online'" text type="success" size="small" @click="handleOnline(row.id)">上架</el-button>
          <!-- 上架状态显示「下架」按钮 -->
          <el-button v-if="row.status==='online'" text type="warning" size="small" @click="handleOffline(row.id)">下架</el-button>
          <!-- 删除（业务上等同下架），需弹窗确认 -->
          <el-button text type="danger" size="small" @click="handleDelete(row.id)">下架</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页器：切换页码触发重新查询 -->
    <el-pagination v-model:current-page="search.page" :total="total" :page-size="20" layout="total,prev,pager,next" style="margin-top:16px;justify-content:flex-end" @change="fetchList" />

    <!-- 商品编辑弹窗：新增/编辑共用，标题按模式切换，关闭时销毁内部状态 -->
    <el-dialog :title="isEdit?'编辑商品':'新增商品'" v-model="dialogVisible" width="800px" destroy-on-close>
      <el-form :model="editForm" label-width="80px">
        <!-- 基础信息：SPU 编码（编辑时禁用）、名称 -->
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="SPU编码"><el-input v-model="editForm.spu_code" :disabled="isEdit" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="商品名称"><el-input v-model="editForm.name" /></el-form-item></el-col>
        </el-row>
        <!-- 副标题与类目选择 -->
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="副标题"><el-input v-model="editForm.subtitle" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="类目"><el-select v-model="editForm.category_id" style="width:100%"><el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" /></el-select></el-form-item></el-col>
        </el-row>
        <!-- 品牌与主图 URL -->
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="品牌"><el-input v-model="editForm.brand" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="主图URL"><el-input v-model="editForm.main_image" /></el-form-item></el-col>
        </el-row>
        <!-- 商品描述（多行文本） -->
        <el-form-item label="描述"><el-input v-model="editForm.description" type="textarea" :rows="3" /></el-form-item>

        <!-- 图片区：URL 输入 + 本地上传 + 主图开关 + 删除 -->
        <el-divider>商品图片</el-divider>
        <div v-for="(img,i) in editForm.images" :key="i" style="display:flex;gap:8px;margin-bottom:8px;align-items:center">
          <div style="display:flex; align-items:center; gap:8px; width:100%">
            <!-- 图片 URL 输入框 -->
            <el-input v-model="img.url" placeholder="图片URL" style="flex:1" />
            <!-- 本地上传按钮：上传成功后回填 URL 到当前行 -->
            <el-upload
              :show-file-list="false"
              :before-upload="(file: File) => handleImageUpload(file, i)"
              accept="image/jpeg,image/png,image/webp"
            >
              <el-button type="primary" size="small">上传</el-button>
            </el-upload>
          </div>
          <!-- 已填 URL 时展示图片预览 -->
          <div v-if="img.url" style="margin-top:6px">
            <el-image :src="img.url" style="width:80px;height:80px;border-radius:6px" fit="cover" />
          </div>
          <!-- 是否设为主图开关 -->
          <el-switch v-model="img.is_main" active-text="主图" style="width:80px" />
          <!-- 删除该图片行 -->
          <el-button text type="danger" @click="editForm.images.splice(i,1)">删除</el-button>
        </div>
        <!-- 添加图片行按钮 -->
        <el-button size="small" @click="addImage">+ 添加图片</el-button>

        <!-- SKU 区：仅新增模式可编辑规格，按规格组合生成 SKU -->
        <el-divider>规格与SKU</el-divider>
        <div v-if="!isEdit">
          <!-- 规格名与规格值输入行（值以逗号分隔，实时拆分为数组） -->
          <div v-for="(k,i) in specKeys" :key="i" style="display:flex;gap:8px;margin-bottom:8px;align-items:center">
            <el-input v-model="specKeys[i]" placeholder="规格名(如:规格)" style="width:140px" />
            <el-input v-model="specTemplate[specKeys[i]]" placeholder="规格值(逗号分隔)" style="flex:1" @input="(v:string) => specTemplate[specKeys[i]] = v.split(',').map(s=>s.trim())" />
            <!-- 删除该规格行 -->
            <el-button text type="danger" @click="removeSpecKey(i)">删除</el-button>
          </div>
          <!-- 添加规格行 / 按规格组合一键生成 SKU（无有效规格名时禁用） -->
          <el-button size="small" @click="addSpecKey">+ 添加规格</el-button>
          <el-button size="small" type="primary" style="margin-left:8px" :disabled="!specKeys.filter(Boolean).length" @click="generateSkus">生成SKU</el-button>
        </div>

        <!-- SKU 明细表格：逐行编辑价格/原价/库存/条码，可删除行 -->
        <el-table v-if="editForm.skus.length" :data="editForm.skus" size="small" style="margin-top:12px">
          <!-- 规格组合展示（如 红/S） -->
          <el-table-column label="规格" min-width="140"><template #default="{row}">{{ Object.values(row.spec_info||{}).join('/') }}</template></el-table-column>
          <!-- 售价 -->
          <el-table-column label="价格" width="120"><template #default="{row,$index}"><el-input v-model="editForm.skus[$index].price" size="small" /></template></el-table-column>
          <!-- 划线原价 -->
          <el-table-column label="原价" width="120"><template #default="{row,$index}"><el-input v-model="editForm.skus[$index].original_price" size="small" /></template></el-table-column>
          <!-- 库存数量 -->
          <el-table-column label="库存" width="100"><template #default="{row,$index}"><el-input v-model="editForm.skus[$index].stock" size="small" /></template></el-table-column>
          <!-- 商品条码 -->
          <el-table-column label="条码" width="130"><template #default="{row,$index}"><el-input v-model="editForm.skus[$index].barcode" size="small" /></template></el-table-column>
          <!-- 删除该 SKU 行 -->
          <el-table-column label="操作" width="70" fixed="right">
            <template #default="{ $index }">
              <el-button text type="danger" size="small" @click="editForm.skus.splice($index, 1)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-form>
      <!-- 弹窗底部按钮：取消 / 保存 -->
      <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" @click="submitForm">保存</el-button></template>
    </el-dialog>

    <!-- 类目弹窗：新增商品类目（可指定上级类目） -->
    <el-dialog title="新增类目" v-model="cateVisible" width="400px">
      <el-form :model="cateForm" label-width="80px">
        <!-- 类目名称 -->
        <el-form-item label="类目名"><el-input v-model="cateForm.name" /></el-form-item>
        <!-- 上级类目（可选，留空则为顶级类目） -->
        <el-form-item label="上级类目"><el-select v-model="cateForm.parent_id" clearable style="width:100%"><el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" /></el-select></el-form-item>
      </el-form>
      <!-- 弹窗底部按钮：取消 / 创建 -->
      <template #footer><el-button @click="cateVisible=false">取消</el-button><el-button type="primary" @click="submitCategory">创建</el-button></template>
    </el-dialog>
  </div>
</template>
