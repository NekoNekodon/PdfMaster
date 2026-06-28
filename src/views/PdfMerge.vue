<template>
  <div class="pdf-editor-container" role="main" aria-label="PDF工具箱-多PDF合并工具">
    <!-- 左侧外层绑定拖拽高亮class，唯一处理文件拖拽上传 -->
    <div 
      class="left-area"
      :class="{ drag_over_wrap: isDragOver }"
      @drop.prevent="handleGlobalDrop"
      @dragover.prevent="isDragOver = true"
      @dragleave="isDragOver = false"
    >
      <!-- 拖拽上传区域（无文件时展示） -->
      <div
        v-if="fileList.length === 0"
        class="upload-drop-area"
        :class="{ drag_over: isDragOver }"
        role="region"
        aria-label="批量上传PDF区域"
        tabindex="0"
        @keydown.enter="openFileDialog"
      >
        <UploadFilled 
          style="width: 9.375em; height: 9.375em; color: #409eff;" 
          aria-hidden="true"
        />
        <p class="tip" role="heading" aria-level="2">拖拽多个PDF到此处</p>
        <p class="sub-tip">支持批量上传，可拖拽调整顺序</p>

        <el-button 
          type="primary" 
          class="default-btn" 
          @click="openFileDialog"
          aria-label="批量选择本地PDF文件"
        >
          批量选择PDF
        </el-button>
      </div>

      <!-- 多PDF卡片容器，支持拖拽排序 -->
      <div 
        v-else
        class="multi-pdf-wrap"
        @drop.prevent="onListDrop"
        @dragover.prevent="handleCardDragOver"
      >
        <div
          v-for="(item, index) in fileList"
          :key="item.uid"
          class="pdf-card"
          draggable="true"
          @dragstart="handleDragStart(index)"
          @dragend="handleDragEnd"
          :class="{ drag_target: hoverIndex === index, dragging: dragIndex === index }"
        >
          <!-- 卡片头部：文件名、删除按钮 -->
          <div class="card-header">
            <span class="card-index">{{ index + 1 }}</span>
            <span class="card-name">{{ item.file.name }}</span>
            <el-button text type="danger" icon="Delete" @click="removeFile(index)" />
          </div>

          <!-- 仅展示封面单页预览，自适应宽度 -->
          <div class="pdf-canvas-box-small">
            <div class="pdf-page-item-mini">
              <canvas 
                :ref="el => setCanvasRef(el, item.uid + '_1')"
              ></canvas>
              <div class="page-label-mini">封面页</div>
            </div>
          </div>

          <!-- 单文件配置：起止页码、密码 -->
          <div class="card-setting">
            <div class="row">
              <span>起始页</span>
              <el-input v-model.number="item.start" size="small" style="width:60px" />
              <span>结束页</span>
              <el-input v-model.number="item.end" size="small" style="width:60px" />
            </div>
            <el-input 
              v-model="item.password" 
              placeholder="PDF密码(无则留空)" 
              size="small" 
              clearable
            />
            <div class="total-tip">文档总页数：{{ item.totalPage }}</div>
          </div>
        </div>
        <!-- 占位卡片 -->
        <div class="pdf-card upload-placeholder-card">
          <div class="placeholder-content">
            <UploadFilled style="width:4.5em;height:4.5em;color:#c0c4cc;margin:0 auto" />
            <p class="placeholder-tip-main">拖拽PDF追加</p>
            <p class="placeholder-tip-sub">支持批量上传</p>
            <el-button type="primary" class="placeholder-upload-btn" @click.stop="openFileDialog">选择PDF</el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧合并操作面板 -->
    <div class="right-panel" role="complementary" aria-label="PDF合并操作面板">
      <div class="panel-title" role="heading" aria-level="2">多PDF合并导出</div>
      <el-divider />

      <div class="split-all-desc">
        <p>✅ 批量上传多个PDF文档</p>
        <p>✅ 拖拽卡片调整合并顺序</p>
        <p>✅ 每个文件独立截取页面、独立解密</p>
        <p>✅ 仅加载封面预览，降低内存占用</p>
      </div>

      <div class="cut-list-title" role="heading" aria-level="3">待合并文档数量</div>
      <div class="cut-list" role="list">
        <div 
          class="empty-tip success-tip"
          role="status"
          aria-live="polite"
        >
          当前共 {{ fileList.length }} 个PDF待合并
        </div>
      </div>

      <el-divider />
      <el-button 
        type="success" 
        class="default-btn full-btn center-btn" 
        @click="mergeAllPdf"
        :loading="exportLoading"
      >
        一键合并导出PDF
      </el-button>
      <el-button 
        class="default-btn full-btn center-btn" 
        @click="resetAll"
      >
        清空全部文件
      </el-button>
    </div>

    <!-- 【关键修复】input移出v-if，永久存在，ref不会变成null -->
    <input 
      ref="fileInputRef" 
      type="file" 
      accept=".pdf" 
      multiple
      hidden 
      @change="handleBatchSelect"
    />
  </div>
