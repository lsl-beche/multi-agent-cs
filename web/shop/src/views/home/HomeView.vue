<!--
  ═══════════════════════════════════════════════════════════
  茗韵茶庄商城 · 首页（HomeView.vue）
  ───────────────────────────────────────────────────────────
  职责说明：
    商城首页品牌展示页，自上而下包含：
      1. Hero Banner：茶山意境大图区（云雾/飘叶/印章装饰）+ 主标语与行动按钮；
      2. 特色服务区：四个优势卖点（原产地直供/匠心制作/保鲜包装/品质承诺）；
      3. 热门推荐区：拉取前 8 个商品并以商品卡片网格展示（含骨架屏加载态）；
      4. 品牌故事区：品牌叙事文案 + 制茶四艺步骤（采青/萎凋/揉捻/干燥）；
      5. 品类展示区：六大茶类快捷入口（点击跳转对应类目商品列表）。
    商品徽标（cardBadges）由真实商品名称/销量推导，不虚构信息。
  ═══════════════════════════════════════════════════════════
-->
<template>
  <div class="home-page">
    <!-- Hero Banner -->
    <section class="hero-banner">
      <!-- 背景装饰：两团流动的云雾 -->
      <div class="hero-mist mist-a"></div>
      <div class="hero-mist mist-b"></div>
      <!-- 背景装饰：三片飘落的茶叶 -->
      <div class="hero-leaf leaf-1"></div>
      <div class="hero-leaf leaf-2"></div>
      <div class="hero-leaf leaf-3"></div>
      <!-- 背景装饰：右上角呼吸浮动的印章 -->
      <div class="hero-seal"><img src="/seal.svg" alt="茗韵" /></div>
      <!-- 主标语区：标题 + 副标题 + 行动按钮 -->
      <div class="shop-container hero-content">
        <p class="hero-eyebrow">— 茗韵茶庄 · MINGYUN TEA —</p>
        <h1 class="hero-title">一盏清茶，品味东方</h1>
        <p class="hero-subtitle">严选产地好茶，从茶园到茶杯的匠心之旅</p>
        <div class="hero-actions">
          <!-- 主按钮：进入全部商品页 -->
          <router-link to="/products">
            <el-button size="large" class="hero-btn-primary">精选好茶</el-button>
          </router-link>
          <!-- 次按钮：进入绿茶类目（category_id=1） -->
          <router-link to="/products?category_id=1">
            <el-button size="large" class="hero-btn-outline">当季新茶</el-button>
          </router-link>
        </div>
      </div>
    </section>

    <!-- 特色服务 -->
    <section class="shop-container features">
      <!-- 卖点卡片：原产地直供 -->
      <div class="feature-card">
        <TeaIcon name="leaf" class="feature-icon" />
        <h4>原产地直供</h4>
        <p>每一片茶叶都来自核心产区</p>
      </div>
      <!-- 卖点卡片：匠心制作 -->
      <div class="feature-card">
        <TeaIcon name="mountain" class="feature-icon" />
        <h4>匠心制作</h4>
        <p>传统工艺，手工精制</p>
      </div>
      <!-- 卖点卡片：保鲜包装 -->
      <div class="feature-card">
        <TeaIcon name="box" class="feature-icon" />
        <h4>保鲜包装</h4>
        <p>氮气锁鲜，品质保证</p>
      </div>
      <!-- 卖点卡片：品质承诺 -->
      <div class="feature-card">
        <TeaIcon name="shield" class="feature-icon" />
        <h4>品质承诺</h4>
        <p>不满意，七天无理由退换</p>
      </div>
    </section>

    <!-- 商品推荐 -->
    <section class="shop-container">
      <!-- 区块标题 -->
      <div class="section-header">
        <h2>热门推荐</h2>
        <p class="section-desc">精心甄选，为您奉上一杯好茶</p>
        <router-link to="/products" class="view-all">查看全部 →</router-link>
      </div>

      <!-- 加载中：展示 8 张骨架屏占位 -->
      <ProductSkeleton v-if="loading" :count="8" />
      <!-- 加载完成：商品卡片网格 -->
      <div v-else class="product-grid">
        <!-- 每张商品卡片：点击跳转商品详情页 -->
        <div
          v-for="item in products"
          :key="item.id"
          class="product-card"
          @click="$router.push(`/product/${item.id}`)"
        >
          <!-- 卡片图片区 -->
          <div class="card-img-wrap">
            <!-- 商品主图：懒加载，失败时用茶碗图标占位 -->
            <el-image :src="item.images?.[0] || ''" fit="cover" class="card-img" lazy>
              <template #error>
                <div class="image-placeholder">
                  <TeaIcon name="bowl" class="placeholder-icon" />
                </div>
              </template>
            </el-image>
            <!-- 图片上的印章徽标：类目名 + 推导徽标 -->
            <div class="card-tags">
              <span class="seal-tag tea" v-if="item.category_name">{{ item.category_name }}</span>
              <span
                v-for="b in cardBadges(item)"
                :key="b.text"
                class="seal-tag"
                :class="b.cls"
              >{{ b.text }}</span>
            </div>
            <!-- 悬停浮层："查看详情"提示 -->
            <div class="card-hover">
              <span class="hover-btn">查看详情 →</span>
            </div>
          </div>
          <!-- 卡片文字区 -->
          <div class="card-body">
            <h3 class="card-name">{{ item.name }}</h3>
            <p class="card-desc">{{ item.description || '品质好茶，值得品尝' }}</p>
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
        <el-button type="primary" @click="$router.push('/products')">去逛逛</el-button>
      </el-empty>
    </section>

    <!-- 为你推荐 -->
    <section class="shop-container" v-if="recommended.length > 0">
      <div class="section-header">
        <h2>为你推荐</h2>
        <p class="section-desc">根据您的偏好与购买记录，精心挑选</p>
      </div>
      <div class="product-grid">
        <div
          v-for="item in recommended"
          :key="'rec-' + item.id"
          class="product-card"
          @click="$router.push(`/product/${item.id}`)"
        >
          <div class="card-img-wrap">
            <el-image :src="item.images?.[0] || ''" fit="cover" class="card-img" lazy>
              <template #error>
                <div class="image-placeholder"><TeaIcon name="bowl" class="placeholder-icon" /></div>
              </template>
            </el-image>
            <div class="card-hover"><span class="hover-btn">查看详情 →</span></div>
          </div>
          <div class="card-body">
            <h3 class="card-name">{{ item.name }}</h3>
            <div class="card-footer">
              <span class="card-price"><i>¥</i>{{ item.price?.toFixed(2) }}</span>
              <span class="card-sold">已售 {{ item.total_sales || 0 }}+</span>
            </div>
            <p class="rec-reason" v-if="item.reason">{{ item.reason }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 品牌故事 -->
    <section class="story-section">
      <div class="shop-container story-inner">
        <!-- 左侧品牌叙事文案 -->
        <div class="story-copy">
          <p class="story-eyebrow">— 匠心 · CRAFT —</p>
          <h2 class="story-title">从一片叶子，到一杯茶</h2>
          <p class="story-text">
            茗韵茶庄的每一款茶，都来自核心原产地的当季鲜叶。
            我们相信，好茶是山场、气候与时间共同写下的诗——
            而我们要做的，只是把这份自然之味，完完整整地交到你手中。
          </p>
          <img src="/seal.svg" alt="茗韵" class="story-seal" />
        </div>
        <!-- 右侧制茶四艺步骤列表 -->
        <div class="story-steps">
          <div v-for="(s, i) in craftSteps" :key="s.name" class="story-step">
            <span class="step-no">0{{ i + 1 }}</span>
            <div class="step-body">
              <h4>{{ s.name }}</h4>
              <p>{{ s.desc }}</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 品类展示区 -->
    <section class="category-showcase">
      <div class="shop-container">
        <div class="section-header light">
          <h2>茶类精选</h2>
          <p class="section-desc">六大茶类，总有一款适合您</p>
        </div>
        <!-- 六大茶类快捷入口：点击跳转对应类目商品列表 -->
        <div class="category-grid">
          <div class="cate-item" v-for="c in featuredCates" :key="c.name" @click="$router.push(`/products?category_id=${c.id}`)">
            <!-- 印章色块：文字类名首字 -->
            <span class="cate-seal" :class="{ dark: c.dark }" :style="{ background: c.color }">{{ c.char }}</span>
            <span class="cate-name">{{ c.name }}</span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
// ── 依赖引入 ──
import { ref, onMounted } from 'vue' // Vue 响应式与生命周期
import { getProducts, getRecommended, type Product } from '@/api/products' // 商品列表 API 与类型
import ProductSkeleton from '@/components/ProductSkeleton.vue' // 商品骨架屏组件
import TeaIcon from '@/components/TeaIcon.vue' // 主题图标组件
import EmptyTea from '@/components/EmptyTea.vue' // 空状态组件

// ── 状态定义 ──
const products = ref<Product[]>([]) // 首页热门推荐商品列表
const recommended = ref<Product[]>([]) // 为你推荐商品列表
const loading = ref(false) // 商品数据加载中标记

// ── 六大茶类展示数据 ──
// 静态配置：类目名称/印章首字/类目 ID/印章色块颜色，dark 标记深色底配浅字
const featuredCates = [
  { name: '绿茶', char: '绿', id: 1, color: '#3f5d4a' },
  { name: '红茶', char: '红', id: 2, color: '#a8433c' },
  { name: '乌龙茶', char: '乌', id: 3, color: '#8a6a45' },
  { name: '普洱茶', char: '普', id: 4, color: '#4a3f35' },
  { name: '白茶', char: '白', id: 5, color: '#e6ddca', dark: true },
  { name: '花茶', char: '花', id: 6, color: '#b08d57' },
]

// 制茶四艺（品牌叙事）
// 品牌故事区展示的制茶工艺步骤（步骤序号/名称/描述）
const craftSteps = [
  { name: '采青', desc: '清明前后，只取一芽一叶，人工采摘' },
  { name: '萎凋', desc: '竹匾薄摊，让水分与青气自然散去' },
  { name: '揉捻', desc: '以手为器，塑造茶形，唤醒内质' },
  { name: '干燥', desc: '炭火烘焙，锁住茶香与鲜爽' },
]

// ── 商品印章徽标推导 ──
// 从真实商品数据推导印章徽标（名称/销量），不虚构信息
// 作用：根据商品名称关键词（明前/雨前/头采/古树/特级/礼盒）与销量阈值
//       生成印章徽标数组（最多取前 2 个），用于商品卡片角标展示
// 参数：item —— 商品对象（Product）；返回值：徽标数组 [{ text, cls }]
function cardBadges(item: Product): { text: string; cls: string }[] {
  const tags: { text: string; cls: string }[] = []
  const n = item.name || ''
  if (n.includes('明前')) tags.push({ text: '明前', cls: 'soft' })
  if (n.includes('雨前')) tags.push({ text: '雨前', cls: 'soft' })
  if (n.includes('头采')) tags.push({ text: '头采', cls: 'gold' })
  if (n.includes('古树')) tags.push({ text: '古树', cls: 'cinnabar' })
  if (n.includes('特级')) tags.push({ text: '特级', cls: 'soft' })
  if (n.includes('礼盒')) tags.push({ text: '礼盒', cls: 'gold' })
  if ((item.total_sales || 0) >= 300) tags.push({ text: '热销', cls: 'cinnabar' }) // 销量 ≥300 打"热销"标
  return tags.slice(0, 2) // 最多展示 2 个徽标，避免遮挡图片
}

// ── 页面挂载后拉取热门推荐 ──
// 作用：请求商品列表（每页 8 条）作为首页"热门推荐"，失败时保持空列表
onMounted(async () => {
  loading.value = true
  try {
    const res = await getProducts({ page_size: 8 }) // 拉取前 8 个商品
    products.value = (res.data.data?.items || []).slice(0, 8)
  } catch {
    products.value = [] // 请求失败展示空状态
  } finally {
    loading.value = false
  }
  try {
    const res = await getRecommended(8)
    recommended.value = res.data.data?.items || []
  } catch {
    recommended.value = []
  }
})
</script>

<style scoped>
/* ── 首页容器：底部留白 ── */
.home-page { padding-bottom: 20px; }

/* ── Hero Banner ── */
/* 首屏横幅：茶山墨绿渐变 + 双层金色/茶青光晕，内容居中，溢出隐藏 */
.hero-banner {
  position: relative;
  min-height: 460px;
  padding: 96px 20px 116px;
  text-align: center;
  overflow: hidden;
  background:
    radial-gradient(1200px 520px at 16% -12%, rgba(176, 141, 87, 0.22), transparent 62%),
    radial-gradient(900px 480px at 86% 112%, rgba(62, 93, 74, 0.55), transparent 66%),
    linear-gradient(150deg, #20341f 0%, #314a3b 38%, #243c26 68%, #182b18 100%);
}

/* 云雾层 */
/* 背景云雾：模糊椭圆，缓慢左右漂移循环动画 */
.hero-mist {
  position: absolute;
  border-radius: 50%;
  filter: blur(46px);
  opacity: 0.5;
  animation: mist-drift 16s ease-in-out infinite alternate;
}

/* 左下方云团 */
.mist-a {
  width: 560px;
  height: 220px;
  left: -120px;
  bottom: 24px;
  background: radial-gradient(ellipse, rgba(250, 246, 239, 0.34), transparent 70%);
}

/* 右上方云团：延迟 6s 起播形成错落感 */
.mist-b {
  width: 640px;
  height: 260px;
  right: -160px;
  top: 30px;
  background: radial-gradient(ellipse, rgba(250, 246, 239, 0.22), transparent 70%);
  animation-delay: -6s;
}

/* 云雾漂移动画关键帧 */
@keyframes mist-drift {
  from { transform: translateX(-18px) scale(1); }
  to   { transform: translateX(26px) scale(1.08); }
}

/* 飘落的茶叶 */
/* 背景茶叶：叶形圆角块，从顶部旋转飘落循环动画 */
.hero-leaf {
  position: absolute;
  width: 16px;
  height: 26px;
  background: radial-gradient(ellipse at 30% 30%, #6b8f72, #334d38 70%);
  border-radius: 80% 0 80% 0;
  opacity: 0.55;
  animation: leaf-fall 9s linear infinite;
}

/* 三片茶叶：不同横向位置/尺寸/旋转/起播时间 */
.leaf-1 { left: 12%; top: -30px; animation-delay: 0s; }
.leaf-2 { left: 38%; top: -40px; animation-delay: 3.2s; transform: scale(0.8) rotate(25deg); }
.leaf-3 { left: 74%; top: -36px; animation-delay: 6.1s; transform: scale(1.15) rotate(-15deg); }

/* 茶叶飘落动画关键帧：下坠 + 旋转 + 淡出 */
@keyframes leaf-fall {
  0%   { transform: translateY(0) rotate(0deg); opacity: 0; }
  12%  { opacity: 0.6; }
  100% { transform: translateY(560px) rotate(300deg); opacity: 0; }
}

/* 印章 */
/* 右上角印章：微微旋转并做呼吸缩放动画 */
.hero-seal {
  position: absolute;
  right: 8%;
  top: 50%;
  transform: translateY(-50%) rotate(6deg);
  animation: seal-breathe 5s ease-in-out infinite;
}

.hero-seal img {
  width: 84px;
  height: 84px;
  filter: drop-shadow(0 8px 24px rgba(0, 0, 0, 0.35));
}

/* 印章呼吸动画关键帧 */
@keyframes seal-breathe {
  0%, 100% { transform: translateY(-50%) rotate(6deg) scale(1); }
  50%      { transform: translateY(-50%) rotate(6deg) scale(1.05); }
}

/* 主标语容器：置于装饰层之上 */
.hero-content { position: relative; z-index: 1; }

/* 眉题小字：金色宽字距 */
.hero-eyebrow {
  font-size: 13px;
  letter-spacing: 6px;
  color: rgba(217, 198, 163, 0.9);
  margin-bottom: 18px;
}

/* 主标题：衬线体大字 + 阴影 */
.hero-title {
  font-family: var(--font-serif);
  font-size: 42px;
  font-weight: 700;
  color: #fdf9f0;
  letter-spacing: 10px;
  margin-bottom: 18px;
  text-shadow: 0 4px 24px rgba(0, 0, 0, 0.35);
}

/* 副标题：半透明白 */
.hero-subtitle {
  font-size: 17px;
  color: rgba(250, 246, 239, 0.78);
  margin-bottom: 40px;
  letter-spacing: 3px;
}

/* 行动按钮容器：水平居中 */
.hero-actions {
  display: flex;
  gap: 16px;
  justify-content: center;
}

/* 主按钮：铜金底深色字圆角胶囊 */
.hero-btn-primary {
  background: #b08d57 !important;
  border-color: #b08d57 !important;
  color: #2c2a26 !important;
  font-weight: 600 !important;
  padding: 12px 32px !important;
  font-size: 16px !important;
  border-radius: 24px !important;
}

.hero-btn-primary:hover {
  background: #a17d4a !important;
}

/* 次按钮：透明底白边描边 */
.hero-btn-outline {
  background: transparent !important;
  border: 2px solid rgba(255, 255, 255, 0.5) !important;
  color: #fff !important;
  padding: 12px 32px !important;
  font-size: 16px !important;
  border-radius: 24px !important;
}

.hero-btn-outline:hover {
  border-color: #fff !important;
}

/* ── Features ── */
/* 特色服务区：四列网格（桌面端） */
.features {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-top: 40px;
  margin-bottom: 50px;
}

/* 卖点卡片：居中文字，hover 上浮 */
.feature-card {
  text-align: center;
  background: #fff;
  border-radius: 12px;
  padding: 28px 16px;
  box-shadow: 0 2px 12px rgba(61, 50, 39, 0.05);
  transition: transform 0.2s;
}

.feature-card:hover { transform: translateY(-4px); }

/* 卖点图标：大号主题图标 */
.feature-icon { font-size: 36px; margin-bottom: 12px; }

/* 卖点标题 */
.feature-card h4 {
  font-size: 16px;
  color: #2c2a26;
  margin-bottom: 6px;
}

/* 卖点描述 */
.feature-card p {
  font-size: 13px;
  color: #6b6257;
}

/* ── Section Header ── */
/* 区块标题：居中，上下留白 */
.section-header {
  text-align: center;
  margin: 50px 0 30px;
  position: relative;
}

.section-header h2 {
  font-size: 28px;
  color: #2c2a26;
  margin-bottom: 8px;
  letter-spacing: 2px;
}

.section-header .section-desc {
  color: #6b6257;
  font-size: 14px;
}

/* "查看全部"链接：茶青色 */
.section-header .view-all {
  display: inline-block;
  margin-top: 12px;
  color: #3f5d4a;
  font-size: 14px;
  font-weight: 500;
}

/* ── Product Grid ── */
/* 商品网格：桌面端四列等宽 */
.product-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

/* 平板及以下：商品两列、卖点两列、标题缩小 */
@media (max-width: 960px) {
  .product-grid { grid-template-columns: repeat(2, 1fr); }
  .features { grid-template-columns: repeat(2, 1fr); }
  .hero-title { font-size: 28px; }
}

/* 手机端：首屏压缩内边距，隐藏印章装饰，进一步缩小标题 */
@media (max-width: 768px) {
  .hero-banner {
    padding: 64px 16px 84px;
  }

  .hero-seal {
    display: none;
  }

  .hero-title {
    font-size: 30px;
    letter-spacing: 6px;
  }

  .hero-subtitle {
    font-size: 15px;
  }
}

/* ── 商品卡片 ── */
/* 卡片：白底圆角，hover 上浮 + 阴影加深 */
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

/* 图片容器：固定高度，溢出隐藏 */
.card-img-wrap {
  position: relative;
  width: 100%;
  height: 240px;
  overflow: hidden;
  background: #faf6ef;
}

/* 商品主图：hover 时缓慢放大（视差效果） */
.card-img {
  width: 100%;
  height: 100%;
  transition: transform 0.4s;
}

.product-card:hover .card-img {
  transform: scale(1.05);
}

/* 左上角徽标区：印章类目/推导徽标 */
.card-tags {
  position: absolute;
  top: 12px;
  left: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-width: calc(100% - 24px);
}

/* 底部悬停浮层：默认透明下移，hover 时浮现"查看详情" */
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

/* 图片加载失败占位区 */
.image-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f2ead9;
}

.placeholder-icon { font-size: 48px; }

/* 卡片文字区 */
.card-body {
  padding: 16px;
}

/* 商品名：单行省略 */
.card-name {
  font-size: 15px;
  font-weight: 600;
  color: #2c2a26;
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 商品描述：单行省略 */
.card-desc {
  font-size: 12px;
  color: #6b6257;
  margin-bottom: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 卡片底部：价格 + 销量两端分布 */
.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 价格：朱砂色衬线大字 */
.card-price {
  font-size: 20px;
  color: var(--cinnabar);
  font-weight: 700;
  font-family: var(--font-serif);
}

/* 价格前的 ¥ 符号：小号非斜体 */
.card-price i {
  font-style: normal;
  font-size: 13px;
  margin-right: 1px;
}

/* 销量文案 */
.card-sold {
  font-size: 12px;
  color: #a3967f;
}

/* 推荐理由 */
.rec-reason {
  margin-top: 8px;
  font-size: 11px;
  color: var(--gold-deep);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── Category Showcase ── */
/* 品类展示区：白底区块，顶部留白 */
.category-showcase {
  background: #fff;
  padding: 50px 0 60px;
  margin-top: 50px;
}

/* 该区标题无需额外上边距（白底自带留白） */
.section-header.light { margin-top: 0; }

/* 六大茶类网格：六列等宽（桌面端） */
.category-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
}

/* 品类项：纵向居中排列，hover 上浮 + 茶青边框 */
.cate-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 24px 12px;
  background: #faf6ef;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s;
  border: 2px solid transparent;
}

.cate-item:hover {
  border-color: #3f5d4a;
  background: #e8efe9;
  transform: translateY(-2px);
}

/* 印章色块：方形圆角，带内描边与外阴影 */
.cate-seal {
  width: 46px;
  height: 46px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 700;
  color: var(--paper);
  box-shadow:
    inset 0 0 0 1px rgba(0, 0, 0, 0.12),
    0 4px 12px rgba(74, 61, 43, 0.2);
  transition: transform 0.25s;
}

/* 浅色底（如白茶）使用深色文字 */
.cate-seal.dark { color: var(--ink); }

/* hover 时印章上浮微旋转 */
.cate-item:hover .cate-seal {
  transform: translateY(-3px) rotate(-3deg);
}

/* 类目名称 */
.cate-name {
  font-size: 14px;
  color: #2c2a26;
  font-weight: 500;
}

/* ── 品牌故事 ── */
/* 故事区：深宣纸底 + 上下描边 */
.story-section {
  background:
    radial-gradient(800px 360px at 88% 20%, rgba(176, 141, 87, 0.1), transparent 65%),
    var(--paper-deep);
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  padding: 64px 0;
  margin-top: 50px;
}

/* 故事内容：左右两栏（文案 / 制茶步骤） */
.story-inner {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 56px;
  align-items: center;
}

/* 眉题：金色宽字距 */
.story-eyebrow {
  font-size: 12px;
  letter-spacing: 5px;
  color: var(--gold);
  margin-bottom: 14px;
}

/* 标题：衬线体大号 */
.story-title {
  font-size: 30px;
  letter-spacing: 4px;
  color: var(--ink);
  margin-bottom: 18px;
}

/* 正文：行高 2 倍，限宽更易读 */
.story-text {
  font-size: 14px;
  line-height: 2;
  color: var(--ink-soft);
  max-width: 420px;
}

/* 文案末尾的印章图 */
.story-seal {
  width: 52px;
  height: 52px;
  margin-top: 24px;
  opacity: 0.9;
}

/* 步骤列表：纵向排列 */
.story-steps {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 单个步骤卡：左侧金色竖线装饰，hover 右移 */
.story-step {
  display: flex;
  align-items: flex-start;
  gap: 18px;
  background: var(--card);
  border-radius: var(--radius-md);
  padding: 18px 22px;
  box-shadow: var(--shadow-sm);
  border-left: 3px solid var(--gold);
  transition: transform 0.25s, box-shadow 0.25s;
}

.story-step:hover {
  transform: translateX(4px);
  box-shadow: var(--shadow-md);
}

/* 步骤序号：衬线金色 */
.step-no {
  font-family: var(--font-serif);
  font-size: 22px;
  font-weight: 700;
  color: var(--gold);
  line-height: 1.2;
}

/* 步骤名称与描述 */
.step-body h4 {
  font-size: 16px;
  color: var(--ink);
  margin-bottom: 4px;
  letter-spacing: 2px;
}

.step-body p {
  font-size: 13px;
  color: var(--ink-soft);
}

/* 移动端：故事区改为单栏 */
@media (max-width: 768px) {
  .story-inner {
    grid-template-columns: 1fr;
    gap: 36px;
  }
}

/* 移动端：品类网格改为三列 */
@media (max-width: 768px) {
  .category-grid { grid-template-columns: repeat(3, 1fr); }
}
</style>
