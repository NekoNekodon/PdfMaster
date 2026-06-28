<template>
  <div class="pdf-editor-container" role="main" aria-label="PDF工具箱-拆分提取页面">
    <!-- 左侧上传&预览区 -->
    <div class="left-area">
      <!-- 拖拽上传区域 -->
      <div
        v-if="!pdfFile"
        class="upload-drop-area"
        :class="{ drag_over: isDragOver }"
        role="region"
        aria-label="PDF文件上传区域"
        @drop.prevent="handleDrop"
        @dragover.prevent="isDragOver = true"
        @dragleave="isDragOver = false"
        tabindex="0"
        @keydown.enter="$refs.fileInputRef.click()"
      >
        <UploadFilled 
          style="width: 9.375em; height: 9.375em; color: #409eff;" 
          aria-hidden="true"
        />
        <p class="tip" role="heading" aria-level="2">将PDF拖拽到此处</p>
        <p class="sub-tip">或点击按钮选择本地PDF</p>

        <el-button 
          type="primary" 
          class="default-btn" 
          @click="fileInputRef.click()"
          aria-label="打开文件选择框，选择本地PDF文件"
        >
          选择PDF文件
        </el-button>

        <input 
          ref="fileInputRef" 
          type="file" 
          accept=".pdf" 
          hidden 
          @change="handleFileSelect"
          id="pdf-file-input"
          aria-labelledby="pdf-file-label"
        />
      </div>

      <!-- PDF预览面板 -->
      <div v-else class="pdf-view-wrap" role="region" aria-label="PDF预览区域">
        <div class="pdf-top-bar">
          <el-button 
            type="success" 
            @click="uploadPdf" 
            :loading="uploadLoading"
            aria-label="确认上传当前PDF文件至后端"
          >
            确认上传PDF
          </el-button>
          <span class="file-name" aria-label="当前已选文件名称">{{ pdfFile.name }}</span>
          <el-button 
            text 
            type="danger" 
            @click="resetAll"
            aria-label="重置所有操作，清空PDF与片段列表"
          >
            重置
          </el-button>
        </div>

        <div class="pdf-canvas-box" ref="canvasWrapRef" role="feed" aria-label="PDF分页预览画布">
          <div 
            v-for="page in pageList" 
            :key="page.pageNum" 
            class="pdf-page-item"
            role="article"
            :aria-label="`PDF第${page.pageNum}页预览`"
          >
            <canvas 
              :ref="el => setCanvasRef(el, page.pageNum)"
              :aria-label="`第${page.pageNum}页PDF画布`"
              role="img"
            ></canvas>
            <div class="page-label">第{{ page.pageNum }}页</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧截取面板 -->
    <div class="right-panel" role="complementary" aria-label="PDF片段截取操作面板">
      <div class="panel-title" role="heading" aria-level="2">PDF片段截取</div>

      <el-form :model="cutForm" label-width="5em">
        <el-form-item label="起始页" label-for="start-page">
          <el-input-number 
            v-model="cutForm.start" 
            :min="1" 
            :max="Math.max(totalPage, 1)"
            id="start-page"
            aria-label="输入截取起始页码"
            style="width: 8em;"
          />
        </el-form-item>
        <el-form-item label="结束页" label-for="end-page">
          <el-input-number 
            v-model="cutForm.end" 
            :min="1" 
            :max="Math.max(totalPage, 1)"
            id="end-page"
            aria-label="输入截取结束页码"
            style="width: 8em;"
          />
        </el-form-item>
        <el-form-item label="片段名称" label-for="cut-name">
          <el-input 
            v-model="cutForm.name" 
            placeholder="如：章节一"
            id="cut-name"
            aria-label="输入当前截取片段自定义名称"
          />
        </el-form-item>
        <el-form-item>
          <el-button 
            type="primary" 
            class="default-btn" 
            @click="addCutRange"
            aria-label="保存当前页码范围为截取片段"
          >
            添加截取片段
          </el-button>
        </el-form-item>
      </el-form>

      <div class="cut-list-title" role="heading" aria-level="3">已保存片段列表</div>
      <div class="cut-list" role="list">
        <div 
          v-if="cutRangeList.length === 0" 
          class="empty-tip"
          role="status"
          aria-live="polite"
        >
          暂无截取片段
        </div>
        <div 
          v-for="(item, idx) in cutRangeList" 
          :key="idx" 
          class="cut-item"
          role="listitem"
          :aria-label="`片段：${item.name}，页码${item.start}至${item.end}`"
        >
          <div class="cut-item-left">
            <div class="cut-name">{{ item.name }}</div>
            <div class="cut-range">{{ item.start }} ~ {{ item.end }} 页</div>
          </div>
          <el-button 
            text 
            type="danger" 
            icon="Close"
            class="del-close-btn" 
            @click="cutRangeList.splice(idx, 1)"
            aria-label="删除当前保存的截取片段"
          />
        </div>
      </div>

      <el-divider />
      <el-button 
        type="success" 
        class="default-btn full-btn center-btn" 
        @click="exportAllCut"
        aria-label="批量导出全部已保存片段为PDF文件"
      >
        全部导出
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, getCurrentInstance } from 'vue'
import * as pdfjsLib from 'pdfjs-dist'
import html2canvas from 'html2canvas'
import { ElMessage, ElLoading, ElInput } from 'element-plus'

