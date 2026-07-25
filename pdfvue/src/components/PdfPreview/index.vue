<template>
  <div class="pdf-view-wrap" role="region" aria-label="PDF预览区域">
    <div class="pdf-top-bar">
      <span class="file-name">{{ pdfFile.name }}</span>
      <el-button text type="danger" @click="$emit('reset')">重置</el-button>
    </div>
    <div class="pdf-canvas-box" ref="canvasWrapRef">
      <div v-for="page in pageList" :key="page.pageNum" class="pdf-page-item">
        <canvas :ref="el => bindCanvas(el, page.pageNum)"></canvas>
        <div class="page-label">第{{ page.pageNum }}页</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import * as pdfjsLib from 'pdfjs-dist'
import { ElMessage } from 'element-plus'

// 全局worker建议放到main.js，这里临时兼容
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js'
pdfjsLib.GlobalWorkerOptions.useWorkerFetch = true

const props = defineProps(['pdfFile', 'uploadLoading'])
const emit = defineEmits(['upload', 'reset', 'update:total-page'])

const canvasWrapRef = ref(null)
const canvasRefMap = new Map()
let pdfDoc = null
const pageList = ref([])

// 绑定canvas
const bindCanvas = (el, pageNum) => {
  if (el) canvasRefMap.set(pageNum, el)
  else canvasRefMap.delete(pageNum)
}

// 单页渲染
const renderSinglePage = async (pageNum) => {
  if (!pdfDoc) return
  const page = await pdfDoc.getPage(pageNum)
  const canvas = canvasRefMap.get(pageNum)
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const scale = 1.0
  const viewport = page.getViewport({ scale })
  canvas.width = viewport.width
  canvas.height = viewport.height
  await page.render({ canvasContext: ctx, viewport }).promise
}

// 对外暴露：加载渲染PDF
const renderPdf = async (buffer) => {
  // 先销毁旧文档释放内存
  destroyPdf()
  try {
    const task = pdfjsLib.getDocument(buffer)
    pdfDoc = await task.promise
    const total = pdfDoc.numPages
    pageList.value = Array.from({ length: total }, (_, i) => ({ pageNum: i + 1 }))
    await nextTick()
    for (let i = 1; i <= total; i++) {
      await renderSinglePage(i)
    }
    ElMessage.success('PDF解析完成')
    emit('update:total-page', total)
  } catch (err) {
    ElMessage.error('PDF解析失败，文件损坏或非标准PDF')
    console.error(err)
  }
}

// 销毁释放资源
const destroyPdf = () => {
  if (pdfDoc && typeof pdfDoc.destroy === 'function') {
    pdfDoc.destroy()
  }
  pdfDoc = null
  pageList.value = []
  canvasRefMap.clear()
}

// 暴露给父页面调用
defineExpose({
  renderPdf,
  destroyPdf
})
</script>

<style scoped>
.pdf-top-bar {
  display: flex;
  align-items: center;
  gap: 0.75em;
  margin-bottom: 0.75em;
}
.file-name {
  color: #666;
}
.pdf-canvas-box {
  height: 37.5em;
  overflow-y: auto;
  overflow-x: hidden;
  background: #e6e6e6;
  padding: 1.25em;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1em;
}
.pdf-page-item {
  background: #fff;
  box-shadow: 0 0.125em 0.5em rgba(0,0,0,0.1);
}
.page-label {
  text-align: center;
  padding: 0.375em;
  font-size: 0.8125em;
  color: #666;
}
canvas {
  display: block;
}
</style>