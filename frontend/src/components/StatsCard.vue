<template>
  <el-card shadow="hover" class="stats-card">
    <div class="stats-content">
      <div class="stats-left">
        <div class="stats-title">{{ title }}</div>
        <div class="stats-value">
          <span :style="{ color }">{{ value }}</span>
          <span class="stats-suffix" v-if="suffix">{{ suffix }}</span>
        </div>
      </div>
      <div class="stats-right">
        <el-icon :size="48" :color="color" class="stats-icon">
          <component :is="icon" />
        </el-icon>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  value: number | string
  suffix?: string
  icon: string
  color: string
}>()
</script>

<style scoped>
.stats-card {
  border-radius: 8px;
}

.stats-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stats-title {
  font-size: 14px;
  color: #909399;
  margin-bottom: 8px;
}

.stats-value {
  font-size: 28px;
  font-weight: bold;
}

.stats-suffix {
  font-size: 14px;
  margin-left: 4px;
  color: #606266;
  font-weight: normal;
}

.stats-icon {
  opacity: 0.8;
}
</style>
