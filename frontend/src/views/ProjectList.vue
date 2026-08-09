<template>
  <div class="pm-card page-card">
    <div class="pm-flex-between toolbar">
      <div class="pm-flex pm-gap">
        <el-input v-model="query.keyword" placeholder="项目名/编号" clearable style="width: 200px" @keyup.enter="load" />
        <el-select v-model="query.status" placeholder="状态" clearable style="width: 130px">
          <el-option v-for="(v, k) in statusMap" :key="k" :label="v" :value="k" />
        </el-select>
        <el-select v-model="query.machine_model" placeholder="机型" clearable filterable style="width: 130px" @change="load">
          <el-option v-for="m in machineOptions" :key="m" :label="m" :value="m" />
        </el-select>
        <el-button type="primary" @click="load">查询</el-button>
        <el-button @click="onReset">重置</el-button>
      </div>
      <el-button type="success" @click="openCreate"><el-icon style="margin-right:4px"><Plus /></el-icon>新建项目</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" stripe @sort-change="onSortChange">
      <el-table-column prop="name" label="项目名称" min-width="200" sortable="custom">
        <template #default="{ row }">
          <el-link type="primary" @click="goDetail(row)">{{ row.name }}</el-link>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="项目描述" min-width="240" sortable="custom">
        <template #default="{ row }">
          <div class="desc-cell">{{ row.description || '—' }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="machine_model" label="机型" width="96" sortable="custom" />
      <el-table-column label="当前节点" width="150">
        <template #default="{ row }">{{ nodeCache[row.id] || '—' }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="132" sortable="custom">
        <template #default="{ row }">
          <el-dropdown v-if="canEditStatus(row)" trigger="click" @command="(v) => onStatusChange(row, v)">
            <span class="status-chip" :class="'st-' + row.status">
              {{ statusMap[row.status] || row.status }}
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-for="o in statusOptions" :key="o.value" :command="o.value">
                  <span class="status-dot" :style="{ background: statusColor(o.value) }"></span>{{ o.label }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <span v-else class="status-chip" :class="'st-' + row.status">{{ statusMap[row.status] || row.status }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="goDetail(row)">详情</el-button>
          <el-button v-if="canEditStatus(row)" link type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="page-pager"
      background layout="total, prev, pager, next" :total="total"
      :page-size="query.size" :current-page="query.page" @current-change="(p) => { query.page = p; load() }" />

    <ProjectForm ref="formRef" @saved="load" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteProject, getProject, listMachineOptions, listProjects, updateProject } from '../api'
import ProjectForm from '../components/ProjectForm.vue'
import { useViewFilterStore } from '../store/filters'
import { useUserStore } from '../store/user'

const router = useRouter()
const userStore = useUserStore()
const formRef = ref()
const loading = ref(false)
const rows = ref([])
const total = ref(0)
const nodeCache = ref({})
const machineOptions = ref([])
const viewFilters = useViewFilterStore()
const query = viewFilters.projectList

// 重置筛选回默认值（关键词/状态/机型/排序/页码）
function onReset() {
  viewFilters.reset('projectList')
  load()
}

// 项目状态：手动配置（未开始/进行中/延期/已完成/暂停），已完成即终态
const statusOptions = [
  { value: 'not_started', label: '未开始' },
  { value: 'in_progress', label: '进行中' },
  { value: 'delayed', label: '延期' },
  { value: 'completed', label: '已完成' },
  { value: 'suspended', label: '暂停' },
]
const statusMap = Object.fromEntries(statusOptions.map((o) => [o.value, o.label]))
// 五种状态各一种颜色（下拉圆点取色；chip 样式走全局 .status-chip）
const statusColor = (s) => ({ not_started: '#5b6b7c', in_progress: '#0284c7', delayed: '#dc3c3c', completed: '#0d9d6c', suspended: '#cf8207' }[s] || '#5b7180')

// 状态内联编辑：仅负责人/管理员可改，其余只读展示
const canEditStatus = (row) => userStore.isAdmin || row.owner_id === userStore.userInfo?.user_id

async function onStatusChange(row, status) {
  const prev = row.status
  row.status = status
  try {
    const data = await updateProject(row.id, { status })
    row.status = data.status
    ElMessage.success(`状态已改为「${statusMap[status] || status}」`)
  } catch {
    row.status = prev
    ElMessage.error('状态更新失败')
  }
}

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

// 服务端排序：表头点击 → 传 sort_field/sort_order 重新查询
function onSortChange({ prop, order }) {
  query.sort_field = order ? (prop || 'id') : 'id'
  query.sort_order = order === 'ascending' ? 'asc' : 'desc'
  query.page = 1
  load()
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

// 删除：两次确认弹窗（第二次需输入项目名称）；仅管理员/负责人可见该按钮（后端同样校验）
async function onDelete(row) {
  await ElMessageBox.confirm(`确认删除项目「${row.name}」？删除后进入回收站，可恢复。`, '删除确认', { type: 'warning', confirmButtonText: '删除' })
  await ElMessageBox.prompt(`删除不可撤销（需到回收站恢复），请输入项目名称「${row.name}」以二次确认。`, '二次确认', {
    inputPlaceholder: `输入「${row.name}」`,
    confirmButtonText: '确认删除',
    inputValidator: (v) => (v === row.name ? true : '输入的项目名称不一致'),
  })
  await deleteProject(row.id)
  ElMessage.success('已删除（可在回收站恢复）')
  load()
}

onMounted(async () => {
  machineOptions.value = await listMachineOptions()
  load()
})
</script>

<style scoped>
.page-card { padding: 18px 20px; }
.toolbar { margin-bottom: 16px; }
.page-pager { margin-top: 16px; justify-content: flex-end; }
.status-chip { cursor: pointer; }
.status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
.desc-cell { white-space: pre-wrap; word-break: break-word; line-height: 1.5; color: var(--pm-text-2); font-size: 12.5px; }
</style>