</template>

<script setup>
import { ref, nextTick, getCurrentInstance, onUnmounted } from 'vue'
import * as pdfjsLib from 'pdfjs-dist'
import { ElMessage, ElLoading } from 'element-plus'
import { UploadFilled, Delete } from '@element-plus/icons-vue'

// axios请求
const { proxy } = getCurrentInstance()
const $api = proxy.$api

// PDF Worker
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js'
pdfjsLib.GlobalWorkerOptions.useWorkerFetch = true

// DOM Ref
const fileInputRef = ref(null)
const canvasRefMap = new Map()

// 拖拽全局状态
const isDragOver = ref(false)
const dragIndex = ref(null)
const hoverIndex = ref(null)
let dragOriginIndex = null

// 文件列表：每个item独立存储文件、仅封面预览、页码、密码
const fileList = ref([])
const exportLoading = ref(false)

// 生成唯一ID
function genUid() {
  return Date.now() + '_' + Math.random().toString(36).slice(2)
}

// 保存Canvas映射
const setCanvasRef = (el, key) => {
  if (el) canvasRefMap.set(key, el)
  else canvasRefMap.delete(key)
}

// 【安全打开文件弹窗】判空再执行，杜绝null报错
const openFileDialog = () => {
  if (fileInputRef.value) {
    fileInputRef.value.click()
  }
}

// 拖拽新增文件（唯一入口：外层全局拖拽，不再多处重复触发）
const handleGlobalDrop = (e) => {
  isDragOver.value = false
  hoverIndex.value = null
  const dragTag = e.dataTransfer.getData('text/plain')
  // 拖拽排序卡片标记sort，直接跳过，不处理文件
  if (dragTag === 'sort') return

  const files = Array.from(e.dataTransfer.files).filter(f => f.type === 'application/pdf')
  if (!files.length) {
    ElMessage.warning('仅支持PDF文件')
    return
  }
  addPdfFiles(files)
}

// 文件选择框批量上传
const handleBatchSelect = (e) => {
  const files = Array.from(e.target.files).filter(f => f.type === 'application/pdf')
  if (!files.length) return
  addPdfFiles(files)
  // 清空input，防止重复选择不触发change
  e.target.value = ''
}

// 批量添加PDF，仅渲染封面第一页
const addPdfFiles = async (files) => {
  for (const file of files) {
    const uid = genUid()
    const arrayBuf = await file.arrayBuffer()
    const fileBackup = new File([arrayBuf], file.name, { type: file.type })
    const task = pdfjsLib.getDocument(arrayBuf)
    const pdfDoc = await task.promise
    const total = pdfDoc.numPages

    fileList.value.push({
      uid,
      file: fileBackup,
      pdfDoc,
      totalPage: total,
      start: 1,
      end: total,
      password: ''
    })
    await nextTick()
    await renderMiniCover(pdfDoc, uid, 1)
  }
  ElMessage.success(`成功加载${files.length}个PDF`)
}

// 渲染封面缩略图
const renderMiniCover = async (pdfDoc, uid, pageNum) => {
  const page = await pdfDoc.getPage(pageNum)
  const canvas = canvasRefMap.get(`${uid}_${pageNum}`)
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  const maxWidth = 160
  const origView = page.getViewport({ scale: 1 })
  const scale = maxWidth / origView.width
  const viewport = page.getViewport({ scale })
  canvas.width = viewport.width
  canvas.height = viewport.height
  await page.render({ canvasContext: ctx, viewport }).promise
}

