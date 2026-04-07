<template>
  <div class="logs-view">
    <el-card shadow="never">
      <el-tabs v-model="activeTab" class="log-tabs">
        <el-tab-pane label="实时日志 (Stream)" name="realtime">
          <LogStream v-if="activeTab === 'realtime'" />
        </el-tab-pane>
        
        <el-tab-pane label="历史查询 (Search)" name="history">
          <div class="filter-container">
            <el-form :inline="true" :model="filters" class="filter-form">
              <el-form-item label="日期">
                <el-date-picker
                  v-model="filters.date"
                  type="date"
                  placeholder="选择日期 (必填)"
                  value-format="YYYY-MM-DD"
                  :clearable="false"
                  @change="handleSearch"
                  style="width: 150px"
                />
              </el-form-item>
              <el-form-item label="级别">
                <el-select
                  v-model="filters.level"
                  placeholder="全部级别"
                  clearable
                  @change="handleSearch"
                  style="width: 120px"
                >
                  <el-option label="INFO" value="INFO" />
                  <el-option label="WARNING" value="WARNING" />
                  <el-option label="ERROR" value="ERROR" />
                  <el-option label="DEBUG" value="DEBUG" />
                </el-select>
              </el-form-item>
              <el-form-item label="关键词">
                <el-input
                  v-model="filters.keyword"
                  placeholder="搜索日志内容"
                  clearable
                  @keyup.enter="handleSearch"
                  style="width: 250px"
                />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" icon="Search" @click="handleSearch" :loading="loading">查询</el-button>
              </el-form-item>
            </el-form>
          </div>

          <el-table
            :data="historyLogs"
            v-loading="loading"
            style="width: 100%"
            stripe
            border
            height="500"
            class="history-table"
          >
            <template #empty>
              <el-empty description="暂无日志数据" />
            </template>
            <el-table-column prop="line_number" label="行号" width="80" align="center" />
            <el-table-column prop="timestamp" label="时间" width="180" />
            <el-table-column prop="level" label="级别" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="getLevelType(row.level)" size="small">
                  {{ row.level }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="message" label="内容" min-width="400" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="log-message" :class="`text-${row.level.toLowerCase()}`">{{ row.message }}</span>
              </template>
            </el-table-column>
          </el-table>
          <div class="log-summary" v-if="totalLines > 0">
            共匹配到 {{ totalLines }} 行记录 (最多显示 1000 行)
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import LogStream from '@/components/LogStream.vue'
import { getLogs } from '@/api/logs'
import { ElMessage } from 'element-plus'

const activeTab = ref('realtime')
const loading = ref(false)
const historyLogs = ref<any[]>([])
const totalLines = ref(0)

// Default to today
const today = new Date()
const defaultDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`

const filters = reactive({
  date: defaultDate,
  level: '',
  keyword: ''
})

const handleSearch = async () => {
  if (!filters.date) {
    ElMessage.warning('请选择要查询的日期')
    return
  }

  loading.value = true
  try {
    const { data } = await getLogs(filters)
    historyLogs.value = data.lines || []
    totalLines.value = data.total_lines || 0
  } catch (error) {
    ElMessage.error('获取历史日志失败')
    historyLogs.value = []
    totalLines.value = 0
  } finally {
    loading.value = false
  }
}

const getLevelType = (level: string) => {
  const map: Record<string, string> = {
    INFO: 'success',
    WARNING: 'warning',
    ERROR: 'danger',
    DEBUG: 'info'
  }
  return map[level] || 'info'
}

onMounted(() => {
  // Automatically search history for today on initial load of that tab
  // Though we start on realtime, it's good to have it ready
  if (activeTab.value === 'history') {
    handleSearch()
  }
})
</script>

<style scoped>
.filter-container {
  margin-bottom: 20px;
}

.history-table {
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
}

.log-message {
  white-space: pre-wrap;
  word-break: break-all;
}

.text-error { color: #F56C6C; }
.text-warning { color: #E6A23C; }

.log-summary {
  margin-top: 10px;
  text-align: right;
  font-size: 13px;
  color: #909399;
}
</style>
