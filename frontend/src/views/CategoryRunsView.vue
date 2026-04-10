<template>
  <div class="category-runs-view">
    <!-- Action Bar -->
    <el-card shadow="never" class="action-card">
      <div class="action-bar">
        <div class="left">
          <el-tag :type="isRunning ? 'warning' : 'info'" size="large" effect="dark">
            {{ isRunning ? '运行中' : '空闲' }}
          </el-tag>
          <span v-if="isRunning && currentBatch" class="progress-text">
            {{ doneCount }}/{{ currentBatch.tasks.length }} 完成
          </span>
        </div>
        <div class="right">
          <el-button
            type="primary"
            icon="VideoPlay"
            :disabled="isRunning"
            :loading="triggering"
            @click="handleTrigger"
          >
            立即触发
          </el-button>
          <el-button
            type="danger"
            icon="SwitchButton"
            :disabled="!isRunning"
            @click="handleStop"
          >
            终止
          </el-button>
          <el-switch
            v-model="autoRefresh"
            active-text="自动刷新"
            style="margin-left: 16px"
          />
        </div>
      </div>
    </el-card>

    <!-- Live Progress -->
    <el-card v-if="isRunning && currentBatch" shadow="never" class="progress-card">
      <template #header>
        <span>当前进度 · 批次 {{ currentBatch.batch_id }}</span>
      </template>
      <el-progress
        :percentage="progressPct"
        :stroke-width="20"
        :text-inside="true"
        striped
        striped-flow
        style="margin-bottom: 16px"
      />
      <el-table :data="currentBatch.tasks" stripe border size="small">
        <el-table-column prop="category_name" label="分类" width="130" />
        <el-table-column prop="product_line" label="产品线" width="120" />
        <el-table-column label="步骤" width="320">
          <template #default="{ row }">
            <el-steps :active="stepIndex(row.step)" finish-status="success" simple style="margin: 0">
              <el-step title="匹配" />
              <el-step title="文案" />
              <el-step title="生图" />
              <el-step title="上传" />
              <el-step title="注册" />
            </el-steps>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="headline" label="标题" min-width="180" show-overflow-tooltip />
        <el-table-column label="耗时" width="80" align="right">
          <template #default="{ row }">
            {{ row.duration_seconds ? row.duration_seconds.toFixed(1) + 's' : '-' }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- History -->
    <el-card shadow="never" class="history-card">
      <template #header>
        <div class="history-header">
          <span>历史记录</span>
          <el-date-picker
            v-model="historyDate"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
            @change="loadBatches"
            style="width: 160px"
          />
        </div>
      </template>

      <el-empty v-if="batches.length === 0" description="暂无记录" />

      <div v-for="batch in batches" :key="batch.batch_id" class="batch-section">
        <div class="batch-header" @click="toggleBatch(batch.batch_id)">
          <span class="batch-title">
            批次 {{ batch.batch_id }}
            <el-tag size="small" type="success">{{ batch.done }} 成功</el-tag>
            <el-tag v-if="batch.failed > 0" size="small" type="danger">{{ batch.failed }} 失败</el-tag>
            <el-tag size="small" type="info">共 {{ batch.total }}</el-tag>
          </span>
          <el-icon>
            <ArrowDown v-if="!expandedBatches.has(batch.batch_id)" />
            <ArrowUp v-else />
          </el-icon>
        </div>
        <el-table
          v-if="expandedBatches.has(batch.batch_id)"
          :data="batchDetails[batch.batch_id] || []"
          v-loading="loadingDetail === batch.batch_id"
          stripe
          border
          size="small"
          style="margin-top: 8px"
        >
          <el-table-column prop="category_name" label="分类" width="130" />
          <el-table-column prop="product_line" label="产品线" width="120" />
          <el-table-column label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)" size="small">
                {{ statusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="headline" label="标题" min-width="180" show-overflow-tooltip />
          <el-table-column label="产品" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.products?.join('、') || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="耗时" width="80" align="right">
            <template #default="{ row }">
              {{ row.duration_seconds ? row.duration_seconds.toFixed(1) + 's' : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="error_msg" label="错误信息" min-width="150" show-overflow-tooltip />
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getCurrent,
  listBatches,
  getBatchDetail,
  triggerPipeline,
  stopPipeline,
} from '@/api/categoryRuns'

// --- State ---
const currentBatch = ref<any>(null)
const isRunning = ref(false)
const triggering = ref(false)
const autoRefresh = ref(true)
const historyDate = ref(new Date().toISOString().slice(0, 10))
const batches = ref<any[]>([])
const expandedBatches = ref(new Set<string>())
const batchDetails = ref<Record<string, any[]>>({})
const loadingDetail = ref('')

let timer: ReturnType<typeof setInterval> | null = null

// --- Computed ---
const doneCount = computed(() =>
  currentBatch.value?.tasks?.filter((t: any) => t.status === 'DONE').length ?? 0
)
const progressPct = computed(() => {
  if (!currentBatch.value?.tasks?.length) return 0
  return Math.round((doneCount.value / currentBatch.value.tasks.length) * 100)
})

// --- Helpers ---
function stepIndex(step: string): number {
  const steps: Record<string, number> = {
    matching: 0, content: 1, image: 2, uploading: 3, registering: 4, done: 5,
  }
  return steps[step] ?? 0
}

function statusType(status: string): 'success' | 'danger' | 'warning' | 'info' {
  const map: Record<string, 'success' | 'danger' | 'warning' | 'info'> = {
    DONE: 'success', FAILED: 'danger', RUNNING: 'warning', PENDING: 'info',
  }
  return map[status] || 'info'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    DONE: '完成', FAILED: '失败', RUNNING: '进行中', PENDING: '等待中',
  }
  return map[status] || status
}

// --- Data loading ---
async function loadCurrent() {
  try {
    const { data } = await getCurrent()
    currentBatch.value = data
    isRunning.value = data !== null && data !== ''
  } catch {
    isRunning.value = false
  }
}

async function loadBatches() {
  try {
    const { data } = await listBatches({ date: historyDate.value || undefined })
    batches.value = data.items || []
  } catch {
    batches.value = []
  }
}

async function toggleBatch(batchId: string) {
  if (expandedBatches.value.has(batchId)) {
    expandedBatches.value.delete(batchId)
    return
  }
  expandedBatches.value.add(batchId)
  if (!batchDetails.value[batchId]) {
    loadingDetail.value = batchId
    try {
      const { data } = await getBatchDetail(batchId)
      batchDetails.value[batchId] = data?.tasks || []
    } catch {
      batchDetails.value[batchId] = []
    }
    loadingDetail.value = ''
  }
}

// --- Actions ---
async function handleTrigger() {
  triggering.value = true
  try {
    await triggerPipeline()
    ElMessage.success('流水线已触发')
    autoRefresh.value = true
    await loadCurrent()
  } catch {
    ElMessage.error('触发失败')
  }
  triggering.value = false
}

async function handleStop() {
  try {
    await stopPipeline()
    ElMessage.info('已发送终止信号')
  } catch {
    ElMessage.error('终止失败')
  }
}

// --- Polling ---
function startPolling() {
  stopPolling()
  timer = setInterval(async () => {
    if (document.hidden || !autoRefresh.value) return
    await loadCurrent()
    if (!isRunning.value) {
      await loadBatches()
    }
  }, 3000)
}

function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

onMounted(async () => {
  await Promise.all([loadCurrent(), loadBatches()])
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.category-runs-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.action-bar .left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.action-bar .right {
  display: flex;
  align-items: center;
}
.progress-text {
  font-size: 14px;
  color: #606266;
}
.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.batch-section {
  margin-bottom: 16px;
}
.batch-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  cursor: pointer;
  user-select: none;
}
.batch-header:hover {
  background: #ebeef5;
}
.batch-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}
</style>