// 删除单个PDF + 同步回收资源
const removeFile = (index) => {
  const item = fileList.value[index]
  // 销毁pdfjs文档释放底层内存
  if (item.pdfDoc && typeof item.pdfDoc.destroy === 'function') {
    item.pdfDoc.destroy()
  }
  canvasRefMap.delete(`${item.uid}_1`)
  fileList.value.splice(index, 1)
}

// 拖拽排序逻辑
const handleDragStart = (index) => {
  dragOriginIndex = index
  dragIndex.value = index
  hoverIndex.value = null
  event.dataTransfer.setData('text/plain', 'sort')
}
const handleDragEnd = () => {
  dragIndex.value = null
  hoverIndex.value = null
  dragOriginIndex = null
}
const handleCardDragOver = (e) => {
  e.preventDefault()
  const targetDom = Array.from(e.currentTarget.children).find(child => {
    const rect = child.getBoundingClientRect()
    return e.clientX >= rect.left && e.clientX <= rect.right && e.clientY >= rect.top && e.clientY <= rect.bottom
  })
  if (!targetDom) {
    hoverIndex.value = null
    return
  }
  hoverIndex.value = Array.from(e.currentTarget.children).indexOf(targetDom)
}
const onListDrop = (e) => {
  hoverIndex.value = null
  // 只处理卡片排序拖拽，不处理外部文件
  if (!e.dataTransfer.getData('text/plain')) return
  const targetIndex = Array.from(e.currentTarget.children).findIndex(el => el.classList.contains('drag_target'))
  if (targetIndex === -1 || targetIndex === dragOriginIndex) return
  const temp = fileList.value[dragOriginIndex]
  fileList.value.splice(dragOriginIndex, 1)
  fileList.value.splice(targetIndex, 0, temp)
}

// 合并提交接口，成功后自动清空回收资源
const mergeAllPdf = async () => {
  if (fileList.value.length === 0) {
    ElMessage.warning('请先上传至少一个PDF文件')
    return
  }
  // 页码本地校验
  for (const item of fileList.value) {
    if (!item.start || !item.end || item.start > item.end || item.end > item.totalPage) {
      ElMessage.error(`【${item.file.name}】页码设置非法`)
      return
    }
  }

  exportLoading.value = true
  const loading = ElLoading.service({ text: '正在合并PDF...' })
  try {
    const formData = new FormData()
    fileList.value.forEach(item => formData.append('pdf_files', item.file))
    fileList.value.forEach(item => formData.append('starts', item.start))
    fileList.value.forEach(item => formData.append('ends', item.end))
    fileList.value.forEach(item => formData.append('passwords', item.password))

    console.log('文件数量', fileList.value.length)
    for (const entry of formData.entries()) {
      console.log(entry[0], entry[1])
    }

    const blob = await $api.post('merge/', formData, {
      responseType: 'blob'
    })
    // 下载合并文件
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `多文件合并_${new Date().getTime()}.pdf`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('合并完成，文件已下载')

    // 合并成功自动回收全部资源、清空列表
    resetAll()
  } catch (err) {
    console.log('完整错误', err)
    if (err.response?.data) {
      const reader = new FileReader()
      reader.readAsText(err.response.data)
      reader.onload = () => {
        try {
          const res = JSON.parse(reader.result)
          console.log('后端返回错误详情：', res)
          ElMessage.error(res.msg || '合并失败')
        } catch {
          ElMessage.error('服务端返回异常')
        }
      }
    } else {
      ElMessage.error('网络请求失败')
    }
  } finally {
    exportLoading.value = false
    loading.close()
  }
}

// 一键清空所有文件 + 完整资源回收
const resetAll = () => {
  // 销毁所有pdfjs文档
  fileList.value.forEach(item => {
    if (item.pdfDoc?.destroy) item.pdfDoc.destroy()
  })
  canvasRefMap.clear()
  fileList.value = []
  exportLoading.value = false
}

