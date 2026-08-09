<template>
  <div>
    <div class="pm-flex-between" style="margin-bottom:12px">
      <span class="sec-title">回收站（假删除项目，可恢复或彻底删除）</span>
      <div>
        <el-button :disabled="!selection.length" @click="onRestore(selection)">恢复选中（{{ selection.length }}）</el-button>
        <el-button type="danger" :disabled="!selection.length" @click="onPurge(selection)">彻底删除选中（{{ selection.length }}）</el-button>
      </div>
    </div>

    <el-table :data="rows" v-loading="loading" border stripe @selection-change="(v) => selection = v">
      <el-table-column type="selection" width="46" />
      <el-table-column prop="code" label="编号" width="110" />
      <el-table-column prop="name" label="项目名称" min-width="180" />
      <el-table-column prop="machine_model" label="机型" width="100">
        <template #default="{ row }">{{ row.machine_model || '—' }}</template>
      </el-table-column>
      <el-table-column prop="owner_name" label="负责人" width="110">
        <template #default="{ row }">{{ row.owner_name || row.owner_id }}</template>
      </el-table-column>
      <el-table-column label="状态" width="104">
        <template #default="{ row }">
          <span class="status-chip" :class="'st-' + row.status">{{ statusMap[row.status] || row.status }}</span>
        </template>
      </el-table-column>
      <el-table-column label="删除时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.deleted_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="onRestore([row])">恢复</el-button>
          <el-button link type="danger" @click="onPurge([row])">彻底删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      style="margin-top:12px; justify-content:flex-end"
      background layout="total, prev, pager, next" :total="total"
      :page-size="query.size" :current-page="query.page" @current-change="(p) => { query.page = p; load() }" />

    <el-empty v-if="!rows.length && !loading" description="回收站暂无项目" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listRecycleBin, purgeRecycleProjects, restoreRecycleProjects } from '../../api'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const selection = ref([])
const query = ref({ page: 1, size: 10 })

const statusMap = { not_started: '未开始', in_progress: '进行中', delayed: '延期', suspended: '暂停', completed: '已完成' }
const fmtTime = (t) => (t ? String(t).replace('T', ' ').slice(0, 19) : '—')

async function load() {
  loading.value = true
  try {
    const data = await listRecycleBin(query.value)
    rows.value = data.list
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function onRestore(items) {
  const ids = items.map((p) => p.id)
  await ElMessageBox.confirm(
    `确定恢复选中的 ${ids.length} 个项目？恢复后连同其节点、任务、成员一并还原。`,
    '恢复确认',
    { type: 'warning', confirmButtonText: '恢复' },
  )
  const resp = await restoreRecycleProjects(ids)
  ElMessage.success(resp?.message || '已恢复')
  load()
}

async function onPurge(items) {
  const ids = items.map((p) => p.id)
  const names = items.slice(0, 5).map((p) => `「${p.name}」`).join('、') + (items.length > 5 ? ' 等' : '')
  await ElMessageBox.confirm(
    `确定彻底删除 ${names}？删除后不可恢复，其全部节点、任务、进展、附件等数据将一并清除！`,
    '彻底删除确认',
    { type: 'warning', confirmButtonText: '彻底删除', confirmButtonClass: 'el-button--danger' },
  )
  const resp = await purgeRecycleProjects(ids)
  ElMessage.success(resp?.message || '已彻底删除')
  load()
}

onMounted(load)
</script>

<style scoped>
.sec-title { font-weight: 700; font-size: 15px; }
</style>