// 获取全局$api请求实例
const { proxy } = getCurrentInstance()
const $api = proxy.$api

// CDN worker + 开启字体远程加载，解决CMap报错
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js'
pdfjsLib.GlobalWorkerOptions.useWorkerFetch = true

// DOM Refs
const fileInputRef = ref(null)
const canvasWrapRef = ref(null)
const canvasRefMap = new Map()

// 拖拽状态
const isDragOver = ref(false)

// PDF全局数据
let pdfDoc = null
const pdfFile = ref(null)
const totalPage = ref(0)
const pageList = ref([])
const uploadLoading = ref(false)

// 截取表单
const cutForm = reactive({
  start: 1,
  end: 1,
  name: ''
})
const cutRangeList = ref([])

// 保存Canvas DOM映射
const setCanvasRef = (el, pageNum) => {
  if (el) canvasRefMap.set(pageNum, el)
  else canvasRefMap.delete(pageNum)
}

// 拖拽文件
const handleDrop = (e) => {
  isDragOver.value = false
  const files = e.dataTransfer.files
  if (!files || files.length === 0) return
  handlePdfFile(files[0])
}

// 选择文件
const handleFileSelect = (e) => {
  const target = e.target
  if (!target.files.length) return
  handlePdfFile(target.files[0])
}

// 校验并解析PDF
const handlePdfFile = async (file) => {
  if (file.type !== 'application/pdf') {
    ElMessage.error('仅支持 .pdf 文件')
    return
  }
  pdfFile.value = file
  const buffer = await file.arrayBuffer()
  await renderAllPdfPages(buffer)
}

// 渲染全部页面
const renderAllPdfPages = async (buffer) => {
  try {
    const task = pdfjsLib.getDocument(buffer)
    pdfDoc = await task.promise
    totalPage.value = pdfDoc.numPages
    pageList.value = Array.from({ length: totalPage.value }, (_, i) => ({ pageNum: i + 1 }))
    cutForm.end = totalPage.value
    await nextTick()
    // 循环渲染每一页
    for (let i = 1; i <= totalPage.value; i++) {
      await renderSinglePage(i)
    }
    ElMessage.success('PDF解析完成')
  } catch (err) {
    ElMessage.error('PDF解析失败，文件损坏或非标准PDF')
    console.error(err)
  }
}

// 渲染单页，固定缩放1倍
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

// 模拟上传接口
const uploadPdf = async () => {
  if (!pdfFile.value) return
  uploadLoading.value = true
  const loading = ElLoading.service({ text: '文件上传中...' })
  try {
    const formData = new FormData()
    formData.append('pdf', pdfFile.value)
    await new Promise(res => setTimeout(res, 1200))
    ElMessage.success('PDF上传成功！')
  } catch (err)
    {ElMessage.error('上传失败，请重试')
  } finally {
    uploadLoading.value = false
    loading.close()
  }
}


