<template>
  <div class="pdf-editor-container" role="main" aria-label="PDF工具箱-拆分提取页面">
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
          v-for="item in cutRangeList"
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
            @click="removeCutItem(item.uid)"
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
import { ref, reactive, getCurrentInstance } from 'vue'
import { ElMessage, ElLoading } from 'element-plus'
import PdfUploadDrag from '../components/PdfUploadDrag/index.vue'
import PdfPreview from '../components/PdfPreview/index.vue'

const { proxy } = getCurrentInstance()
const $api = proxy.$api

// 子组件实例
const previewRef = ref(null)

// 全局业务状态
const pdfFile = ref(null)
const totalPage = ref(0)
const uploadLoading = ref(false)

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

// 添加截取片段，生成唯一uid
const addCutRange = () => {
  if (!pdfFile.value) {
    ElMessage.warning('请先上传并正常解析PDF文件')
    return
  }
  const { start, end, name } = cutForm
  if (!name.trim()) {
    ElMessage.warning('请填写片段名称')
    return
  }
  if (start > end) {
    ElMessage.warning('起始页码不能大于结束页码')
    return
  }
  cutRangeList.value.push({
    uid: Date.now() + '_' + Math.random().toString(36).slice(2),
    start,
    end,
    name: name.trim()
  })
  ElMessage.success('截取片段添加成功')
}

// 删除单条片段
const removeCutItem = (uid) => {
  const idx = cutRangeList.value.findIndex(i => i.uid === uid)
  if (idx > -1) cutRangeList.value.splice(idx, 1)
}

// 单个片段请求后端导出
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

    const blob = await $api.post("/split_extract/", formData, {
      responseType: "blob"
    })

    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `${name}.pdf`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success(`【${name}】PDF导出完成`)
  } catch (err) {
    if (err?.response?.data) {
      try {
        // blob 二进制转字符串
        const buf = await err.response.data.arrayBuffer()
        const txt = new TextDecoder().decode(new Uint8Array(buf))
        const res = JSON.parse(txt)
        ElMessage.error(res.msg || '处理失败')
      } catch {
        ElMessage.error('服务端返回数据解析失败')
      }
    } else {
      ElMessage.error('网络请求失败，请检查连接')
    }
  } finally {
    loading.close()
  }
}

// 批量导出全部片段
const exportAllCut = async () => {
  if (cutRangeList.value.length === 0) {
    ElMessage.warning('暂无截取片段')
    return
  }
  for (const item of cutRangeList.value) {
    await exportByBackend(item.start, item.end, item.name)
  }
}

// 重置全部数据，调用子组件销毁pdf资源
const resetAll = () => {
  pdfFile.value = null
  totalPage.value = 0
  cutRangeList.value = []
  cutForm.start = 1
  cutForm.end = 1
  cutForm.name = ''
  previewRef.value?.destroyPdf()
}

</script>

<style scoped>
</style>