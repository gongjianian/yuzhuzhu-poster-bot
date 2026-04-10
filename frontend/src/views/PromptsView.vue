<template>
  <div class="prompts-view">
    <el-card shadow="never" class="header-card">
      <template #header>
        <div class="header">
          <div>
            <h2>Prompt 设置</h2>
            <p class="hint">
              修改管线使用的 AI prompt 模板。支持分步测试：先测方案策划 → 再测视觉翻译 → 最后生成图像。
            </p>
          </div>
          <el-button type="primary" plain icon="Refresh" @click="loadPrompts">
            刷新
          </el-button>
        </div>
      </template>

      <!-- Model settings -->
      <div class="model-bar">
        <div class="model-row">
          <span class="model-label">文案模型 (Stage 1/2)：</span>
          <el-select
            v-model="modelSettings.gemini_copy_model"
            placeholder="选择文案模型"
            filterable
            style="width: 320px"
            :loading="modelsLoading"
          >
            <el-option
              v-for="m in availableTextModels"
              :key="m.id"
              :label="m.id"
              :value="m.id"
            />
          </el-select>
          <span class="model-hint">用于方案策划 + 视觉翻译 prompt</span>
        </div>
        <div class="model-row">
          <span class="model-label">图像模型 (Stage 3)：</span>
          <el-select
            v-model="modelSettings.gemini_image_model"
            placeholder="选择图像模型"
            filterable
            style="width: 320px"
            :loading="modelsLoading"
          >
            <el-option
              v-for="m in availableImageModels"
              :key="m.id"
              :label="m.id"
              :value="m.id"
            />
          </el-select>
          <span class="model-hint">用于最终海报图像生成</span>
        </div>
        <div class="model-actions">
          <el-button size="small" plain icon="Refresh" :loading="modelsLoading" @click="loadAvailableModels">
            刷新模型列表
          </el-button>
          <el-button
            size="small"
            type="primary"
            :loading="savingModel"
            :disabled="!isModelDirty"
            @click="saveModelSettings"
          >
            <el-icon><DocumentChecked /></el-icon>
            保存模型选择
          </el-button>
        </div>
      </div>

      <!-- Shared product picker -->
      <div class="product-bar">
        <span class="product-label">测试产品：</span>
        <el-select
          v-model="selectedRecordId"
          placeholder="选择一个产品"
          filterable
          style="width: 360px"
        >
          <el-option
            v-for="task in testableTasks"
            :key="task.record_id"
            :label="`${task.product_name} (${task.category})`"
            :value="task.record_id"
            :disabled="!task.asset_filename"
          />
        </el-select>
        <el-tag v-if="stage1Result" type="success" size="small" class="state-tag">
          Stage 1 ✓ ({{ (stage1Result.duration_ms / 1000).toFixed(1) }}s)
        </el-tag>
        <el-tag v-if="stage2Result" type="success" size="small" class="state-tag">
          Stage 2 ✓ ({{ (stage2Result.duration_ms / 1000).toFixed(1) }}s)
        </el-tag>
        <el-tag v-if="stage3Result" type="success" size="small" class="state-tag">
          Stage 3 ✓ ({{ (stage3Result.total_ms / 1000).toFixed(1) }}s)
        </el-tag>
        <el-button
          v-if="stage1Result || stage2Result || stage3Result"
          link
          type="danger"
          @click="clearAllStages"
        >
          清除测试状态
        </el-button>
      </div>

      <el-tabs v-model="activeTab" v-loading="loading" type="card">
        <!-- Tab 1: scheme_prompt -->
        <el-tab-pane
          v-for="prompt in prompts"
          :key="prompt.name"
          :label="prompt.title"
          :name="prompt.name"
        >
          <div v-if="currentDetail" class="prompt-editor">
            <el-alert
              :title="currentDetail.description"
              type="info"
              :closable="false"
              show-icon
              class="description"
            />

            <div class="placeholders">
              <span class="placeholders-label">可用占位符（删除即不使用）：</span>
              <el-tag
                v-for="ph in currentDetail.placeholders"
                :key="ph"
                size="small"
                :type="editedContent.includes(ph) ? 'success' : 'info'"
                :effect="editedContent.includes(ph) ? 'light' : 'plain'"
                class="placeholder-tag"
              >
                {{ ph }}
              </el-tag>
            </div>

            <div class="meta-bar">
              <span>
                <el-icon><Document /></el-icon>
                {{ currentDetail.name }}
              </span>
              <span>{{ editedContent.length }} 字符</span>
              <span v-if="currentDetail.modified_at">
                <el-icon><Clock /></el-icon>
                {{ formatTime(currentDetail.modified_at) }}
              </span>
            </div>

            <el-input
              v-model="editedContent"
              type="textarea"
              :rows="20"
              resize="vertical"
              class="editor-textarea"
              placeholder="Prompt 内容..."
              :disabled="saving"
            />

            <div class="actions">
              <el-button :disabled="!isDirty || saving" @click="revertChanges">
                撤销
              </el-button>
              <el-button
                type="primary"
                :loading="saving"
                :disabled="!isDirty"
                @click="handleSave"
              >
                <el-icon><DocumentChecked /></el-icon>
                保存
              </el-button>

              <!-- Tab-specific test button -->
              <el-button
                v-if="activeTab === 'scheme_prompt.txt'"
                type="success"
                :disabled="isDirty || !selectedRecordId || testing"
                :loading="testing && currentTestStage === 'stage1'"
                @click="runStage1"
              >
                <el-icon><VideoPlay /></el-icon>
                测试 Stage 1 (方案策划)
              </el-button>

              <el-button
                v-if="activeTab === 'image_prompt.txt'"
                type="success"
                :disabled="isDirty || !selectedRecordId || !stage1Result || testing"
                :loading="testing && currentTestStage === 'stage2'"
                @click="runStage2"
              >
                <el-icon><VideoPlay /></el-icon>
                测试 Stage 2 (视觉翻译)
              </el-button>
            </div>

            <el-alert
              v-if="activeTab === 'image_prompt.txt' && !stage1Result"
              title="需要先运行 Stage 1"
              description="请先在「方案策划 Prompt」tab 运行测试，然后回到这里测试视觉翻译。"
              type="warning"
              :closable="false"
              show-icon
              class="warning"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- Stage results panel -->
    <el-card v-if="stage1Result || stage2Result || stage3Result" shadow="never" class="results-card">
      <template #header>
        <div class="results-header">
          <span>测试结果</span>
          <el-button
            type="primary"
            :disabled="!stage2Result || testing"
            :loading="testing && currentTestStage === 'stage3'"
            @click="runStage3"
          >
            <el-icon><Picture /></el-icon>
            生成最终图像（Stage 3）
          </el-button>
        </div>
      </template>

      <el-collapse v-model="expandedSections">
        <!-- Stage 1 result -->
        <el-collapse-item
          v-if="stage1Result"
          name="stage1"
        >
          <template #title>
            <div class="collapse-title">
              <el-icon :class="stage1Result.error ? 'fail' : 'ok'">
                <Check v-if="!stage1Result.error" /><Close v-else />
              </el-icon>
              <span>Stage 1: 方案策划</span>
              <span class="mini-meta">{{ stage1Result.product_name }} · {{ (stage1Result.duration_ms / 1000).toFixed(1) }}s</span>
            </div>
          </template>

          <el-alert
            v-if="stage1Result.error"
            :title="stage1Result.error"
            type="error"
            :closable="false"
            show-icon
          />
          <pre v-else class="code-block">{{ JSON.stringify(stage1Result.scheme, null, 2) }}</pre>
        </el-collapse-item>

        <!-- Stage 2 result -->
        <el-collapse-item v-if="stage2Result" name="stage2">
          <template #title>
            <div class="collapse-title">
              <el-icon :class="stage2Result.error ? 'fail' : 'ok'">
                <Check v-if="!stage2Result.error" /><Close v-else />
              </el-icon>
              <span>Stage 2: 视觉翻译（发给图像模型的 Prompt）</span>
              <span class="mini-meta">{{ (stage2Result.duration_ms / 1000).toFixed(1) }}s · {{ stage2Result.image_prompt.length }} 字符</span>
            </div>
          </template>

          <el-alert
            v-if="stage2Result.error"
            :title="stage2Result.error"
            type="error"
            :closable="false"
            show-icon
          />
          <pre v-else class="code-block">{{ stage2Result.image_prompt }}</pre>
        </el-collapse-item>

        <!-- Stage 3 result -->
        <el-collapse-item v-if="stage3Result" name="stage3">
          <template #title>
            <div class="collapse-title">
              <el-icon :class="stage3Result.error ? 'fail' : 'ok'">
                <Check v-if="!stage3Result.error" /><Close v-else />
              </el-icon>
              <span>Stage 3: 最终图像</span>
              <span class="mini-meta">
                抠图 {{ (stage3Result.asset_process_ms / 1000).toFixed(1) }}s · 生成 {{ (stage3Result.image_gen_ms / 1000).toFixed(1) }}s · {{ (stage3Result.image_size_bytes / 1024).toFixed(0) }} KB
              </span>
            </div>
          </template>

          <el-alert
            v-if="stage3Result.error"
            :title="stage3Result.error"
            type="error"
            :closable="false"
            show-icon
          />
          <div v-else-if="stage3Result.image_b64" class="image-preview">
            <img :src="`data:image/png;base64,${stage3Result.image_b64}`" />
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Check,
  Close,
  Document,
  DocumentChecked,
  Clock,
  VideoPlay,
  Picture,
} from '@element-plus/icons-vue'
import {
  listPrompts,
  getPrompt,
  updatePrompt,
  testSchemePrompt,
  testImagePrompt,
  testImage,
} from '@/api/prompts'
import type {
  PromptDetail,
  PromptMeta,
  SchemeTestResult,
  ImagePromptTestResult,
  ImageTestResult,
} from '@/api/prompts'
import { getTasks } from '@/api/tasks'
import {
  listAvailableModels,
  getModelSettings,
  updateModelSettings,
} from '@/api/settings'
import type { ModelInfo, ModelSettings } from '@/api/settings'

