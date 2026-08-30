<!--
  ═══════════════════════════════════════════════════════════
  茗韵茶庄商城 · 空状态组件（EmptyTea.vue）
  ───────────────────────────────────────────────────────────
  职责说明：
    以"茶碗"主题 SVG 插画 + 提示文案组成的空状态占位组件，
    用于购物车为空、暂无商品等场景，替代 Element Plus 默认的 el-empty 图片。
    通过默认插槽 <slot> 支持外部自定义提示文案（不传时使用内置文案）。
  ═══════════════════════════════════════════════════════════
-->
<template>
  <div class="empty-tea">
    <!-- 茶碗主题 SVG 插画：使用设计系统 CSS 变量着色（茶青/铜金/宣纸色调），
         circle 为背景圆环，path 绘制碗身、碗口、热气与茶叶轮廓 -->
    <svg viewBox="0 0 120 120" fill="none" class="empty-svg" aria-hidden="true">
      <!-- 背景圆环：茶青浅底填充 + 铜金描边 -->
      <circle cx="60" cy="60" r="50" fill="var(--tea-soft)" stroke="var(--gold-soft)" stroke-width="1.5" />
      <!-- 碗身：暖白卡片填充 + 茶青描边 -->
      <path
        d="M42 68H78C78 79.5 70 87 60 87C50 87 42 79.5 42 68Z"
        fill="var(--card)"
        stroke="var(--tea)"
        stroke-width="2"
        stroke-linejoin="round"
      />
      <!-- 碗口：茶青横线 -->
      <path d="M38 68H82" stroke="var(--tea)" stroke-width="2" stroke-linecap="round" />
      <!-- 碗底托：铜金横线 -->
      <path d="M50 89H70" stroke="var(--gold)" stroke-width="2" stroke-linecap="round" />
      <!-- 热腾的茶气：碗口上方三竖短线 -->
      <path d="M52 52V55M60 50V55M68 52V55" stroke="var(--gold-soft)" stroke-width="2" stroke-linecap="round" />
      <!-- 两侧茶叶装饰：弯曲的叶形轮廓 -->
      <path
        d="M46 46C47.5 41 56 41 57 46M74 42C75.5 37 84 37 85 42"
        stroke="var(--gold-soft)"
        stroke-width="2"
        stroke-linecap="round"
        opacity="0.8"
      />
    </svg>
    <!-- 空状态文案：默认提示"这里还空着，去逛逛吧"，可通过插槽自定义 -->
    <p class="empty-text"><slot>这里还空着，去逛逛吧</slot></p>
  </div>
</template>

<style scoped>
/* ── 空状态整体布局：垂直居中排列 ── */
.empty-tea {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

/* ── SVG 插画尺寸 ── */
.empty-svg {
  width: 120px;
  height: 120px;
}

/* ── 文案样式：次级文字色，字间距拉开呈现雅致感 ── */
.empty-text {
  font-size: 13px;
  color: var(--ink-soft);
  letter-spacing: 1px;
}
</style>
