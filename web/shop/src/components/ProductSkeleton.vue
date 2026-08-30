<!--
  ═══════════════════════════════════════════════════════════
  茗韵茶庄商城 · 商品卡片骨架屏（ProductSkeleton.vue）
  ───────────────────────────────────────────────────────────
  职责说明：
    在商品数据异步加载期间展示的占位卡片，使用"微光扫过"（shimmer）
    动画模拟内容加载状态，避免页面白屏/跳动，提升首屏体验。
    通过 count 属性控制占位卡片数量，网格布局与真实商品卡片保持一致。
  ═══════════════════════════════════════════════════════════
-->
<template>
  <!-- 骨架网格容器：与真实商品列表 grid 布局对齐 -->
  <div class="skeleton-grid">
    <!-- 循环生成 count 个骨架卡片 -->
    <div v-for="i in count" :key="i" class="skeleton-card">
      <!-- 图片占位区：带微光动画 -->
      <div class="sk-img shimmer"></div>
      <!-- 文字占位区：三条不同宽度的横线模拟标题/描述/价格 -->
      <div class="sk-body">
        <div class="sk-line w-70 shimmer"></div>
        <div class="sk-line w-40 shimmer"></div>
        <div class="sk-line w-55 shimmer"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// 组件属性：count 为骨架卡片数量，默认渲染 8 张（withDefaults 提供默认值）
withDefaults(defineProps<{ count?: number }>(), { count: 8 })
</script>

<style scoped>
/* ── 骨架网格：桌面端 4 列 ── */
.skeleton-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

/* ── 平板及以下：2 列 ── */
@media (max-width: 960px) {
  .skeleton-grid { grid-template-columns: repeat(2, 1fr); }
}

/* ── 骨架卡片容器：与真实商品卡片同款背景/圆角/阴影 ── */
.skeleton-card {
  background: var(--card);
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}

/* ── 图片占位区：固定高度，深宣纸底色 ── */
.sk-img {
  height: 240px;
  background: var(--paper-deep);
}

/* ── 文字占位区：内边距 + 纵向排列 ── */
.sk-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ── 占位横线：短条状灰色块 ── */
.sk-line {
  height: 14px;
  border-radius: 4px;
  background: var(--paper-deep);
}

/* ── 横线宽度变体（模拟不同长度文字） ── */
.w-70 { width: 70%; }
.w-40 { width: 40%; }
.w-55 { width: 55%; }

/* ── 微光扫过效果：在元素上覆盖一层渐变光带 ── */
.shimmer {
  position: relative;
  overflow: hidden;
}

/* 光带本体：从左侧(-100%)水平扫过，循环播放 */
.shimmer::after {
  content: '';
  position: absolute;
  inset: 0;
  transform: translateX(-100%);
  background: linear-gradient(90deg, transparent, rgba(250, 246, 239, 0.75), transparent);
  animation: shimmer 1.4s infinite;
}

/* ── 微光动画关键帧：光带从左侧扫到右侧 ── */
@keyframes shimmer {
  100% { transform: translateX(100%); }
}
</style>
