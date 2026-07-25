import { createRouter, createWebHistory } from 'vue-router'
// 当前拆分页面
const RemoveWatermark = () => import('../views/RemoveWatermark.vue')
const JpgToPdf = () => import('../views/JpgToPdf.vue')
const PdfToImg = () => import('../views/PdfToImg.vue')
const PdfOcr = () => import('../views/PdfOcr.vue')
const AiReadPdf = () => import('../views/AiReadPdf.vue')
const PdfDecompose = () => import('../views/PdfDecompose.vue')
const PdfMerge = () => import('../views/PdfMerge.vue')
const PdfSplit = () => import('../views/PdfSplit.vue')
const PdfSecurityScan = () => import('../views/PdfSecurityScan.vue')

const routes = [
  {
    path: '/',
    redirect: '/split'
  },
  {
    path: '/split',
    name: 'split',
    component: PdfSplit
  },
  {
    path: '/merge',
    name: 'merge',
    component: PdfMerge
  },

  {
    path: '/watermark',
    name: 'watermark',
    component: RemoveWatermark
  },

  {
    path: '/decompose',
    name: 'decompose',
    component: PdfDecompose
  },
  {
    path: '/ocr',
    name: 'ocr',
    component: PdfOcr
  },
  {
    path: '/pdf2jpg',
    name: 'pdf2jpg',
    component: PdfToImg
  },

  {
    path: '/security_scan',
    name: 'security_scan',
    component: PdfSecurityScan
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router