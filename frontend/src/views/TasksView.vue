<template>
  <div class="tasks-view">
    <el-card shadow="never">
      <div class="filter-container">
        <div class="left-actions">
          <el-select
            v-model="statusFilter"
            placeholder="按状态筛选"
            clearable
            @change="loadTasks"
            class="filter-item"
          >
            <el-option label="待处理" value="PENDING" />
            <el-option label="进行中" value="RUNNING" />
            <el-option label="已完成" value="DONE" />
            <el-option label="失败" value="FAILED" />
          </el-select>
          <el-button type="primary" plain icon="Refresh" @click="loadTasks" :loading="loading">
            刷新
          </el-button>
        </div>
        <div class="right-actions">
          <el-button
            type="primary"
            icon="VideoPlay"
            :disabled="selectedRows.length === 0"
            @click="handleBatchTrigger"
          >
            批量重新生成 ({{ selectedRows.length }})
          </el-button>
        </div>
      </div>

      <el-table
        :data="tasks"
        v-loading="loading"
        style="width: 100%"
        stripe
        border
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" align="center" />
        <el-table-column prop="product_name" label="产品名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="120" align="center" />
        <el-table-column prop="status" label="当前状态" width="120" align="center">
          <template #default="{ row }">
            <StatusBadge :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column prop="asset_filename" label="资产文件" min-width="150" show-overflow-tooltip />
        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              size="small"
              icon="View"
              :disabled="row.status !== 'DONE'"
              @click="handlePreview(row)"
            >
              查看海报
            </el-button>
            <el-divider direction="vertical" />
            <el-button
              link
              type="warning"
              size="small"
              icon="RefreshRight"
              @click="handleSingleTrigger(row)"
            >
              重新生成
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <PosterPreview
      v-model="previewVisible"
      :cloudFileId="previewCloudFileId"
      :productName="previewProductName"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import StatusBadge from '@/components/StatusBadge.vue'
import PosterPreview from '@/components/PosterPreview.vue'
import { getTasks, triggerSingle, triggerBatch } from '@/api/tasks'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const tasks = ref<any[]>([])
const statusFilter = ref('')
const selectedRows = ref<any[]>([])

const previewVisible = ref(false)
const previewCloudFileId = ref('')
const previewProductName = ref('')

const loadTasks = async () => {
  loading.value = true
  try {
    const { data } = await getTasks({ status: statusFilter.value || undefined })
    tasks.value = data.items || []
  } catch (error) {
    ElMessage.error('获取任务列表失败')
  } finally {
    loading.value = false
  }
}

const handleSelectionChange = (val: any[]) => {
  selectedRows.value = val
}

const handlePreview = (row: any) => {
  previewCloudFileId.value = row.cloud_file_id || ''
  previewProductName.value = row.product_name || ''
  previewVisible.value = true
}

const handleSingleTrigger = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确定要重新生成产品 "${row.product_name}" 的海报吗？`, '确认触发', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await triggerSingle(row.record_id)
    ElMessage.success(`已加入生成队列: ${row.product_name}`)
    loadTasks()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error('触发生成失败')
    }
  }
}

const handleBatchTrigger = async () => {
  if (selectedRows.value.length === 0) return
  
  try {
    await ElMessageBox.confirm(`确定要批量重新生成选中的 ${selectedRows.value.length} 个产品的海报吗？`, '批量触发', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    const ids = selectedRows.value.map(row => row.record_id)
    await triggerBatch(ids)
    ElMessage.success(`已批量加入生成队列，共 ${ids.length} 个任务`)
    
    // Reset selection and refresh
    selectedRows.value = []
    loadTasks()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error('批量触发失败')
    }
  }
}

onMounted(() => {
  loadTasks()
})
</script>

<style scoped>
.filter-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.left-actions {
  display: flex;
  gap: 10px;
}

.filter-item {
  width: 200px;
}
</style>
