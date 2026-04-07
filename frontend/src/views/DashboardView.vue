<template>
  <div class="dashboard-view">
    <el-row :gutter="20" class="mb-20">
      <el-col :span="6">
        <StatsCard
          title="今日总数"
          :value="summary.total"
          icon="DocumentCopy"
          color="#409EFF"
        />
      </el-col>
      <el-col :span="6">
        <StatsCard
          title="成功数"
          :value="summary.success"
          icon="CircleCheck"
          color="#67C23A"
        />
      </el-col>
      <el-col :span="6">
        <StatsCard
          title="失败数"
          :value="summary.failed"
          icon="CircleClose"
          color="#F56C6C"
        />
      </el-col>
      <el-col :span="6">
        <StatsCard
          title="成功率"
          :value="summary.success_rate"
          suffix="%"
          icon="DataLine"
          color="#E6A23C"
        />
      </el-col>
    </el-row>

    <el-row :gutter="20" class="mb-20">
      <el-col :span="24">
        <el-card shadow="hover">
          <TrendChart
            :dates="trendData.dates"
            :successData="trendData.success"
            :failedData="trendData.failed"
            v-if="trendData.dates.length > 0"
          />
          <el-skeleton v-else animated :rows="8" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="24">
        <el-card shadow="hover" header="最近执行记录">
          <el-table :data="recentRuns" stripe style="width: 100%" v-loading="loadingRuns">
            <el-table-column prop="product_name" label="产品名称" width="200" show-overflow-tooltip />
            <el-table-column prop="trigger_type" label="触发类型" width="120">
              <template #default="{ row }">
                <el-tag :type="row.trigger_type === 'cron' ? 'info' : 'primary'" size="small">
                  {{ row.trigger_type === 'cron' ? '定时任务' : '手动触发' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="120">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="stage" label="执行阶段" width="120" />
            <el-table-column prop="duration_seconds" label="耗时" width="100">
              <template #default="{ row }">
                {{ row.duration_seconds ? row.duration_seconds.toFixed(1) + 's' : '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="started_at" label="开始时间">
              <template #default="{ row }">
                {{ formatTime(row.started_at) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import StatsCard from '@/components/StatsCard.vue'
import TrendChart from '@/components/TrendChart.vue'
import { getStatsSummary, getStatsTrend } from '@/api/stats'
import { getRuns } from '@/api/runs'
import { ElMessage } from 'element-plus'

const summary = ref({
  total: 0,
  success: 0,
  failed: 0,
  success_rate: 0
})

const trendData = ref({
  dates: [] as string[],
  success: [] as number[],
  failed: [] as number[]
})

const recentRuns = ref<any[]>([])
const loadingRuns = ref(false)

const loadStats = async () => {
  try {
    const { data } = await getStatsSummary()
    summary.value = data
  } catch (e) {
    ElMessage.error('获取今日统计失败')
  }
}

const loadTrend = async () => {
  try {
    const { data } = await getStatsTrend({ days: 7 })
    if (data.items) {
      trendData.value.dates = data.items.map((i: any) => i.date)
      trendData.value.success = data.items.map((i: any) => i.success)
      trendData.value.failed = data.items.map((i: any) => i.failed)
    }
  } catch (e) {
    ElMessage.error('获取趋势数据失败')
  }
}

const loadRecentRuns = async () => {
  loadingRuns.value = true
  try {
    const { data } = await getRuns({ page: 1, page_size: 5 })
    recentRuns.value = data.items || []
  } catch (e) {
    ElMessage.error('获取最新记录失败')
  } finally {
    loadingRuns.value = false
  }
}

const getStatusType = (status: string) => {
  const map: Record<string, string> = {
    DONE: 'success',
    FAILED: 'danger',
    RUNNING: 'warning'
  }
  return map[status] || 'info'
}

const formatTime = (isoString: string) => {
  if (!isoString) return '-'
  const date = new Date(isoString)
  return date.toLocaleString('zh-CN', { hour12: false })
}

onMounted(() => {
  loadStats()
  loadTrend()
  loadRecentRuns()
})
</script>

<style scoped>
.mb-20 {
  margin-bottom: 20px;
}
</style>
