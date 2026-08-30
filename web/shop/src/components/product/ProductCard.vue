<script setup lang="ts">
import { defineEmits, defineProps } from 'vue'
import TeaIcon from '@/components/TeaIcon.vue'
import type { Product } from '@/api/products'

const props = defineProps<{ item: Product }>()
const emit = defineEmits<{ (e: 'click'): void }>()

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
</script>

<template>
  <div class="product-card" @click="emit('click')">
    <div class="card-img-wrap">
      <el-image :src="props.item.images?.[0] || ''" fit="cover" class="card-img" lazy>
        <template #error>
          <div class="image-placeholder"><TeaIcon name="bowl" class="placeholder-icon" /></div>
        </template>
      </el-image>
      <div class="card-tags">
        <span class="seal-tag tea" v-if="props.item.category_name">{{ props.item.category_name }}</span>
        <span v-for="b in cardBadges(props.item)" :key="b.text" class="seal-tag" :class="b.cls">{{ b.text }}</span>
      </div>
      <div class="card-hover"><span class="hover-btn">查看详情 →</span></div>
    </div>
    <div class="card-body">
      <h3 class="card-name">{{ props.item.name }}</h3>
      <div class="card-footer">
        <span class="card-price"><i>¥</i>{{ props.item.price?.toFixed(2) }}</span>
        <span class="card-sold">已售 {{ props.item.total_sales || 0 }}+</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.product-card { cursor: pointer; transition: transform .2s ease, box-shadow .2s ease; }
.product-card:hover { transform: translateY(-4px); }
.card-img-wrap { position: relative; overflow: hidden; aspect-ratio: 1; }
.card-img { width: 100%; height: 100%; transition: transform .3s ease; }
.product-card:hover .card-img { transform: scale(1.05); }
.card-tags { position: absolute; left: 12px; top: 12px; display: flex; gap: 6px; }
.card-hover { position: absolute; inset: auto 0 0 0; opacity: 0; transition: opacity .2s ease; }
.product-card:hover .card-hover { opacity: 1; }
.card-body { padding: 16px; }
.card-name { margin: 0 0 10px; font-size: 16px; }
.card-footer { display: flex; justify-content: space-between; align-items: center; }
.card-price { color: var(--cinnabar); font-weight: 700; }
.card-price i { font-style: normal; font-size: 13px; margin-right: 1px; }
.card-sold { font-size: 12px; color: var(--ink-soft); opacity: .75; }
</style>
