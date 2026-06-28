<template>
  <div class="pdf-editor-container" role="main" aria-label="PDF工具箱-PDF转图片">
    <!-- 左侧上传&预览区（和你拆分页面完全一模一样，无改动） -->
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

    <!-- 右侧转图片操作面板（结构、样式完全对标你拆分页面） -->
    <div class="right-panel" role="complementary" aria-label="PDF转图片操作面板">
      <div class="panel-title" role="heading" aria-level="2">PDF 转图片设置</div>

      <!-- 全局转换参数 -->
      <el-form :model="imgBaseForm" label-width="5em">
        <el-form-item label="图片格式">
          <el-switch
            v-model="imgBaseForm.isPng"
            active-text="PNG"
            inactive-text="JPG"
            @change="onFormatChange"
          />
          <div class="tip-text">{{ imgBaseForm.type === 'jpg' ? '有损压缩，体积更小' : '无损透明，画质无损' }}</div>
        </el-form-item>
        <el-form-item label="画质档位">
          <el-select 
            v-model="imgBaseForm.qualityLevel" 
            placeholder="选择压缩档位" 
            style="width:100%"
            :disabled="imgBaseForm.type === 'png'"
          >
            <el-option label="原图（100）" value="100" />
            <el-option label="大（90）" value="90" />
            <el-option label="中（75）" value="75" />
            <el-option label="小（60）" value="60" />
          </el-select>
        </el-form-item>
        <el-form-item label="文档密码">
          <el-input 
            v-model="imgBaseForm.password" 
            placeholder="加密PDF请填写密码，无加密留空"
            show-password
          />
        </el-form-item>
      </el-form>

      <el-divider />

      <!-- 添加转换片段表单（和拆分页面布局完全一致） -->
      <el-form :model="rangeForm" label-width="5em">
        <el-form-item label="起始页" label-for="start-page">
          <el-input-number 
            v-model="rangeForm.start" 
            :min="1" 
            :max="Math.max(totalPage, 1)"
            id="start-page"
            aria-label="输入转换起始页码"
            style="width: 8em;"
          />
        </el-form-item>
        <el-form-item label="结束页" label-for="end-page">
          <el-input-number 
            v-model="rangeForm.end" 
            :min="1" 
            :max="Math.max(totalPage, 1)"
            id="end-page"
            aria-label="输入转换结束页码"
            style="width: 8em;"
          />
        </el-form-item>
        <el-form-item label="片段名称" label-for="cut-name">
          <el-input 
            v-model="rangeForm.name" 
            placeholder="留空自动使用页码范围"
            id="cut-name"
            aria-label="输入当前转换片段自定义名称"
          />
        </el-form-item>
        <el-form-item>
          <el-button 
            type="primary" 
            class="default-btn" 
            @click="addImageRange"
            aria-label="保存当前页码范围为转换片段"
          >
            添加转换片段
          </el-button>
        </el-form-item>
      </el-form>

      <div class="cut-list-title" role="heading" aria-level="3">已保存转换片段列表</div>
      <div class="cut-list" role="list">
        <div 
          v-if="imgRangeList.length === 0" 
          class="empty-tip"
          role="status"
          aria-live="polite"
        >
          暂无转换片段
        </div>
        <div 
          v-for="(item, idx) in imgRangeList" 
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
            @click="imgRangeList.splice(idx, 1)"
            aria-label="删除当前保存的转换片段"
          />
        </div>
      </div>

      <el-divider />
      <el-button 
        type="success" 
        class="default-btn full-btn center-btn" 
        @click="exportAllImageZip"
        aria-label="批量导出全部已保存片段为图片压缩包"
        :loading="exportLoading"
      >
        全部导出
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, getCurrentInstance, watch } from 'vue'
import { ElMessage, ElLoading } from 'element-plus'

// 获取全局$api请求实例
const { proxy } = getCurrentInstance()
const $api = proxy.$api

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
const exportLoading = ref(false)

// 全局图片转换配置
const imgBaseForm = reactive({
  isPng: false,
  type: 'jpg',
  qualityLevel: 85,
  password: ''
})

// 添加片段表单
const rangeForm = reactive({
  start: 1,
  end: 1,
  name: ''
})
const imgRangeList = ref([])

// 监听总页数变化，自动填充结束页码
watch(totalPage, (val) => {
  if (val > 0) {
    rangeForm.end = val
  }
})

// 切换图片格式
const onFormatChange = () => {
  imgBaseForm.type = imgBaseForm.isPng ? 'png' : 'jpg'
}

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
    rangeForm.end = totalPage.value
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

// 添加转换片段（留空名称自动填充页码）
const addImageRange = () => {
  // 先判断是否解析PDF
  if (!pdfDoc) {
    ElMessage.warning('请先上传并正常解析PDF文件')
    return
  }
  const { start, end, name } = rangeForm
  if (start > end) {
    ElMessage.warning('起始页码不能大于结束页码')
    return
  }
  // 名称为空自动使用 起始-结束
  const realName = name.trim() || `${start}-${end}`
  imgRangeList.value.push({ start, end, name: realName })
  ElMessage.success('转换片段添加成功')
  // 清空名称输入框
  rangeForm.name = ''
}

/**
 * 调用Django后端接口导出单个图片压缩包
 * @param {Number} start 起始页
 * @param {Number} end 结束页
 * @param {String} name 片段名称
 * @param {String} pwd 加密PDF密码
 */
const exportSingleImageZip = async (start, end, name, pwd = "") => {
  if (!pdfFile.value) {
    ElMessage.warning("请先上传PDF文件")
    return
  }
  const { type, qualityLevel } = imgBaseForm
  const formData = new FormData()
  formData.append("pdf_file", pdfFile.value)
  formData.append("type", type)
  formData.append("quality", qualityLevel)
  formData.append("password", pwd)
  formData.append("page1", start)
  formData.append("page2", end)

  // 请求后端二进制流
  const blob = await $api.post("/toimg/", formData, {
    responseType: "blob"
  })

  // 浏览器下载
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `${name}_imgs.zip`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success(`【${name}】图片包导出完成`)
}

// 批量导出全部转换片段
const exportAllImageZip = async () => {
  if (imgRangeList.value.length === 0) {
    ElMessage.warning('暂无转换片段')
    return
  }
  exportLoading.value = true
  const loading = ElLoading.service({ text: "后端正在批量生成图片压缩包..." })
  try {
    // 循环逐个导出
    for (const item of imgRangeList.value) {
      await exportSingleImageZip(item.start, item.end, item.name, imgBaseForm.password)
    }
  } catch (err)
    {const reader = new FileReader()
    reader.readAsText(err.response.data)
    reader.onload = () => {
      const res = JSON.parse(reader.result)
      ElMessage.error(res.msg || '转换失败')
    }
  } finally {
    exportLoading.value = false
    loading.close()
  }
}

// 全部重置
const resetAll = () => {
  pdfFile.value = null
  pdfDoc = null
  totalPage.value = 0
  pageList.value = []
  imgRangeList.value = []
  canvasRefMap.clear()
  // 重置全局转换参数
  imgBaseForm.isPng = false
  imgBaseForm.type = 'jpg'
  imgBaseForm.qualityLevel = 85
  imgBaseForm.password = ''
  // 重置片段表单
  rangeForm.start = 1
  rangeForm.end = 1
  rangeForm.name = ''
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
.tip-text {
  font-size: 0.8125em;
  color: #909399;
  margin-top: 0.3em;
}
</style>