const loading = ref(false)
const saving = ref(false)
const prompts = ref<PromptMeta[]>([])
const activeTab = ref('')
const detailCache = ref<Record<string, PromptDetail>>({})
const editedContent = ref('')

// Model settings state
const modelSettings = ref<ModelSettings>({
  gemini_copy_model: '',
  gemini_image_model: '',
})
const savedModelSettings = ref<ModelSettings>({
  gemini_copy_model: '',
  gemini_image_model: '',
})
const availableTextModels = ref<ModelInfo[]>([])
const availableImageModels = ref<ModelInfo[]>([])
const modelsLoading = ref(false)
const savingModel = ref(false)

const isModelDirty = computed(() => {
  return (
    modelSettings.value.gemini_copy_model !== savedModelSettings.value.gemini_copy_model ||
    modelSettings.value.gemini_image_model !== savedModelSettings.value.gemini_image_model
  )
})

// Test state - shared across tabs and persisted to sessionStorage
const testableTasks = ref<any[]>([])
const selectedRecordId = ref('')
const stage1Result = ref<SchemeTestResult | null>(null)
const stage2Result = ref<ImagePromptTestResult | null>(null)
const stage3Result = ref<ImageTestResult | null>(null)
const testing = ref(false)
const currentTestStage = ref<'stage1' | 'stage2' | 'stage3' | null>(null)
const expandedSections = ref<string[]>(['stage1', 'stage2', 'stage3'])

