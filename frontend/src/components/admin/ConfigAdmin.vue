<template>
  <div>
    <div class="sec-title" style="margin-bottom:14px">系统配置</div>
    <el-table :data="rows" v-loading="loading" border>
      <el-table-column prop="key" label="配置项" width="240" />
      <el-table-column label="值" min-width="280">
        <template #default="{ row }">
          <el-input v-model="row.value" size="small" :type="isSensitive(row.key) ? 'password' : 'text'" />
        </template>
      </el-table-column>
      <el-table-column prop="description" label="说明" min-width="240">
        <template #default="{ row }"><span class="pm-sub">{{ row.description }}</span></template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="save(row)">保存</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listConfig, setConfig } from '../../api'

const loading = ref(false)
const rows = ref([])
const isSensitive = (k) => k.toLowerCase().includes('key') || k.toLowerCase().includes('secret')

async function load() { loading.value = true; try { rows.value = await listConfig() } finally { loading.value = false } }
async function save(row) { await setConfig(row.key, row.value); ElMessage.success(`已保存 ${row.key}`) }
onMounted(load)
</script>
<style scoped>
.sec-title { font-weight: 700; font-size: 15px; }
</style>
