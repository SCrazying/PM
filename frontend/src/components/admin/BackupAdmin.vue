<template>
  <div>
    <div class="pm-flex-between" style="margin-bottom:12px">
      <span class="sec-title">数据备份</span>
      <el-button type="primary" :loading="backing" @click="doBackup">立即备份</el-button>
    </div>
    <el-alert type="info" :closable="false" style="margin-bottom:12px"
              title="备份为数据库 pg_dump 文件；建议同时配置服务器定时任务（deploy/scripts/backup.sh）做每日备份。" />
    <el-table :data="rows" v-loading="loading" border>
      <el-table-column prop="file" label="备份文件" min-width="240" />
      <el-table-column label="大小" width="140">
        <template #default="{ row }">{{ formatSize(row.size) }}</template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!rows.length" description="暂无备份" :image-size="60" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listBackups, triggerBackup } from '../../api'

const loading = ref(false)
const backing = ref(false)
const rows = ref([])

const formatSize = (s) => (s > 1024 * 1024 ? (s / 1024 / 1024).toFixed(1) + ' MB' : (s / 1024).toFixed(1) + ' KB')

async function load() { loading.value = true; try { rows.value = await listBackups() } finally { loading.value = false } }
async function doBackup() {
  backing.value = true
  try { const r = await triggerBackup(); ElMessage.success(`已备份：${r.file}`); load() }
  finally { backing.value = false }
}
onMounted(load)
</script>
<style scoped>
.sec-title { font-weight: 700; font-size: 15px; }
</style>
