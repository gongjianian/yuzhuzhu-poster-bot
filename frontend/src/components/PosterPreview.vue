<template>
  <el-dialog
    v-model="dialogVisible"
    title="海报信息"
    width="600px"
    destroy-on-close
    class="poster-dialog"
  >
    <div class="poster-container">
      <el-empty
        v-if="!cloudFileId"
        description="该产品尚未生成海报"
      />
      <div v-else class="info-card">
        <div class="info-header">
          <el-icon class="success-icon"><CircleCheck /></el-icon>
          <span>海报已生成并上传至微信云存储</span>
        </div>
        <div class="info-row">
          <div class="info-label">产品名称</div>
          <div class="info-value">{{ productName || '-' }}</div>
        </div>
        <div class="info-row">
          <div class="info-label">云存储 File ID</div>
          <div class="info-value file-id">
            {{ cloudFileId }}
            <el-button size="small" type="primary" plain @click="copyFileId">
              <el-icon><DocumentCopy /></el-icon>
              复制
            </el-button>
          </div>
        </div>
        <el-alert
          title="如何查看海报"
          type="info"
          :closable="false"
          show-icon
        >
          <template #default>
            <p>由于微信云存储的 cloud:// 协议无法在 Web 端直接显示，请通过以下方式查看：</p>
            <ol>
              <li>在微信云开发控制台 → 存储 → 搜索此 File ID</li>
              <li>或在小程序内调用 <code>wx.cloud.downloadFile</code> 拿到临时 URL</li>
            </ol>
            <p class="hint">Web 端预览功能将在后续版本通过后端代理实现。</p>
          </template>
        </el-alert>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { CircleCheck, DocumentCopy } from '@element-plus/icons-vue'

const props = defineProps<{
  modelValue: boolean
  cloudFileId?: string
  productName?: string
}>()

const emit = defineEmits(['update:modelValue'])

const dialogVisible = ref(props.modelValue)

watch(
  () => props.modelValue,
  (val) => {
    dialogVisible.value = val
  }
)

watch(dialogVisible, (val) => {
  emit('update:modelValue', val)
})

const copyFileId = async () => {
  if (!props.cloudFileId) return
  try {
    await navigator.clipboard.writeText(props.cloudFileId)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动选择文本')
  }
}
</script>

<style scoped>
.poster-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 300px;
  background-color: #f5f7fa;
  border-radius: 4px;
  overflow: hidden;
}

.info-card {
  width: 100%;
  padding: 16px;
}

.info-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  color: #67c23a;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
}

.success-icon {
  font-size: 24px;
}

.info-row {
  margin-bottom: 16px;
}

.info-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
}

.info-value {
  font-size: 14px;
  color: #303133;
  word-break: break-all;
}

.file-id {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  background-color: #f5f7fa;
  padding: 10px 12px;
  border-radius: 4px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 12px;
}

.hint {
  color: #909399;
  font-size: 12px;
  margin-top: 8px;
}

code {
  background-color: #f0f0f0;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 12px;
}

ol {
  padding-left: 20px;
  margin: 8px 0;
}

ol li {
  margin: 4px 0;
}
</style>