// Persist test state across page navigation
const STORAGE_KEY = 'prompts_test_state'

const saveTestState = () => {
  const state = {
    selectedRecordId: selectedRecordId.value,
    stage1Result: stage1Result.value,
    stage2Result: stage2Result.value,
    stage3Result: stage3Result.value,
  }
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

const loadTestState = () => {
  const raw = sessionStorage.getItem(STORAGE_KEY)
  if (!raw) return
  try {
    const state = JSON.parse(raw)
    selectedRecordId.value = state.selectedRecordId || ''
    stage1Result.value = state.stage1Result || null
    stage2Result.value = state.stage2Result || null
    stage3Result.value = state.stage3Result || null
  } catch {}
}

const clearAllStages = () => {
  stage1Result.value = null
  stage2Result.value = null
  stage3Result.value = null
  sessionStorage.removeItem(STORAGE_KEY)
  ElMessage.success('测试状态已清除')
}

watch([stage1Result, stage2Result, stage3Result, selectedRecordId], saveTestState, { deep: true })

// Computed
const currentDetail = computed<PromptDetail | null>(() => detailCache.value[activeTab.value] ?? null)
const isDirty = computed(() => {
  if (!currentDetail.value) return false
  return editedContent.value !== currentDetail.value.content
})

// Prompt loading
const loadPrompts = async () => {
  loading.value = true
  try {
    const { data } = await listPrompts()
    prompts.value = data
    if (data.length > 0 && !activeTab.value) {
      activeTab.value = data[0].name
    }
    for (const p of data) {
      await loadPromptDetail(p.name)
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '加载 prompt 列表失败')
  } finally {
    loading.value = false
  }
}

const loadPromptDetail = async (name: string) => {
  try {
    const { data } = await getPrompt(name)
    detailCache.value[name] = data
    if (activeTab.value === name) {
      editedContent.value = data.content
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || `加载 ${name} 失败`)
  }
}

const handleSave = async () => {
  if (!currentDetail.value) return
  try {
    await ElMessageBox.confirm(
      `确定要保存修改到 ${currentDetail.value.title} 吗？旧版本会自动备份。`,
      '确认保存',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }

  saving.value = true
  try {
    const { data } = await updatePrompt(currentDetail.value.name, editedContent.value)
    detailCache.value[currentDetail.value.name] = data
    editedContent.value = data.content
    ElMessage.success('保存成功')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

const revertChanges = () => {
  if (currentDetail.value) editedContent.value = currentDetail.value.content
}

const formatTime = (iso: string) => new Date(iso).toLocaleString('zh-CN', { hour12: false })

// Stage 1: test scheme_prompt
const runStage1 = async () => {
  if (!selectedRecordId.value) return
  testing.value = true
  currentTestStage.value = 'stage1'
  try {
    const { data } = await testSchemePrompt(selectedRecordId.value)
    stage1Result.value = data
    // Clear downstream stages when stage 1 re-runs
    stage2Result.value = null
    stage3Result.value = null
    if (data.error) {
      ElMessage.error(`Stage 1 失败: ${data.error}`)
    } else {
      ElMessage.success(`Stage 1 完成 (${(data.duration_ms / 1000).toFixed(1)}s)`)
      expandedSections.value = ['stage1']
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Stage 1 请求失败')
  } finally {
    testing.value = false
    currentTestStage.value = null
  }
}

// Stage 2: test image_prompt using stage1 output
const runStage2 = async () => {
  if (!selectedRecordId.value || !stage1Result.value || stage1Result.value.error) return
  testing.value = true
  currentTestStage.value = 'stage2'
  try {
    const { data } = await testImagePrompt(selectedRecordId.value, stage1Result.value.scheme)
    stage2Result.value = data
    stage3Result.value = null
    if (data.error) {
      ElMessage.error(`Stage 2 失败: ${data.error}`)
    } else {
      ElMessage.success(`Stage 2 完成 (${(data.duration_ms / 1000).toFixed(1)}s)`)
      expandedSections.value = ['stage2']
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Stage 2 请求失败')
  } finally {
    testing.value = false
    currentTestStage.value = null
  }
}

// Stage 3: generate image using stage2 output
const runStage3 = async () => {
  if (!selectedRecordId.value || !stage2Result.value || stage2Result.value.error) return
  if (!stage1Result.value || stage1Result.value.error) return
  try {
    await ElMessageBox.confirm(
      '这会调用 Gemini 图像生成 API（约 60-180 秒，有费用）。确定吗？',
      '确认生成图像',
      { confirmButtonText: '开始', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }

  testing.value = true
  currentTestStage.value = 'stage3'
  try {
    const { data } = await testImage(
      selectedRecordId.value,
      stage2Result.value.image_prompt,
    )
    stage3Result.value = data
    if (data.error) {
      ElMessage.error(`Stage 3 失败: ${data.error}`)
    } else {
      ElMessage.success(`海报生成完成 (${(data.total_ms / 1000).toFixed(1)}s)`)
      expandedSections.value = ['stage3']
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Stage 3 请求失败')
  } finally {
    testing.value = false
    currentTestStage.value = null
  }
}

// Model settings
const loadModelSettings = async () => {
  try {
    const { data } = await getModelSettings()
    modelSettings.value = { ...data }
    savedModelSettings.value = { ...data }
  } catch (e: any) {
    console.error('Failed to load model settings:', e)
  }
}

const loadAvailableModels = async () => {
  modelsLoading.value = true
  try {
    const { data } = await listAvailableModels()
    availableTextModels.value = data.text_models
    availableImageModels.value = data.image_models
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '加载模型列表失败')
  } finally {
    modelsLoading.value = false
  }
}

const saveModelSettings = async () => {
  savingModel.value = true
  try {
    const { data } = await updateModelSettings({
      gemini_copy_model: modelSettings.value.gemini_copy_model,
      gemini_image_model: modelSettings.value.gemini_image_model,
    })
    savedModelSettings.value = { ...data }
    modelSettings.value = { ...data }
    ElMessage.success('模型设置已保存，立即生效')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '保存模型设置失败')
  } finally {
    savingModel.value = false
  }
}

// Load product list
const loadTasks = async () => {
  try {
    const { data } = await getTasks({})
    testableTasks.value = (data.items || []).filter((t: any) => t.asset_filename)
    if (!selectedRecordId.value) {
      const jinyinhua = testableTasks.value.find((t: any) => t.product_name === '金银花泡浴')
      if (jinyinhua) selectedRecordId.value = jinyinhua.record_id
    }
  } catch (e: any) {
    console.error('Failed to load tasks:', e)
  }
}

watch(activeTab, (newName) => {
  if (newName && detailCache.value[newName]) {
    editedContent.value = detailCache.value[newName].content
  }
})

onMounted(() => {
  loadPrompts()
  loadTasks()
  loadTestState()
  loadModelSettings()
  loadAvailableModels()
})
</script>

<style scoped>
.prompts-view {
  padding: 0;
}

.header-card {
  border: none;
  margin-bottom: 16px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header h2 {
  margin: 0 0 4px 0;
  font-size: 20px;
  color: #303133;
}

.hint {
  margin: 0;
  font-size: 13px;
  color: #909399;
  max-width: 700px;
}

.model-bar {
  padding: 14px 16px;
  background: linear-gradient(to right, #f0f9ff, #f5f7fa);
  border: 1px solid #d9ecff;
  border-radius: 6px;
  margin-bottom: 12px;
}

.model-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.model-row:last-of-type {
  margin-bottom: 10px;
}

.model-label {
  font-size: 13px;
  color: #303133;
  font-weight: 500;
  min-width: 160px;
}

.model-hint {
  font-size: 12px;
  color: #909399;
}

.model-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 8px;
  border-top: 1px dashed #c6e2ff;
}

.product-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background-color: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.product-label {
  font-size: 13px;
  color: #606266;
  font-weight: 500;
}

.state-tag {
  font-family: 'Courier New', Courier, monospace;
}

.prompt-editor {
  padding-top: 8px;
}

.description {
  margin-bottom: 16px;
}

.placeholders {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background-color: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 12px;
}

.placeholders-label {
  font-size: 12px;
  color: #606266;
  font-weight: 500;
}

.placeholder-tag {
  font-family: 'Courier New', Courier, monospace;
  font-size: 11px;
}

.meta-bar {
  display: flex;
  gap: 20px;
  padding: 8px 12px;
  font-size: 12px;
  color: #909399;
  background-color: #fafbfc;
  border-radius: 4px 4px 0 0;
  border: 1px solid #e4e7ed;
  border-bottom: none;
}

.meta-bar .el-icon {
  margin-right: 4px;
  vertical-align: middle;
}

.editor-textarea :deep(.el-textarea__inner) {
  font-family: 'Courier New', Consolas, Monaco, monospace;
  font-size: 13px;
  line-height: 1.6;
  border-radius: 0 0 4px 4px;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
}

.warning {
  margin-top: 12px;
}

.results-card {
  border: none;
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
  font-weight: 500;
}

.collapse-title {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  padding-right: 16px;
}

.collapse-title .ok {
  color: #67c23a;
  font-size: 16px;
}

.collapse-title .fail {
  color: #f56c6c;
  font-size: 16px;
}

.mini-meta {
  margin-left: auto;
  font-size: 12px;
  color: #909399;
  font-weight: normal;
}

.code-block {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 14px;
  border-radius: 4px;
  font-family: 'Courier New', Consolas, Monaco, monospace;
  font-size: 12px;
  line-height: 1.6;
  max-height: 500px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
}

.image-preview {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 4px;
  text-align: center;
  border: 1px solid #e4e7ed;
}

.image-preview img {
  max-width: 100%;
  max-height: 600px;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}
</style>