// 路由/页面销毁钩子：切页面强制释放全部内存
onUnmounted(() => {
  fileList.value.forEach(item => {
    if (item.pdfDoc && typeof item.pdfDoc.destroy === 'function') {
      item.pdfDoc.destroy()
    }
  })
  canvasRefMap.clear()
  fileList.value = []
  exportLoading.value = false
})
</script>

<style scoped>
html {
  font-size: 100%;
}
.pdf-editor-container {
  display: flex;
  width: 100%;
  height: 100vh;
  gap: 1em;
  padding: 1em;
  box-sizing: border-box;
  background: #f5f7fa;
}
.left-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow-y: auto;
  border-radius: 0.625em;
  transition: background-color 0.2s ease;
}
.left-area.drag_over_wrap {
  background-color: #ecf5ff;
}
.right-panel {
  width: 22em;
  background: #fff;
  border-radius: 0.5em;
  padding: 1em;
  box-shadow: 0 0.125em 0.75em rgba(0,0,0,0.08);
  display: flex;
  flex-direction: column;
  height:90%;
  justify-content: space-between;
  overflow-y: auto;
}
.panel-title {
  font-size: 1em;
  font-weight: 600;
  margin-bottom: 1em;
  text-align: center;
}
.split-all-desc {
  line-height: 1.6;
  color: #303133;
  padding: 0.5em;
  background: #f8f9fa;
  border-radius: 0.4em;
  margin-bottom: 1em;
}
.split-all-desc p {
  margin: 0.4em 0;
}
.success-tip {
  color: #00b42a !important;
  font-weight: 500;
}
.cut-list-title {
  font-weight: 500;
  margin: 0.75em 0 0.5em;
}
.cut-list {
  flex: 1;
  overflow-y: auto;
}
.empty-tip {
  color: #999;
  text-align: center;
  padding: 1.25em 0;
}
.full-btn {
  width: 100%;
  margin-top: 0.75em;
}
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
.center-btn {
  margin: 0 auto;
  display: block;
  margin-bottom: 1em;
}
.multi-pdf-wrap {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1.5em;
  padding: 1em;
}
.pdf-card {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 0.5em;
  padding: 0.7em;
  cursor: grab;
  transition: all 0.2s ease;
  transform: scale(0.96);
}
.pdf-card:active {
  cursor: grabbing;
}
.pdf-card.drag_target {
  border: 2px solid #409eff;
  background: #f0f7ff;
  transform: scale(0.98);
}
.pdf-card.dragging {
  opacity: 0.6;
  transform: scale(0.92);
}
.card-header {
  display: flex;
  align-items: center;
  gap: 0.5em;
  margin-bottom: 0.6em;
}
.card-index {
  width: 1.5em;
  height: 1.5em;
  background: #409eff;
  color: #fff;
  border-radius: 50%;
  text-align: center;
  font-size: 0.8em;
  line-height: 1.5em;
}
.card-name {
  flex: 1;
  font-size: 0.9em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pdf-canvas-box-small {
  background: #eee;
  padding: 0.4em;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4em;
  margin-bottom: 0.6em;
}
.pdf-page-item-mini {
  background: #fff;
  box-shadow: 0 0 4px rgba(0,0,0,0.1);
}
.page-label-mini {
  font-size: 0.7em;
  text-align: center;
  color: #666;
  padding: 2px;
}
canvas {
  display: block;
  max-width: 100%;
}
.card-setting {
  display: flex;
  flex-direction: column;
  gap: 0.5em;
}
.card-setting .row {
  display: flex;
  align-items: center;
  gap: 0.4em;
}
.total-tip {
  font-size: 0.75em;
  color: #666;
}
/* 上传占位卡片 */
.upload-placeholder-card {
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  background: #fafafa;
  border: 1px dashed #c0c4cc;
}
.upload-placeholder-card .placeholder-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.6em;
  text-align: center;
}
.placeholder-tip-main {
  font-size: 1em;
  color: #606266;
  margin: 0;
}
.placeholder-tip-sub {
  font-size: 0.8em;
  color: #909399;
  margin: 0;
}
.placeholder-upload-btn {
  font-size: 0.9em;
  width: 9em;
  height: 2.6em;
}
</style>