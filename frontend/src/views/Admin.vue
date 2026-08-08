<template>
  <div>
    <div class="pm-toolbar"><span class="pm-page-title">系统管理</span></div>
    <el-tabs v-model="tab" class="pm-card">
      <!-- 用户管理 -->
      <el-tab-pane label="用户管理" name="users"><UserAdmin /></el-tab-pane>
      <!-- TR 模板 -->
      <el-tab-pane label="TR 模板" name="templates"><TemplateAdmin /></el-tab-pane>
      <!-- Excel 导入 -->
      <el-tab-pane label="Excel 导入" name="import"><ImportAdmin /></el-tab-pane>
      <!-- 系统配置 -->
      <el-tab-pane label="系统配置" name="config"><ConfigAdmin /></el-tab-pane>
      <!-- 备份 -->
      <el-tab-pane label="数据备份" name="backup"><BackupAdmin /></el-tab-pane>
      <!-- 回收站 -->
      <el-tab-pane label="回收站" name="recycle"><RecycleBinAdmin /></el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import UserAdmin from '../components/admin/UserAdmin.vue'
import TemplateAdmin from '../components/admin/TemplateAdmin.vue'
import ConfigAdmin from '../components/admin/ConfigAdmin.vue'
import BackupAdmin from '../components/admin/BackupAdmin.vue'
import ImportAdmin from '../components/admin/ImportAdmin.vue'
import RecycleBinAdmin from '../components/admin/RecycleBinAdmin.vue'

const tab = ref('users')
</script>
