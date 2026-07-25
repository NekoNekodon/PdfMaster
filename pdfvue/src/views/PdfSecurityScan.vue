<template>
  <div class="pdf-editor-container" role="main" aria-label="PDF工具箱-PDF安全检测">
    <!-- 左侧上传&预览区 完全复用公共组件 -->
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

    <!-- 右侧安全检测面板 -->
    <div class="right-panel" role="complementary" aria-label="PDF安全检测操作面板">
      <div class="panel-title" role="heading" aria-level="2">PDF 安全扫描</div>
      <el-divider />

      <div class="split-all-desc">
        <p>✅ ClamAV 病毒引擎查杀恶意样本</p>
        <p>✅ YARA 规则检测自动脚本/OpenAction</p>
        <p>✅ 加密PDF支持密码解密扫描</p>
      </div>

      <!-- 密码输入框 -->
      <el-form :model="scanForm" label-width="5em">
        <el-form-item label="文档密码">
          <el-input
            v-model="scanForm.password"
            placeholder="加密PDF填写打开密码，无加密留空"
            show-password
          />
        </el-form-item>
      </el-form>

      <el-divider />

      <!-- 扫描结果展示区域 -->
      <div class="cut-list" role="list">
        <div
          v-if="scanResult === null"
          class="empty-tip"
          role="status"
          aria-live="polite"
        >
          上传PDF后点击扫描检测安全状态
        </div>
        <div
          v-else
          :class="scanResult.safe ? 'empty-tip success-tip' : 'empty-tip danger-tip'"
          role="status"
          aria-live="polite"
        >
          {{ scanResult.msg }}
        </div>
      </div>

      <el-divider />
      <el-button
        type="primary"
        class="default-btn full-btn center-btn"
        @click="runSecurityScan"
        :loading="scanLoading"
        aria-label="执行PDF双重安全扫描"
      >
        开始安全扫描
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, getCurrentInstance } from 'vue'
import * as pdfjsLib from 'pdfjs-dist'
import { ElMessage, ElLoading } from 'element-plus'
import PdfUploadDrag from '../components/PdfUploadDrag/index.vue'
import PdfPreview from '../components/PdfPreview/index.vue'

// 全局请求实例
const { proxy } = getCurrentInstance()
const $api = proxy.$api

// PDF Worker 配置（和其他页面保持一致）
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js'
pdfjsLib.GlobalWorkerOptions.useWorkerFetch = true

// 组件ref
const previewRef = ref(null)

// PDF基础数据
const pdfFile = ref(null)
const totalPage = ref(0)
const uploadLoading = ref(false)
const scanLoading = ref(false)

// 扫描表单：密码
const scanForm = reactive({
  password: ''
})

// 扫描结果存储
const scanResult = ref(null)

// 接收预览组件传回总页数
const handleUpdateTotal = (val) => {
  totalPage.value = val
}

// 接收上传文件，交给预览渲染
const handlePdfFile = async (file) => {
  if (file.type !== 'application/pdf') {
    ElMessage.error('仅支持 .pdf 文件')
    return
  }
  pdfFile.value = file
  scanResult.value = null // 新文件清空上次扫描结果
  const buffer = await file.arrayBuffer()
  await previewRef.value.renderPdf(buffer)
}

// 模拟上传接口（和其他页面统一）
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

// 核心：调用后端安全扫描接口
const runSecurityScan = async () => {
  if (!pdfFile.value) {
    ElMessage.warning('请先上传PDF文件')
    return
  }
  scanLoading.value = true
  const loading = ElLoading.service({ text: 'ClamAV + YARA 双重扫描中...' })
  try {
    const formData = new FormData()
    formData.append('pdf_file', pdfFile.value)
    formData.append('password', scanForm.password)

    // 修复：request拦截器已自动返回data，不需要 .data
    const res = await $api.post('/security_scan/', formData)
    scanResult.value = res
    if (res.safe) {
      ElMessage.success('文档安全无风险')
    } else {
      ElMessage.warning('检测到PDF存在安全隐患')
    }
  } catch (err) {
    scanResult.value = null
    if (err.response) {
      const data = err.response.data
      ElMessage.error(data.msg || '扫描校验失败')
    } else {
      ElMessage.error('网络异常，请检查后端服务是否启动、接口地址是否正确')
    }
  } finally {
    scanLoading.value = false
    loading.close()
  }
}

// 重置全部状态
const resetAll = () => {
  pdfFile.value = null
  totalPage.value = 0
  scanResult.value = null
  scanForm.password = ''
  scanLoading.value = false
  previewRef.value?.destroyPdf()
}
</script>

<style scoped>
.danger-tip {
  color: #f53f3f !important;
  font-weight: 500;
}
</style>