<template>
  <div>
    <div class="toolbar">
      <el-input v-model="query.keyword" placeholder="项目名/编号" clearable style="width: 200px" @keyup.enter="load" />
      <el-select v-model="query.status" placeholder="状态" clearable style="width: 130px">
        <el-option v-for="(v, k) in statusMap" :key="k" :label="v" :value="k" />
      </el-select>
      <el-input v-model="query.machine_model" placeholder="机型" clearable style="width: 130px" @keyup.enter="load" />
      <el-button type="primary" @click="load">查询</el-button>
      <el-button type="success" style="margin-left: auto" @click="openCreate">新建项目</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="code" label="编号" width="110" />
      <el-table-column prop="name" label="项目名称" min-width="180">
        <template #default="{ row }">
          <el-link type="primary" @click="goDetail(row)">{{ row.name }}</el-link>
        </template>
      </el-table-column>
      <el-table-column prop="machine_model" label="机型" width="100" />
      <el-table-column label="当前节点" width="140">
        <template #default="{ row }">{{ nodeCache[row.id] || '—' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)">{{ statusMap[row.status] || row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="健康度" width="90">
        <template #default="{ row }">
          <el-tag :type="healthTag(row.health)" effect="plain">{{ healthMap[row.health] || row.health }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="goDetail(row)">详情</el-button>
          <el-button link type="warning" @click="onArchive(row)">{{ row.status === 'archived' ? '恢复' : '归档' }}</el-button>
          <el-button link type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      style="margin-top: 12px; justify-content: flex-end"
      background layout="total, prev, pager, next" :total="total"
      :page-size="query.size" :current-page="query.page" @current-change="(p) => { query.page = p; load() }" />

    <ProjectForm ref="formRef" @saved="load" />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { archiveProject, deleteProject, getProject, listProjects, unarchiveProject } from '../api'
import ProjectForm from '../components/ProjectForm.vue'

const router = useRouter()
const formRef = ref()
const loading = ref(false)
const rows = ref([])
const total = ref(0)
const nodeCache = ref({})
const query = reactive({ keyword: '', status: '', machine_model: '', page: 1, size: 10 })

const statusMap = { not_started: '未开始', in_progress: '进行中', suspended: '暂停', completed: '已完成', archived: '已归档' }
const healthMap = { on_track: '正常', at_risk: '风险', delayed: '延期' }
const statusTag = (s) => ({ in_progress: 'primary', completed: 'success', archived: 'info', suspended: 'warning' }[s] || 'info')
const healthTag = (h) => ({ on_track: 'success', at_risk: 'warning', delayed: 'danger' }[h] || 'info')

async function load() {
  loading.value = true
  try {
    const data = await listProjects(query)
    rows.value = data.list
    total.value = data.total
    for (const p of data.list) fetchCurrentNode(p)
  } finally {
    loading.value = false
  }
}

async function fetchCurrentNode(p) {
  try {
    const d = await getProject(p.id)
    const cur = (d.nodes || []).find((n) => n.id === d.current_node_id)
    nodeCache.value[p.id] = cur ? `${cur.node_key} ${cur.name}` : '—'
  } catch { /* 忽略 */ }
}

function openCreate() { formRef.value.open() }
function goDetail(row) { router.push({ name: 'project-detail', params: { id: row.id } }) }

async function onArchive(row) {
  if (row.status === 'archived') { await unarchiveProject(row.id); ElMessage.success('已恢复') }
  else { await archiveProject(row.id); ElMessage.success('已归档') }
  load()
}

async function onDelete(row) {
  await ElMessageBox.confirm(`确认删除项目「${row.name}」？（软删除，可恢复）`, '提示', { type: 'warning' })
  await deleteProject(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
</style>
