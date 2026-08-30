<script setup lang="ts">
withDefaults(defineProps<{ title?: string; description?: string }>(), { title: '', description: '' })
</script>

<template>
  <section class="shared-page-container">
    <header v-if="title || description" class="shared-page-header">
      <h2 v-if="title">{{ title }}</h2>
      <p v-if="description">{{ description }}</p>
    </header>
    <div class="shared-page-content">
      <slot />
    </div>
  </section>
</template>