// 添加截取片段
const addCutRange = () => {
  // 先判断是否解析PDF
  if (!pdfDoc) {
    ElMessage.warning('请先上传并正常解析PDF文件')
    return
  }
  const { start, end, name } = cutForm
  if (!name) {
    ElMessage.warning('请填写片段名称')
    return
  }
  if (start > end) {
    ElMessage.warning('起始页码不能大于结束页码')
    return
  }
  cutRangeList.value.push({ start, end, name })
  ElMessage.success('截取片段添加成功')
}

// 预览片段提示
const previewCut = (item) => {
  ElMessage.info(`片段【${item.name}】页码范围：${item.start} ~ ${item.end}`)
}

/**
 * 调用Django后端接口导出单个PDF片段
 * @param {Number} start 起始页
 * @param {Number} end 结束页
 * @param {String} name 片段名称
 * @param {String} pwd 加密PDF密码
 */
const exportByBackend = async (start, end, name, pwd = "") => {
  if (!pdfFile.value) {
    ElMessage.warning("请先上传PDF文件")
    return
  }
  const loading = ElLoading.service({ text: "后端正在处理PDF..." })
  try {
    const formData = new FormData()
    formData.append("pdf_file", pdfFile.value)
    formData.append("page1", start)
    formData.append("page2", end)
    formData.append("password", pwd)

    // 请求后端二进制流
    const blob = await $api.post("/split_extract/", formData, {
      responseType: "blob"
    })

    // 浏览器下载
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `${name}.pdf`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success(`【${name}】PDF导出完成`)
  } catch (err)
    // 解析后端返回的错误JSON
    {const reader = new FileReader()
    reader.readAsText(err.response.data)
    reader.onload = () => {
      const res = JSON.parse(reader.result)
      ElMessage.error(res.msg)
    }
    } finally {
      loading.close()
    }
}

// 批量导出全部截取片段（调用后端生成PDF）
const exportAllCut = async () => {
  if (cutRangeList.value.length === 0) {
    ElMessage.warning('暂无截取片段')
    return
  }
  // 循环逐个导出
  for (const item of cutRangeList.value) {
    await exportByBackend(item.start, item.end, item.name)
  }
}

// 全部重置
const resetAll = () => {
  pdfFile.value = null
  pdfDoc = null
  totalPage.value = 0
  pageList.value = []
  cutRangeList.value = []
  canvasRefMap.clear()
  cutForm.start = 1
  cutForm.end = 1
  cutForm.name = ''
}
</script>

<style scoped>
/* 全局基准字号，1em = 16px */
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
  height: 100%; /* 占满父容器高度 */
  overflow-y: auto;
}
.right-panel {
  width: 20em;
  background: #fff;
  border-radius: 0.5em;
  padding: 1em;
  box-shadow: 0 0.125em 0.75em rgba(0,0,0,0.08);
  display: flex;
  flex-direction: column;
  height:90%; /* 关键：侧边栏高度100%填满页面 */
  justify-content: space-between;
  overflow-y: auto;
}
.panel-title {
  font-size: 1em;
  font-weight: 600;
  margin-bottom: 1em;
}
.cut-list-title {
  font-weight: 500;
  margin: 0.75em 0 0.5em;
}
.cut-list {
  flex: 1;
  overflow-y: auto;
}
.cut-item {
  border: 1px solid #eee;
  border-radius: 0.375em;
  padding: 0.5em;
  margin-bottom: 0.5em;
}
.cut-name {
  font-weight: 500;
}
.cut-range {
  color: #666;
  font-size: 0.8125em;
}
.cut-ops {
  margin-top: 0.25em;
  display: flex;
  gap: 0.375em;
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

/* 拖拽上传 */
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
.drag_over {
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

/* PDF预览 */
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
.cut-item {
  border: 1px solid #eee;
  border-radius: 0.375em;
  padding: 0.5em;
  margin-bottom: 0.5em;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5em;
}
.cut-item-left {
  flex: 1;
}
.cut-name {
  font-weight: 500;
}
.cut-range {
  color: #666;
  font-size: 0.8125em;
}
.del-close-btn {
  padding: 0;
  font-size: 1em;
}
</style>