<script setup lang="ts">
withDefaults(
  defineProps<{
    loading?: boolean
    error?: string
    empty?: boolean
  }>(),
  { loading: false, error: '', empty: false },
)
</script>

<template>
  <div v-if="loading" class="shared-async-state">加载中...</div>
  <div v-else-if="error" class="shared-async-state shared-async-error">{{ error }}</div>
  <div v-else-if="empty" class="shared-async-state">暂无数据</div>
  <slot v-else />
</template>

