<!--
  ═══════════════════════════════════════════════════════════
  茗韵茶庄商城 · 商品列表页（ProductListView.vue）
  ───────────────────────────────────────────────────────────
  职责说明：
    商城商品浏览与筛选页（路由 /products），支持：
      1. 类目胶囊筛选（全部 + 各茶叶类目，通过路由 query.category_id 驱动）；
      2. 排序（综合 / 价格升序 / 价格降序）与价格区间筛选（最低/最高价）；
      3. 关键词搜索联动（读取 route.query.keyword）；
      4. 商品卡片网格展示（含骨架屏加载态、印章徽标、悬停浮层）；
      5. 分页浏览（el-pagination）；
      6. 路由查询变化（类目/关键词）时自动重置页码并重新拉取（watch）。
  ═══════════════════════════════════════════════════════════
-->
<template>
  <div class="shop-container products-page">
    <!-- 页面标题 -->
    <div class="list-head">
      <h2 class="list-title">全部好茶</h2>
      <p class="list-sub">精选产地直供 · 传统工艺制作</p>
    </div>

    <!-- 类目胶囊 -->
    <!-- 类目筛选：点击后更新路由 query（pickCat），"全部"清除类目参数 -->
    <div class="category-pills">
      <span class="pill" :class="{ active: !activeCat }" @click="pickCat()">全部</span>
      <span
        v-for="c in cats"
        :key="c.id"
        class="pill"
        :class="{ active: activeCat === c.id }"
        @click="pickCat(c.id)"
      >{{ c.name }}</span>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <!-- 排序单选组：切换排序后重新拉取 -->
      <el-radio-group v-model="sort" @change="fetchData" class="sort-group">
        <el-radio-button value="">综合</el-radio-button>
        <el-radio-button value="price_asc">价格 ↑</el-radio-button>
        <el-radio-button value="price_desc">价格 ↓</el-radio-button>
      </el-radio-group>
      <!-- 价格区间：最低价—最高价 + 确定按钮 -->
      <div class="price-filter">
        <el-input-number v-model="minPrice" :min="0" placeholder="最低价" size="small" controls-position="right" style="width:110px" />
        <span class="price-sep">—</span>
        <el-input-number v-model="maxPrice" :min="0" placeholder="最高价" size="small" controls-position="right" style="width:110px" />
        <el-button size="small" class="filter-btn" @click="fetchData">确定</el-button>
      </div>
    </div>

    <!-- 商品列表 -->
    <!-- 加载中：12 张骨架屏占位 -->
    <ProductSkeleton v-if="loading" :count="12" />
    <!-- 加载完成：商品卡片网格 -->
    <div v-else class="product-grid">
      <!-- 每张商品卡片：点击进入详情页 -->
      <div
        v-for="item in products"
        :key="item.id"
        class="product-card"
        @click="$router.push(`/product/${item.id}`)"
      >
        <!-- 图片区：主图 + 印章徽标 + 悬停浮层 -->
        <div class="card-img-wrap">
          <el-image :src="item.images?.[0] || ''" fit="cover" class="card-img" lazy>
            <template #error>
              <div class="image-placeholder"><TeaIcon name="bowl" class="placeholder-icon" /></div>
            </template>
          </el-image>
          <!-- 徽标：类目名 + 推导徽标 -->
          <div class="card-tags">
            <span class="seal-tag tea" v-if="item.category_name">{{ item.category_name }}</span>
            <span
              v-for="b in cardBadges(item)"
              :key="b.text"
              class="seal-tag"
              :class="b.cls"
            >{{ b.text }}</span>
          </div>
          <div class="card-hover">
            <span class="hover-btn">查看详情 →</span>
          </div>
        </div>
        <!-- 文字区：名称 + 价格/销量 -->
        <div class="card-body">
          <h3 class="card-name">{{ item.name }}</h3>
          <div class="card-footer">
            <span class="card-price"><i>¥</i>{{ item.price?.toFixed(2) }}</span>
            <span class="card-sold">已售 {{ item.total_sales || 0 }}+</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态：无商品时展示 -->
    <el-empty v-if="!loading && products.length === 0">
      <template #image><EmptyTea>暂无上架商品</EmptyTea></template>
      <el-button type="primary" @click="fetchData">刷新看看</el-button>
    </el-empty>

    <!-- 分页组件 -->
    <div class="pagination-wrap" v-if="total > 0">
      <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next" background @current-change="fetchData" />
    </div>
  </div>
</template>

