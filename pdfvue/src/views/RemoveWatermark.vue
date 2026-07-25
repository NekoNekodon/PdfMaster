<template>
  <div class="pdf-editor-container" role="main" aria-label="PDF工具箱-去除文本水印">
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
            aria-label="重置所有操作，清空PDF"
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

    <!-- 右侧去水印面板 -->
    <div class="right-panel" role="complementary" aria-label="PDF去除水印操作面板">
      <div class="panel-title" role="heading" aria-level="2">PDF去除文本水印</div>
      <el-divider />

      <div class="split-all-desc">
        <p>✅ 批量擦除页面内指定水印文字</p>
        <p>✅ 每个水印关键词单独占一行输入</p>
        <p>✅ 永久移除文字，保留PDF图片与表格</p>
      </div>

      <div class="cut-list-title" role="heading" aria-level="3">输入水印关键词</div>
      <el-input
        v-model="keywordText"
        type="textarea"
        :rows="4"
        placeholder="示例：
CDH573
CFA网课咨询
微信资料"
        clearable
      />
      <div class="tip-desc">每一行填写一个水印文本，无需逗号分隔</div>

      <el-divider />
      <div class="cut-list" role="list">
        <div 
          class="empty-tip success-tip"
          role="status"
          aria-live="polite"
        >
          文档共 {{ totalPage }} 页，匹配水印文本将自动清除
        </div>
      </div>

      <el-divider />
      <el-button 
        type="success" 
        class="default-btn full-btn center-btn" 
        @click="exportCleanPdf"
        :loading="exportLoading"
        aria-label="清除水印并下载处理后PDF"
      >
        导出
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, getCurrentInstance } from 'vue'
import * as pdfjsLib from 'pdfjs-dist'
import { ElMessage, ElLoading } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'

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
const exportLoading = ref(false)

// 水印关键词输入
const keywordText = ref('')

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
    await nextTick()
    // 循环渲染每一页
    for (let i = 1; i <= totalPage.value; i++) {
      await renderSinglePage(i)
    }
    ElMessage.success('PDF解析完成')
  } catch (err)
    {ElMessage.error('PDF解析失败，文件损坏或非标准PDF')
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

/**
 * 调用后端去除水印接口
 */
const exportCleanPdf = async () => {
  if (!pdfFile.value) {
    ElMessage.warning('请先上传PDF文件')
    return
  }
  const rawText = keywordText.value.trim()
  if (!rawText) {
    ElMessage.warning('请输入至少一个水印关键词，一行一个')
    return
  }

  // 关键修改：按换行分割，不再逗号分割
  // 兼容 \r\n windows换行 和 \n 换行
  const keywordLines = rawText.split(/[\r\n]+/)
  // 过滤空行、去除每行首尾空格
  const keywordList = keywordLines.map(item => item.trim()).filter(item => item)
  if (keywordList.length === 0) {
    ElMessage.warning('关键词不能为空行')
    return
  }

  exportLoading.value = true
  const loading = ElLoading.service({ text: '正在清除水印文字...' })
  
  try {
    const formData = new FormData()
    formData.append('pdf_file', pdfFile.value)
    // 用特殊分隔符 ||| 拼接数组传给后端，方便后端拆分
    formData.append('keyword', keywordList.join('|||'))
    
    const blob = await $api.post('/remove-keyword/', formData, {
      responseType: 'blob'
    })
    
    // 下载处理后的PDF
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `去除水印_${pdfFile.value.name}`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('水印清除完成，文件已下载')
  } catch (err)
    {if (err.response && err.response.data) {
      const reader = new FileReader()
      reader.readAsText(err.response.data)
      reader.onload = () => {
        try {
          const res = JSON.parse(reader.result)
          ElMessage.error(res.msg || '水印清除失败')
        } catch (e) {
          ElMessage.error('服务端返回数据异常')
        }
      }
    } else {
      ElMessage.error('网络请求失败，请检查后端服务')
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
  canvasRefMap.clear()
  keywordText.value = ''
  exportLoading.value = false
}
</script>

<style scoped>

</style>