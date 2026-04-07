<template>
  <div class="runs-view">
    <el-card shadow="never">
      <div class="filter-container">
        <el-form :inline="true" :model="filters" class="filter-form">
          <el-form-item label="执行日期">
            <el-date-picker
              v-model="filters.date"
              type="date"
              placeholder="选择日期"
              value-format="YYYY-MM-DD"
              @change="handleFilter"
              style="width: 150px"
            />
          </el-form-item>
          <el-form-item label="状态">
            <el-select
              v-model="filters.status"
              placeholder="全部"
              clearable
              @change="handleFilter"
              style="width: 120px"
            >
              <el-option label="进行中" value="RUNNING" />
              <el-option label="已完成" value="DONE" />
              <el-option label="失败" value="FAILED" />
            </el-select>
          </el-form-item>
          <el-form-item label="产品名称">
            <el-input
              v-model="filters.product_name"
              placeholder="输入关键词"
              clearable
              @keyup.enter="handleFilter"
              style="width: 150px"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" icon="Search" @click="handleFilter">查询</el-button>
            <el-button icon="Refresh" @click="resetFilter">重置</el-button>
          </el-form-item>
        </el-form>
      </div>

      <el-table
        :data="runs"
        v-loading="loading"
        style="width: 100%"
        stripe
        border
        @row-click="handleRowClick"
        class="runs-table"
      >
        <el-table-column prop="run_id" label="Run ID" width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="monospace-text">{{ row.run_id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="product_name" label="产品名称" min-width="150" show-overflow-tooltip />
        <el-table-column prop="trigger_type" label="触发方式" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.trigger_type === 'cron' ? 'info' : 'primary'" size="small">
              {{ row.trigger_type === 'cron' ? '定时任务' : '手动触发' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <StatusBadge :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="QC结果" width="100" align="center">
          <template #default="{ row }">
            <el-tag
              v-if="row.qc_passed !== null"
              :type="row.qc_passed ? 'success' : 'danger'"
              size="small"
              effect="plain"
            >
              {{ row.qc_passed ? '通过' : '未通过' }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="duration_seconds" label="耗时" width="80" align="right">
          <template #default="{ row }">
            {{ row.duration_seconds ? row.duration_seconds.toFixed(1) + 's' : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="started_at" label="开始时间" width="160" align="center">
          <template #default="{ row }">
            {{ formatTime(row.started_at) }}
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <el-drawer
      v-model="drawerVisible"
      title="执行记录详情"
      size="50%"
      class="detail-drawer"
    >
      <div v-if="selectedRun" class="drawer-content">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="Run ID" :span="2">
            <span class="monospace-text">{{ selectedRun.run_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="产品名称">{{ selectedRun.product_name }}</el-descriptions-item>
          <el-descriptions-item label="Record ID">
            <span class="monospace-text">{{ selectedRun.record_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="触发方式">
            {{ selectedRun.trigger_type === 'cron' ? '定时任务' : '手动触发' }}
          </el-descriptions-item>
          <el-descriptions-item label="当前状态">
            <StatusBadge :status="selectedRun.status" />
          </el-descriptions-item>
          <el-descriptions-item label="执行阶段">{{ selectedRun.stage || '-' }}</el-descriptions-item>
          <el-descriptions-item label="耗时">
            {{ selectedRun.duration_seconds ? selectedRun.duration_seconds.toFixed(2) + ' 秒' : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ formatTime(selectedRun.started_at) }}</el-descriptions-item>
          <el-descriptions-item label="结束时间">{{ formatTime(selectedRun.finished_at) }}</el-descriptions-item>
        </el-descriptions>

        <div class="detail-section">
          <h3>生成文案 (Headline)</h3>
          <el-card shadow="never" class="code-card">
            {{ selectedRun.headline || '无' }}
          </el-card>
        </div>

        <div class="detail-section">
          <h3>图像提示词 (Image Prompt)</h3>
          <el-card shadow="never" class="code-card">
            <pre>{{ selectedRun.image_prompt || '无' }}</pre>
          </el-card>
        </div>

        <div class="detail-section" v-if="selectedRun.qc_passed !== null">
          <h3>
            QC 质量检查
            <el-tag
              :type="selectedRun.qc_passed ? 'success' : 'danger'"
              size="small"
              class="ml-2"
            >
              置信度: {{ selectedRun.qc_confidence?.toFixed(2) || '-' }}
            </el-tag>
          </h3>
          <el-alert
            v-if="selectedRun.qc_issues && selectedRun.qc_issues.length > 0"
            title="发现的问题"
            type="warning"
            :closable="false"
            show-icon
          >
            <ul>
              <li v-for="(issue, index) in selectedRun.qc_issues" :key="index">{{ issue }}</li>
            </ul>
          </el-alert>
          <el-alert
            v-else
            title="未发现质量问题"
            type="success"
            :closable="false"
            show-icon
          />
        </div>

        <div class="detail-section" v-if="selectedRun.error_msg">
          <h3>错误信息</h3>
          <el-alert
            :title="selectedRun.error_msg"
            type="error"
            :closable="false"
            show-icon
          />
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { getRuns, getRunDetail } from '@/api/runs'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const runs = ref<any[]>([])

const filters = reactive({
  date: '',
  status: '',
  product_name: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const drawerVisible = ref(false)
const selectedRun = ref<any>(null)

const loadRuns = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      status: filters.status || undefined,
      product_name: filters.product_name || undefined,
      date: filters.date || undefined
    }
    const { data } = await getRuns(params)
    runs.value = data.items || []
    pagination.total = data.total || 0
  } catch (error) {
    ElMessage.error('获取执行记录失败')
  } finally {
    loading.value = false
  }
}

const handleFilter = () => {
  pagination.page = 1
  loadRuns()
}

const resetFilter = () => {
  filters.date = ''
  filters.status = ''
  filters.product_name = ''
  handleFilter()
}

const handleSizeChange = (val: number) => {
  pagination.pageSize = val
  loadRuns()
}

const handleCurrentChange = (val: number) => {
  pagination.page = val
  loadRuns()
}

const handleRowClick = async (row: any) => {
  try {
    const { data } = await getRunDetail(row.run_id)
    selectedRun.value = data
    drawerVisible.value = true
  } catch (error) {
    ElMessage.error('获取记录详情失败')
  }
}

const formatTime = (isoString: string) => {
  if (!isoString) return '-'
  const date = new Date(isoString)
  return date.toLocaleString('zh-CN', { hour12: false })
}

onMounted(() => {
  loadRuns()
})
</script>

<style scoped>
.filter-container {
  margin-bottom: 20px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
}

.runs-table {
  cursor: pointer;
}

.monospace-text {
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  color: #606266;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.drawer-content {
  padding: 0 20px 20px;
}

.detail-section {
  margin-top: 24px;
}

.detail-section h3 {
  font-size: 16px;
  margin-bottom: 12px;
  color: #303133;
  display: flex;
  align-items: center;
}

.code-card {
  background-color: #f8f9fa;
}

.code-card pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  color: #303133;
}

.ml-2 {
  margin-left: 8px;
}
</style>