<script setup lang="ts">
// ── 依赖引入 ──
import { ref, computed, onMounted, watch } from 'vue' // Vue 响应式/计算属性/生命周期/侦听器
import { useRoute, useRouter } from 'vue-router' // 路由：读取查询参数 + 更新类目参数
import { getProducts, getCategories, type Product, type Category } from '@/api/products' // 商品/类目 API 与类型
import ProductSkeleton from '@/components/ProductSkeleton.vue' // 骨架屏组件
import TeaIcon from '@/components/TeaIcon.vue' // 主题图标（图片失败占位）
import EmptyTea from '@/components/EmptyTea.vue' // 空状态组件

// ── 状态定义 ──
const route = useRoute() // 当前路由（读取 keyword/category_id 查询参数）
const router = useRouter() // 路由实例（pickCat 更新类目参数）

const products = ref<Product[]>([]) // 商品列表
const loading = ref(false) // 加载中标记
const page = ref(1) // 当前页码
const pageSize = 12 // 每页条数（固定 12）
const total = ref(0) // 商品总数（驱动分页）
const sort = ref('') // 排序方式：'' 综合 / price_asc 价格升序 / price_desc 价格降序
const minPrice = ref<number | undefined>() // 最低价筛选（未填为 undefined）
const maxPrice = ref<number | undefined>() // 最高价筛选
const cats = ref<Category[]>([]) // 类目列表（胶囊数据源）

// ── 当前激活类目（计算属性） ──
// 作用：从路由查询参数 category_id 派生当前类目 ID（无参数时为 undefined）
const activeCat = computed(() => (route.query.category_id ? Number(route.query.category_id) : undefined))

// ── 切换类目 ──
// 作用：更新路由查询参数（设置或删除 category_id），路由变化由下方 watch 感知并重新拉取
// 参数：id —— 类目 ID（省略或 undefined 表示"全部"，删除类目参数）；返回值：无
function pickCat(id?: number) {
  const q: Record<string, string> = { ...route.query } as Record<string, string> // 拷贝当前查询参数
  if (id) q.category_id = String(id) // 有类目：写入 category_id
  else delete q.category_id // 无类目："全部"，删除 category_id
  router.push({ query: q }) // 更新路由
}

// ── 监听路由查询变化 ──
// 作用：类目/关键词等查询参数变化时重置到第一页并重新拉取商品
watch(() => route.query, () => {
  page.value = 1 // 查询变化时回到第一页
  fetchData()
})

// ── 商品印章徽标推导 ──
// 从真实商品数据推导印章徽标（名称/销量），不虚构信息
// 作用：根据商品名称关键词与销量阈值生成徽标数组（最多 2 个）
// 参数：item —— 商品对象；返回值：徽标数组 [{ text, cls }]
function cardBadges(item: Product): { text: string; cls: string }[] {
  const tags: { text: string; cls: string }[] = []
  const n = item.name || ''
  if (n.includes('明前')) tags.push({ text: '明前', cls: 'soft' })
  if (n.includes('雨前')) tags.push({ text: '雨前', cls: 'soft' })
  if (n.includes('头采')) tags.push({ text: '头采', cls: 'gold' })
  if (n.includes('古树')) tags.push({ text: '古树', cls: 'cinnabar' })
  if (n.includes('特级')) tags.push({ text: '特级', cls: 'soft' })
  if (n.includes('礼盒')) tags.push({ text: '礼盒', cls: 'gold' })
  if ((item.total_sales || 0) >= 300) tags.push({ text: '热销', cls: 'cinnabar' })
  return tags.slice(0, 2)
}

// ── 拉取商品列表 ──
// 作用：按页码/关键词/类目/排序/价格区间组装参数请求商品列表，成功写入列表与总数
// 参数：无；返回值：Promise<void>
async function fetchData() {
  loading.value = true
  try {
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize } // 基础分页参数
    if (route.query.keyword) params.keyword = route.query.keyword // 关键词（来自顶部搜索框）
    if (route.query.category_id) params.category_id = Number(route.query.category_id) // 类目
    if (sort.value) params.sort = sort.value // 排序方式
    if (minPrice.value != null) params.min_price = minPrice.value // 最低价
    if (maxPrice.value != null) params.max_price = maxPrice.value // 最高价

    const res = await getProducts(params) // 请求商品列表
    products.value = res.data.data?.items || []
    total.value = res.data.data?.total || 0
  } catch { products.value = [] } finally { loading.value = false } // 失败置空；最终复位 loading
}

