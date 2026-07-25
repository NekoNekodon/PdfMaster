<template>
  <div class="pdf-editor-container" role="main" aria-label="PDF工具箱-全部拆分PDF">
    <!-- 左侧上传&预览区 -->
    <div class="left-area">
      <PdfUploadDrag
        v-if="!pdfFile"
        @file-select="handlePdfFile"
      />
      <PdfPreview
        v-else
        ref="previewRef"
        :pdf-file="pdfFile"
        :upload-loading="uploadLoading"
        @upload="uploadPdf"
        @reset="resetAll"
        @update:total-page="handleUpdateTotal"
      />
    </div>

    <!-- 右侧全部拆分面板 -->
    <div class="right-panel" role="complementary" aria-label="PDF全部拆分操作面板">
      <div class="panel-title" role="heading" aria-level="2">PDF全部拆分</div>
      <el-divider />

      <div class="split-all-desc">
        <p>✅ 一键将PDF<strong>每页拆分为一个独立PDF</strong></p>
        <p>✅ 自动打包为ZIP压缩包下载</p>
        <p>✅ 无需设置页码，直接导出全部页面</p>
      </div>

      <div class="cut-list" role="list">
        <div 
          class="empty-tip success-tip"
          role="status"
          aria-live="polite"
        >
          共 {{ totalPage }} 页
        </div>
      </div>

      <el-divider />
      <el-button 
        type="success" 
        class="default-btn full-btn center-btn" 
        @click="exportAllSplitZip"
        :loading="exportLoading"
        aria-label="导出全部页面压缩包ZIP"
      >
        导出全部ZIP
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, getCurrentInstance } from 'vue'
import * as pdfjsLib from 'pdfjs-dist'
import { ElMessage, ElLoading } from 'element-plus'
import PdfUploadDrag from '../components/PdfUploadDrag/index.vue'
import PdfPreview from '../components/PdfPreview/index.vue'

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

// 子组件实例
const previewRef = ref(null)


// 截取表单
const cutForm = reactive({
  start: 1,
  end: 1,
  name: ''
})
const cutRangeList = ref([])

// 接收预览组件传回总页数
const handleUpdateTotal = (val) => {
  totalPage.value = val
  cutForm.end = val
}

// 接收上传文件，交给预览组件解析渲染
const handlePdfFile = async (file) => {
  if (file.type !== 'application/pdf') {
    ElMessage.error('仅支持 .pdf 文件')
    return
  }
  pdfFile.value = file
  const buffer = await file.arrayBuffer()
  await previewRef.value.renderPdf(buffer)
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
  } catch (err) {
    ElMessage.error('上传失败，请重试')
  } finally {
    uploadLoading.value = false
    loading.close()
  }
}

/**
 * 调用接口：全部拆分为ZIP
 */
const exportAllSplitZip = async () => {
  if (!pdfFile.value) {
    ElMessage.warning('请先上传PDF文件')
    return
  }
  exportLoading.value = true
  const loading = ElLoading.service({ text: '正在每页拆分并打包ZIP...' })
  
  try {
    const formData = new FormData()
    formData.append('pdf_file', pdfFile.value)
    
    const blob = await $api.post('/split_all_zip/', formData, {
      responseType: 'blob'
    })
    
    // 下载ZIP
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `PDF全部拆分_${new Date().getTime()}.zip`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('全部拆分完成，ZIP已下载')
  } catch (err) {
    if (err.response && err.response.data) {
      const reader = new FileReader()
      reader.readAsText(err.response.data)
      reader.onload = () => {
        try {
          const res = JSON.parse(reader.result)
          ElMessage.error(res.msg || 'ZIP导出失败')
        } catch (e) {
          ElMessage.error('服务端返回数据异常')
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

// 全部重置
const resetAll = () => {
  pdfFile.value = null
  pdfDoc = null
  totalPage.value = 0
  pageList.value = []
  canvasRefMap.clear()
  exportLoading.value = false
}
</script>

<style scoped>

</style>