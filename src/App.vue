<template>
  <div class="app-wrap">
    <!-- 顶部导航栏 -->
    <header class="nav-header">
      <div class="nav-container">
        <div class="logo">PDF工具箱</div>
        <nav class="nav-menu">
          <router-link to="/split" class="nav-item" :class="{ active: $route.path === '/split' }">PDF切片</router-link>
          <router-link to="/decompose" class="nav-item" :class="{ active: $route.path === '/decompose' }">PDF分解</router-link>
          <router-link to="/watermark" class="nav-item" :class="{ active: $route.path === '/watermark' }">PDF去水印</router-link>
          <router-link to="/merge" class="nav-item" :class="{ active: $route.path === '/merge' }">PDF合并</router-link>
          <router-link to="/pdf2jpg" class="nav-item" :class="{ active: $route.path === '/pdf2jpg' }">PDF转JPG</router-link>
          <router-link to="/ocr" class="nav-item" :class="{ active: $route.path === '/ocr' }">PDF OCR识别</router-link>
        </nav>
      </div>
    </header>
    <!-- 页面路由容器 -->
    <main class="page-container">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { useRoute } from 'vue-router'
const route = useRoute()
// 模板已直接使用 $route，导入仅为规范，无额外业务逻辑
</script>

<style>
html, body {
  margin: 0;
  padding: 0;
  overflow: hidden; /* 禁止浏览器全局滚动条 */
  font-size: 100%;
}
</style>

<style scoped>
.app-wrap {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.nav-header {
  background: #2478ff;
  color: #fff;
  box-shadow: 0 2px 8px rgba(0,0,0,0.12);
}
.nav-container {
  width: 95%;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 40px;
  padding: 0 12px;
}
.logo {
  font-size: 20px;
  font-weight: 600;
  padding: 16px 0;
  white-space: nowrap;
}
.nav-menu {
  display: flex;
  gap: 4px;
}
.nav-item {
  display: block;
  padding: 16px 14px;
  color: rgba(255,255,255,0.7);
  text-decoration: none;
  border-radius: 6px;
  transition: all 0.2s ease;
}
/* 悬浮样式 */
.nav-item:hover {
  color: rgba(255,255,255,0.95);
  background: rgba(255,255,255,0.1);
}
/* 当前页面激活高光（强化区分） */
.nav-item.active {
  color: #ffffff;
  background: rgba(255,255,255,0.22);
  font-weight: 500;
}
.page-container {
  flex: 1;
}
</style>