// ── 页面挂载后：加载类目并拉取首屏商品 ──
onMounted(async () => {
  try {
    const res = await getCategories() // 拉取类目列表（胶囊数据源）
    cats.value = res.data.data || []
  } catch { /* ignore */ } // 类目拉取失败不影响商品展示
  fetchData() // 拉取首屏商品
})
</script>

<style scoped>
/* ── 页面容器 ── */
.products-page { padding: 24px 20px 40px; }

/* ── 页面标题区：居中 ── */
.list-head {
  text-align: center;
  margin: 10px 0 26px;
}

.list-title {
  font-family: var(--font-serif);
  font-size: 30px;
  letter-spacing: 6px;
  color: var(--ink);
  margin-bottom: 8px;
}

.list-sub {
  font-size: 13px;
  color: var(--ink-soft);
  letter-spacing: 2px;
}

/* ── 类目胶囊：换行居中的胶囊按钮组 ── */
.category-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 18px;
  justify-content: center;
}

/* 胶囊按钮：默认白底描边，hover 金色，激活态茶青底白字 */
.pill {
  padding: 7px 18px;
  font-size: 13px;
  color: var(--ink-soft);
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.2s;
  letter-spacing: 1px;
}

.pill:hover {
  border-color: var(--gold);
  color: var(--gold-deep);
}

.pill.active {
  background: var(--tea);
  border-color: var(--tea);
  color: var(--paper);
  font-weight: 600;
}

/* ── 筛选栏：排序 + 价格区间，两端分布 ── */
.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
  padding: 14px 20px;
  border-radius: 12px;
  margin-bottom: 20px;
  box-shadow: 0 2px 12px rgba(61, 50, 39, 0.05);
}

.price-filter {
  display: flex;
  align-items: center;
  gap: 8px;
}

.price-sep { color: #d9c6a3; margin: 0 4px; }

.filter-btn { background: #3f5d4a !important; border-color: #3f5d4a !important; color: #fff !important; }

/* ── Product Grid ── */
/* 商品网格：桌面端四列 */
.product-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

/* 平板及以下：两列 */
@media (max-width: 960px) { .product-grid { grid-template-columns: repeat(2, 1fr); } }

/* ── 商品卡片 ── */
.product-card {
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 2px 12px rgba(61, 50, 39, 0.06);
}

.product-card:hover {
  transform: translateY(-6px);
  box-shadow: 0 12px 32px rgba(61, 50, 39, 0.12);
}

/* 图片区：固定高度 */
.card-img-wrap {
  width: 100%;
  height: 240px;
  overflow: hidden;
  background: #faf6ef;
}

.card-img {
  width: 100%;
  height: 100%;
  transition: transform 0.4s;
}

/* 左上角徽标区 */
.card-tags {
  position: absolute;
  top: 12px;
  left: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-width: calc(100% - 24px);
}

/* 底部悬停浮层：hover 时浮现"查看详情" */
.card-hover {
  position: absolute;
  inset: auto 0 0 0;
  padding: 28px 16px 14px;
  display: flex;
  justify-content: center;
  background: linear-gradient(180deg, transparent, rgba(44, 42, 38, 0.55));
  opacity: 0;
  transform: translateY(8px);
  transition: all 0.3s;
}

.product-card:hover .card-hover {
  opacity: 1;
  transform: translateY(0);
}

/* 悬停按钮：胶囊描边 + 毛玻璃 */
.hover-btn {
  font-size: 13px;
  color: #fdf9f0;
  border: 1px solid rgba(250, 246, 239, 0.75);
  border-radius: 999px;
  padding: 7px 18px;
  background: rgba(44, 42, 38, 0.35);
  backdrop-filter: blur(4px);
  letter-spacing: 1px;
}

/* 图片 hover 放大 */
.product-card:hover .card-img { transform: scale(1.05); }

/* 图片加载失败占位 */
.image-placeholder {
  width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
  background: #f2ead9;
}

.placeholder-icon { font-size: 48px; }

/* 卡片文字区 */
.card-body { padding: 16px; }

/* 商品名：单行省略 */
.card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  letter-spacing: 1px;
}

/* 底部行：价格 + 销量 */
.card-footer { display: flex; justify-content: space-between; align-items: center; }
.card-price { font-size: 20px; color: var(--cinnabar); font-weight: 700; font-family: var(--font-serif); }
.card-price i { font-style: normal; font-size: 13px; margin-right: 1px; }
.card-sold { font-size: 12px; color: var(--ink-soft); opacity: 0.75; }

/* ── 分页区：居中 ── */
.pagination-wrap { display: flex; justify-content: center; margin-top: 36px; }
</style>
