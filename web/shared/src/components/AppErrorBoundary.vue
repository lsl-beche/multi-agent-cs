<script setup lang="ts">
import { onErrorCaptured, ref } from 'vue'

const hasError = ref(false)
const errorMessage = ref('')

onErrorCaptured((error) => {
  hasError.value = true
  errorMessage.value = (error as Error).message || String(error)
  console.error('[AppErrorBoundary]', error)
  return false
})

function retry() {
  hasError.value = false
  errorMessage.value = ''
  window.location.reload()
}
</script>

<template>
  <div v-if="hasError" class="shared-error-boundary">
    <h3>页面加载失败</h3>
    <p>{{ errorMessage }}</p>
    <button type="button" @click="retry">重新加载</button>
  </div>
  <slot v-else />
</template>

