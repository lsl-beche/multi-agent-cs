<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import Layout from '@/components/Layout.vue'
import { AppErrorBoundary } from '@shared'

const auth = useAuthStore()
</script>

<template>
  <AppErrorBoundary>
    <router-view v-if="!auth.token" />
    <Layout v-else />
  </AppErrorBoundary>
</template>
