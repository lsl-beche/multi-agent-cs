<script setup lang="ts" generic="T extends Record<string, unknown>">
import { ElTable } from 'element-plus'

defineProps<{
  rows: T[]
  loading?: boolean
}>()
</script>

<template>
  <el-table :data="rows" v-loading="loading" stripe>
    <slot />
  </el-table>
</template>
