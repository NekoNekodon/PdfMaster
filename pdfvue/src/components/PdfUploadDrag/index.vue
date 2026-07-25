<template>
  <div
    class="upload-drop-area"
    :class="{ drag_over: isDragOver }"
    role="region"
    aria-label="PDF文件上传区域"
    @drop.prevent="handleDrop"
    @dragover.prevent="isDragOver = true"
    @dragleave="isDragOver = false"
    tabindex="0"
    @keydown.enter="triggerInput"
  >
    <UploadFilled style="width: 9.375em; height: 9.375em; color: #409eff;" aria-hidden="true" />
    <p class="tip" role="heading" aria-level="2">将PDF拖拽到此处</p>
    <p class="sub-tip">或点击按钮选择本地PDF</p>

    <el-button type="primary" class="default-btn" @click="triggerInput">
      选择PDF文件
    </el-button>

    <input ref="fileInputRef" type="file" accept=".pdf" hidden @change="onFileSelect" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'

const emit = defineEmits(['file-select'])
const fileInputRef = ref(null)
const isDragOver = ref(false)

const triggerInput = () => {
  fileInputRef.value?.click()
}
const handleDrop = (e) => {
  isDragOver.value = false
  const file = e.dataTransfer.files[0]
  if (!file) return
  emit('file-select', file)
}
const onFileSelect = (e) => {
  const file = e.target.files[0]
  if (!file) return
  emit('file-select', file)
  e.target.value = ''
}
</script>

<style scoped>
.upload-drop-area {
  height: 37.5em;
  flex: 1;
  border: 0.125em dashed #c0c4cc;
  border-radius: 0.625em;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75em;
  transition: 0.2s;
}
.upload-drop-area.drag_over {
  border-color: #409eff;
  background: #ecf5ff;
}
.tip {
  font-size: 1.875em;
  color: #303133;
  margin: 0;
}
.sub-tip {
  font-size: 1.25em;
  color: #909399;
  margin: 0;
}
.default-btn {
  font-size: 1.2em;
  width: 10em;
  height: 3em;
}
</style>