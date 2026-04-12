<template>
  <div class="category-runs-view">
    <!-- Action bar -->
    <el-card shadow="never" class="action-card">
      <div class="action-bar">
        <div class="left">
          <span class="title">今日栏目计划</span>
          <el-tag v-if="schedule" :type="overallTagType" size="large" effect="plain">
            {{ overallLabel }}
          </el-tag>
          <span v-if="schedule" class="summary-text">
            {{ schedule.done_slots }}/{{ schedule.total_slots }} 完成
          </span>
        </div>
        <div class="right">
          <el-button
            type="primary"
            icon="Calendar"
            :disabled="!!schedule"
            :loading="triggering"
            @click="handleTrigger"
          >
            生成今日计划
          </el-button>
          <el-button
            type="danger"
            icon="SwitchButton"
            :disabled="!hasScheduled"
            @click="handleStop"
          >
            停止剩余
          </el-button>
          <el-switch
            v-model="autoRefresh"
            active-text="自动刷新"
            style="margin-left: 16px"
          />
        </div>
      </div>
    </el-card>

    <!-- Initialising spinner (triggered but no slots yet) -->
    <el-card v-if="initialising" shadow="never" class="init-card">
      <el-icon class="spin"><Loading /></el-icon>
      <span style="margin-left: 8px; color: #909399">
        正在匹配产品，生成今日时间表（约 1-2 分钟）…
      </span>
    </el-card>

    <!-- Timeline -->
    <el-card v-if="schedule" shadow="never" class="timeline-card">
      <template #header>
        <span>{{ schedule.date }}  ·  10 个栏目均匀分布在 24 小时内</span>
      </template>

      <div class="timeline">
        <div
          v-for="slot in schedule.slots"
          :key="slot.category_id"
          class="slot-row"
          :class="{ expanded: expandedSlots.has(slot.category_id) }"
        >
          <!-- Slot summary row -->
          <div class="slot-head" @click="toggleSlot(slot.category_id)">
            <div class="slot-time">
              {{ formatTime(slot.scheduled_at) }}
            </div>

            <div class="slot-dot" :class="'dot-' + slot.slot_status" />

            <div class="slot-info">
              <span class="level1">{{ slot.level1_name }}</span>
              <span class="separator">·</span>
              <span class="cat-name">{{ slot.category_name }}</span>
            </div>

            <div class="slot-status-cell">
              <template v-if="slot.slot_status === 'RUNNING'">
                <el-tag type="warning" size="small" effect="dark">进行中</el-tag>
                <span class="step-hint">{{ runningStep(slot) }}</span>
              </template>
              <template v-else-if="slot.slot_status === 'DONE'">
                <el-tag type="success" size="small" effect="plain">完成</el-tag>
                <span class="done-count">{{ slot.done_count }}/{{ slot.total_count }}</span>
              </template>
              <template v-else-if="slot.slot_status === 'PARTIAL'">
                <el-tag type="warning" size="small" effect="plain">部分完成</el-tag>
                <span class="done-count">{{ slot.done_count }}/{{ slot.total_count }}</span>
              </template>
              <template v-else-if="slot.slot_status === 'FAILED'">
                <el-tag type="danger" size="small" effect="plain">失败</el-tag>
              </template>
              <template v-else>
                <!-- SCHEDULED -->
                <el-tag type="info" size="small" effect="plain">待执行</el-tag>
                <span class="countdown">{{ countdown(slot.scheduled_at) }}</span>
              </template>
            </div>

            <el-icon class="expand-icon">
              <ArrowDown v-if="!expandedSlots.has(slot.category_id)" />
              <ArrowUp v-else />
            </el-icon>
          </div>

          <!-- Expanded task detail -->
          <div v-if="expandedSlots.has(slot.category_id)" class="slot-tasks">
            <el-table :data="normalizedTasks(slot.tasks)" stripe border size="small">
              <el-table-column prop="product_line" label="产品线" width="130" />
              <el-table-column label="步骤" width="300">
                <template #default="{ row }">
                  <el-steps
                    v-if="row.status === 'RUNNING'"
                    :active="stepIndex(row.step)"
                    finish-status="success"
                    simple
                    style="margin: 0"
                  >
                    <el-step title="匹配" />
                    <el-step title="文案" />
                    <el-step title="生图" />
                    <el-step title="上传" />
                    <el-step title="注册" />
                  </el-steps>
                  <span v-else class="step-label">{{ stepLabel(row.step, row.status) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="90" align="center">
                <template #default="{ row }">
                  <el-tag :type="statusType(row.status)" size="small">
                    {{ statusLabel(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="headline" label="标题" min-width="160" show-overflow-tooltip />
              <el-table-column label="产品" min-width="160" show-overflow-tooltip>
                <template #default="{ row }">
                  {{ row.products?.join('、') || '-' }}
                </template>
              </el-table-column>
              <el-table-column label="耗时" width="80" align="right">
                <template #default="{ row }">
                  {{ row.duration_seconds ? row.duration_seconds.toFixed(0) + 's' : '-' }}
                </template>
              </el-table-column>
              <el-table-column prop="error_msg" label="错误" min-width="120" show-overflow-tooltip />
            </el-table>
          </div>
        </div>
      </div>
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
            <el-tag size="small" type="success">{{ batch.done }} 完成</el-tag>
            <el-tag v-if="batch.failed > 0" size="small" type="danger">{{ batch.failed }} 失败</el-tag>
            <el-tag v-if="batch.scheduled > 0" size="small" type="info">{{ batch.scheduled }} 待执行</el-tag>
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
          stripe border size="small"
          style="margin-top: 8px"
        >
          <el-table-column label="时间" width="60">
            <template #default="{ row }">
              {{ formatTime(row.scheduled_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="category_name" label="分类" width="120" />
          <el-table-column prop="product_line" label="产品线" width="110" />
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)" size="small">
                {{ statusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="headline" label="标题" min-width="160" show-overflow-tooltip />
          <el-table-column label="耗时" width="70" align="right">
            <template #default="{ row }">
              {{ row.duration_seconds ? row.duration_seconds.toFixed(0) + 's' : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="error_msg" label="错误" min-width="120" show-overflow-tooltip />
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getToday,
  listBatches as apiBatches,
  getBatchDetail,
  triggerPipeline,
  stopPipeline,
} from '@/api/categoryRuns'

// ── State ─────────────────────────────────────────────────────────────────────
const schedule = ref<any>(null)
const triggering = ref(false)
const initialising = ref(false)   // triggered but no slots created yet
const autoRefresh = ref(true)
const expandedSlots = ref(new Set<string>())

const historyDate = ref(new Date().toISOString().slice(0, 10))
const batches = ref<any[]>([])
const expandedBatches = ref(new Set<string>())
const batchDetails = ref<Record<string, any[]>>({})
const loadingDetail = ref('')

let timer: ReturnType<typeof setInterval> | null = null

// ── Computed ──────────────────────────────────────────────────────────────────
const hasScheduled = computed(() =>
  schedule.value?.slots?.some((s: any) => s.slot_status === 'SCHEDULED') ?? false
)

const overallTagType = computed(() => {
  if (!schedule.value) return 'info'
  const slots: any[] = schedule.value.slots || []
  if (slots.some((s: any) => s.slot_status === 'RUNNING')) return 'warning'
  if (slots.every((s: any) => s.slot_status === 'DONE')) return 'success'
  if (slots.some((s: any) => s.slot_status === 'SCHEDULED')) return 'info'
  return 'info'
})

const overallLabel = computed(() => {
  if (!schedule.value) return '空闲'
  const slots: any[] = schedule.value.slots || []
  if (slots.some((s: any) => s.slot_status === 'RUNNING')) return '执行中'
  if (slots.every((s: any) => ['DONE', 'PARTIAL', 'FAILED'].includes(s.slot_status))) return '今日已完成'
  if (slots.some((s: any) => s.slot_status === 'SCHEDULED')) return '计划中'
  return '空闲'
})

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatTime(iso: string | null | undefined): string {
  if (!iso) return '--:--'
  return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function countdown(iso: string | null | undefined): string {
  if (!iso) return ''
  const diff = new Date(iso).getTime() - Date.now()
  if (diff <= 0) return '即将执行'
  const h = Math.floor(diff / 3600000)
  const m = Math.floor((diff % 3600000) / 60000)
  if (h > 0) return `${h}h ${m}m 后`
  return `${m}m 后`
}

function stepIndex(step: string): number {
  const steps: Record<string, number> = {
    matching: 0, content: 1, image: 2, uploading: 3, registering: 4, done: 5,
  }
  return steps[step] ?? 0
}

function stepLabel(step: string, status: string): string {
  if (status === 'DONE') return '完成'
  if (status === 'FAILED') return '失败'
  if (status === 'SCHEDULED') return '待执行'
  return step
}

function statusType(status: string): 'success' | 'danger' | 'warning' | 'info' {
  const map: Record<string, 'success' | 'danger' | 'warning' | 'info'> = {
    DONE: 'success', FAILED: 'danger', RUNNING: 'warning', PENDING: 'info', SCHEDULED: 'info',
  }
  return map[status] || 'info'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    DONE: '完成', FAILED: '失败', RUNNING: '进行中', PENDING: '等待中', SCHEDULED: '待执行',
  }
  return map[status] || status
}

function runningStep(slot: any): string {
  const running = slot.tasks?.find((t: any) => t.status === 'RUNNING')
  if (!running) return ''
  const labels: Record<string, string> = {
    matching: '匹配中', content: '生成文案', image: '生成图片',
    uploading: '上传中', registering: '注册中',
  }
  return labels[running.step] || running.step
}

function normalizedTasks(tasks: any[]): any[] {
  // products in DB can be strings (legacy) or objects — normalise to strings
  return tasks.map((t: any) => ({
    ...t,
    products: (t.products || []).map((p: any) =>
      typeof p === 'string' ? p : p.product_name || String(p)
    ),
  }))
}

// ── Data loading ──────────────────────────────────────────────────────────────
async function loadSchedule() {
  try {
    const { data } = await getToday()
    schedule.value = data || null
    if (initialising.value && data) {
      initialising.value = false
    }
  } catch {
    // network error — keep previous state
  }
}

async function loadBatches() {
  try {
    const { data } = await apiBatches({ date: historyDate.value || undefined })
    batches.value = data.items || []
  } catch {
    batches.value = []
  }
}

function toggleSlot(categoryId: string) {
  if (expandedSlots.value.has(categoryId)) {
    expandedSlots.value.delete(categoryId)
  } else {
    expandedSlots.value.add(categoryId)
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

// ── Actions ───────────────────────────────────────────────────────────────────
async function handleTrigger() {
  triggering.value = true
  try {
    await triggerPipeline()
    ElMessage.success('已开始生成今日计划，正在匹配产品…')
    initialising.value = true
    autoRefresh.value = true
  } catch (err: any) {
    const msg = err?.response?.data?.detail || '触发失败'
    ElMessage.error(msg)
  }
  triggering.value = false
}

async function handleStop() {
  try {
    const { data } = await stopPipeline()
    ElMessage.info(data?.message || '已发送停止信号')
    await loadSchedule()
  } catch {
    ElMessage.error('停止失败')
  }
}

// ── Polling ───────────────────────────────────────────────────────────────────
function startPolling() {
  stopPolling()
  timer = setInterval(async () => {
    if (document.hidden || !autoRefresh.value) return
    await loadSchedule()
    if (!schedule.value || overallLabel.value === '今日已完成') {
      await loadBatches()
    }
  }, 5000)
}

function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

onMounted(async () => {
  await Promise.all([loadSchedule(), loadBatches()])
  startPolling()
})

onUnmounted(() => stopPolling())
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
  gap: 8px;
}
.title {
  font-size: 16px;
  font-weight: 600;
}
.summary-text {
  font-size: 13px;
  color: #606266;
}

.init-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  padding: 20px;
}
.spin {
  animation: spin 1.2s linear infinite;
  font-size: 18px;
  color: #909399;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}

/* Timeline */
.timeline {
  display: flex;
  flex-direction: column;
}

.slot-row {
  border-bottom: 1px solid #f0f0f0;
}
.slot-row:last-child {
  border-bottom: none;
}

.slot-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 8px;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.15s;
  user-select: none;
}
.slot-head:hover {
  background: #f5f7fa;
}

.slot-time {
  font-family: monospace;
  font-size: 15px;
  color: #303133;
  width: 48px;
  flex-shrink: 0;
}

.slot-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot-DONE    { background: #67c23a; }
.dot-RUNNING { background: #e6a23c; }
.dot-FAILED  { background: #f56c6c; }
.dot-PARTIAL { background: #e6a23c; }
.dot-SCHEDULED { background: #c0c4cc; }

.slot-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
}
.level1 {
  font-size: 12px;
  color: #909399;
}
.separator {
  color: #c0c4cc;
}
.cat-name {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.slot-status-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 160px;
  justify-content: flex-end;
}
.step-hint {
  font-size: 12px;
  color: #e6a23c;
}
.done-count {
  font-size: 12px;
  color: #606266;
}
.countdown {
  font-size: 12px;
  color: #909399;
}

.expand-icon {
  color: #909399;
  flex-shrink: 0;
}

.slot-tasks {
  padding: 0 8px 12px 8px;
}

/* History */
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
.step-label {
  font-size: 12px;
  color: #909399;
}
</style>
