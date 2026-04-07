<template>
  <el-tag :type="type" :size="size" :effect="effect">
    {{ label || status }}
  </el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    status: string
    size?: 'large' | 'default' | 'small'
    effect?: 'dark' | 'light' | 'plain'
  }>(),
  {
    size: 'small',
    effect: 'light'
  }
)

const type = computed(() => {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info' | 'primary'> = {
    DONE: 'success',
    FAILED: 'danger',
    RUNNING: 'warning',
    PENDING: 'info',
    UPLOAD_OK: 'primary',
    IMAGE_OK: 'primary',
    COPY_OK: 'primary'
  }
  return map[props.status] || 'info'
})

const label = computed(() => {
  const map: Record<string, string> = {
    DONE: '已完成',
    FAILED: '失败',
    RUNNING: '进行中',
    PENDING: '待处理'
  }
  return map[props.status] || props.status
})
</script>
