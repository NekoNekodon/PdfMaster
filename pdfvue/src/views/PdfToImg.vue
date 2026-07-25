<template>
  <div class="pdf-editor-container" role="main" aria-label="PDF工具箱-PDF转图片">
    <!-- 左侧复用上传+预览组件，不再手写DOM -->
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
        @update:total-page="(val) => rangeForm.end = val"
      />
    </div>

    <!-- 右侧转图片操作面板 -->
    <div class="right-panel" role="complementary" aria-label="PDF转图片操作面板">
      <div class="panel-title" role="heading" aria-level="2">PDF 转图片设置</div>

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
          v-for="item in imgRangeList"
          :key="item.uid"
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
            @click="removeImageItem(item.uid)"
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
import * as pdfjsLib from 'pdfjs-dist'
import { ElMessage, ElLoading } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import PdfUploadDrag from '../components/PdfUploadDrag/index.vue'
import PdfPreview from '../components/PdfPreview/index.vue'

const { proxy } = getCurrentInstance()
const $api = proxy.$api

// PDF Worker 全局配置
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js'
pdfjsLib.GlobalWorkerOptions.useWorkerFetch = true

const previewRef = ref(null)

// PDF全局数据
const pdfFile = ref(null)
const totalPage = ref(0)
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

// 监听总页数变化
watch(totalPage, (val) => {
  if (val > 0) rangeForm.end = val
})

// 切换图片格式
const onFormatChange = () => {
  imgBaseForm.type = imgBaseForm.isPng ? 'png' : 'jpg'
}

// 接收上传文件
const handlePdfFile = async (file) => {
  if (file.type !== 'application/pdf') {
    ElMessage.error('仅支持 .pdf 文件')
    return
  }
  pdfFile.value = file
  const buffer = await file.arrayBuffer()
  await previewRef.value.renderPdf(buffer)
}

// 模拟上传接口（修复缺少大括号语法错误）
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

// 添加转换片段，生成唯一uid
const addImageRange = () => {
  if (!pdfFile.value) {
    ElMessage.warning('请先上传并正常解析PDF文件')
    return
  }
  const { start, end, name } = rangeForm
  if (start > end) {
    ElMessage.warning('起始页码不能大于结束页码')
    return
  }
  const realName = name.trim() || `${start}-${end}`
  imgRangeList.value.push({
    uid: Date.now() + '_' + Math.random().toString(36).slice(2),
    start,
    end,
    name: realName
  })
  ElMessage.success('转换片段添加成功')
  rangeForm.name = ''
}

// 删除单条片段
const removeImageItem = (uid) => {
  const idx = imgRangeList.value.findIndex(i => i.uid === uid)
  if (idx > -1) imgRangeList.value.splice(idx, 1)
}

// 导出单个图片包（补全/api前缀）
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

  const blob = await $api.post("/toimg/", formData, {
    responseType: "blob"
  })

  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `${name}_imgs.zip`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success(`【${name}】图片包导出完成`)
}

// 批量导出（修复catch语法错误、二进制解析）
const exportAllImageZip = async () => {
  if (imgRangeList.value.length === 0) {
    ElMessage.warning('暂无转换片段')
    return
  }
  exportLoading.value = true
  const loading = ElLoading.service({ text: "后端正在批量生成图片压缩包..." })
  try {
    for (const item of imgRangeList.value) {
      await exportSingleImageZip(item.start, item.end, item.name, imgBaseForm.password)
    }
  } catch (err) {
    if (err?.response?.data) {
      try {
        const buf = await err.response.data.arrayBuffer()
        const txt = new TextDecoder().decode(new Uint8Array(buf))
        const res = JSON.parse(txt)
        ElMessage.error(res.msg || '转换失败')
      } catch {
        ElMessage.error('服务端返回数据解析异常')
      }
    } else {
      ElMessage.error('网络请求失败，请检查后端')
    }
  } finally {
    exportLoading.value = false
    loading.close()
  }
}

// 全部重置（增加销毁pdf资源）
const resetAll = () => {
  pdfFile.value = null
  totalPage.value = 0
  imgRangeList.value = []
  imgBaseForm.isPng = false
  imgBaseForm.type = 'jpg'
  imgBaseForm.qualityLevel = 85
  imgBaseForm.password = ''
  rangeForm.start = 1
  rangeForm.end = 1
  rangeForm.name = ''
  previewRef.value?.destroyPdf()
}
</script>

<style scoped>
/* 页面独有样式，通用布局全部抽至全局pdfCommon.css */
.tip-text {
  font-size: 0.8125em;
  color: #909399;
  margin-top: 0.3em;
}
</style>