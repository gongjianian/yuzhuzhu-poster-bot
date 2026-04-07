<template>
  <el-dialog
    v-model="dialogVisible"
    title="海报预览"
    width="50%"
    destroy-on-close
    class="poster-dialog"
  >
    <div class="poster-container" v-loading="loading">
      <el-image
        v-if="imageUrl"
        :src="imageUrl"
        fit="contain"
        class="poster-image"
        :preview-src-list="[imageUrl]"
      >
        <template #error>
          <div class="image-slot">
            <el-icon><icon-picture /></el-icon>
            <span>加载失败</span>
          </div>
        </template>
      </el-image>
      <el-empty v-else description="暂无预览图" />
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Picture as IconPicture } from '@element-plus/icons-vue'

const props = defineProps<{
  modelValue: boolean
  imageUrl: string
}>()

const emit = defineEmits(['update:modelValue'])

const dialogVisible = ref(props.modelValue)
const loading = ref(false)

watch(
  () => props.modelValue,
  (val) => {
    dialogVisible.value = val
    if (val && props.imageUrl) {
      loading.value = true
      // Simulate image loading delay for better UX
      setTimeout(() => {
        loading.value = false
      }, 500)
    }
  }
)

watch(dialogVisible, (val) => {
  emit('update:modelValue', val)
})
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

.poster-image {
  max-width: 100%;
  max-height: 600px;
}

.image-slot {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: #909399;
  font-size: 14px;
}

.image-slot .el-icon {
  font-size: 32px;
  margin-bottom: 8px;
}
</style>
