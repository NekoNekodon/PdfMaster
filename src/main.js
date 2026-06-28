import { createApp } from 'vue'
import App from './App.vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import request from './utils/request'
import router from './router'

const app = createApp(App)
app.use(ElementPlus)
app.use(router)
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}
app.config.globalProperties.$api = request
app.mount('#app')

async function initPdfJs() {
  const pdfjsLib = await import('pdfjs-dist')
  const opts = pdfjsLib.GlobalWorkerOptions
  opts.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js'
  opts.cMapUrl = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/cmaps/'
  opts.cMapPacked = true
  opts.useWorkerFetch = true
}
initPdfJs()