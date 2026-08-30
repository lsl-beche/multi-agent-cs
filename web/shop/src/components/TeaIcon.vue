<!--
  ═══════════════════════════════════════════════════════════
  茗韵茶庄商城 · 主题图标组件（TeaIcon.vue）
  ───────────────────────────────────────────────────────────
  职责说明：
    以 SVG 绘制的"茶"主题线性图标集，通过 name 属性选择不同图形：
      - leaf      茶叶（特色服务"原产地直供"）
      - mountain  茶山（特色服务"匠心制作"）
      - box       保鲜包装（特色服务）
      - shield    品质承诺（特色服务）
      - bowl      茶碗（商品图加载失败的占位图标 / 空状态）
    图标使用 currentColor 描边，颜色随父元素文字颜色自适应；
    尺寸通过 font-size 控制（width/height 为 1em）。
  ═══════════════════════════════════════════════════════════
-->
<template>
  <!-- 图标根节点：统一 viewBox 24x24，线性风格（stroke 描边、圆角端点/连接） -->
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.6"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="tea-icon"
    aria-hidden="true"
  >
    <!-- 茶叶图标：叶片轮廓 + 叶脉线 -->
    <template v-if="name === 'leaf'">
      <path d="M4.5 19.5C4.5 11 11 4.5 19.5 4.5C19.5 13 13 19.5 4.5 19.5Z" />
      <path d="M4.5 19.5L11.5 12.5" />
      <path d="M15.5 7.5C13.5 9 12 10.5 11 12" />
    </template>
    <!-- 茶山图标：连绵山峦 + 地平线 + 云气 -->
    <template v-else-if="name === 'mountain'">
      <path d="M3 18L9 7.5L13 13.5L16 10L21 18H3Z" />
      <path d="M4 21H20" />
      <path d="M6.5 15.5C8 14.8 10 15.2 12 16" />
    </template>
    <!-- 保鲜包装图标：立体纸盒线条 -->
    <template v-else-if="name === 'box'">
      <path d="M3 8L12 3.5L21 8V16L12 20.5L3 16V8Z" />
      <path d="M3 8L12 12.5L21 8" />
      <path d="M12 12.5V20.5" />
    </template>
    <!-- 品质承诺图标：盾牌 + 对勾 -->
    <template v-else-if="name === 'shield'">
      <path d="M12 3L19.5 5.8V11C19.5 15.3 16.3 18.7 12 20.4C7.7 18.7 4.5 15.3 4.5 11V5.8L12 3Z" />
      <path d="M9 11.5L11.2 13.7L15.2 9.2" />
    </template>
    <!-- 茶碗图标（占位/空状态）：碗身 + 碗口 + 碗托 + 热气 -->
    <template v-else-if="name === 'bowl'">
      <path d="M4 11.5H20C20 15.8 16.4 19.2 12 19.2C7.6 19.2 4 15.8 4 11.5Z" />
      <path d="M3 11.5H21" />
      <path d="M8.5 21H15.5" />
      <path d="M8.2 5.8V7.6M12 4.8V7.6M15.8 5.8V7.6" />
    </template>
  </svg>
</template>

<script setup lang="ts">
// 组件属性声明：name 为必填项，限定图标类型（联合类型约束可选值）
defineProps<{ name: 'leaf' | 'mountain' | 'box' | 'shield' | 'bowl' }>()
</script>

<style scoped>
/* ── 图标尺寸与基线对齐：宽高跟随字号，垂直方向微调对齐文字基线 ── */
.tea-icon {
  width: 1em;
  height: 1em;
  display: inline-block;
  vertical-align: -0.15em;
}
</style>
