<template>
  <div class="health-view">
    <div class="header-actions">
      <el-button type="primary" plain icon="Refresh" @click="loadHealth" :loading="loading">
        手动刷新
      </el-button>
      <span class="refresh-info">
        数据每 60 秒自动刷新，最后更新时间：{{ lastUpdated || '尚未更新' }}
      </span>
    </div>

    <el-row :gutter="20">
      <el-col :span="12" v-for="(item, index) in healthItems" :key="index" class="health-col">
        <el-card shadow="hover" class="health-card" :class="item.status === 'error' ? 'error-card' : ''">
          <div class="health-header">
            <div class="health-title">
              <span class="status-dot" :class="item.status"></span>
              {{ item.name }}
            </div>
            <div class="health-latency" v-if="item.latency_ms !== null && item.latency_ms !== undefined">
              {{ item.latency_ms.toFixed(0) }} ms
            </div>
          </div>
          <div class="health-body">
            <div class="health-status-text" :class="item.status">
              {{ item.status === 'ok' ? '正常运行' : '发生异常' }}
            </div>
            <div class="health-detail" v-if="item.detail">
              <el-alert
                :title="item.detail"
                :type="item.status === 'ok' ? 'info' : 'error'"
                :closable="false"
                class="detail-alert"
              />
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { getHealth } from '@/api/health'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const healthItems = ref<any[]>([])
const lastUpdated = ref('')
let timer: ReturnType<typeof setInterval> | null = null

const loadHealth = async () => {
  loading.value = true
  try {
    const { data } = await getHealth()
    healthItems.value = data.items || []
    
    const now = new Date()
    lastUpdated.value = now.toLocaleTimeString('zh-CN')
  } catch (error) {
    ElMessage.error('获取系统健康状态失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadHealth()
  // 60秒自动刷新
  timer = setInterval(loadHealth, 60000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.header-actions {
  display: flex;
  align-items: center;
  margin-bottom: 24px;
}

.refresh-info {
  margin-left: 16px;
  font-size: 13px;
  color: #909399;
}

.health-col {
  margin-bottom: 20px;
}

.health-card {
  height: 100%;
  border-radius: 8px;
  transition: all 0.3s;
}

.error-card {
  border-color: #F56C6C;
}

.health-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 12px;
  border-bottom: 1px solid #EBEEF5;
  margin-bottom: 12px;
}

.health-title {
  font-size: 16px;
  font-weight: 500;
  display: flex;
  align-items: center;
}

.status-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  margin-right: 12px;
  box-shadow: 0 0 4px rgba(0, 0, 0, 0.1);
}

.status-dot.ok {
  background-color: #67C23A;
  box-shadow: 0 0 6px rgba(103, 194, 58, 0.6);
}

.status-dot.error {
  background-color: #F56C6C;
  box-shadow: 0 0 6px rgba(245, 108, 108, 0.6);
}

.health-latency {
  font-size: 14px;
  color: #909399;
  background-color: #f4f4f5;
  padding: 2px 8px;
  border-radius: 12px;
}

.health-status-text {
  font-size: 18px;
  font-weight: bold;
  margin-bottom: 12px;
}

.health-status-text.ok {
  color: #67C23A;
}

.health-status-text.error {
  color: #F56C6C;
}

.health-detail {
  margin-top: 12px;
}

.detail-alert {
  padding: 8px 16px;
}
</style>
