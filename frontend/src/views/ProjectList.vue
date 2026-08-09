<template>
  <div>
    <div class="toolbar">
      <el-input v-model="query.keyword" placeholder="项目名/编号" clearable style="width: 200px" @keyup.enter="load" />
      <el-select v-model="query.status" placeholder="状态" clearable style="width: 130px">
        <el-option v-for="(v, k) in statusMap" :key="k" :label="v" :value="k" />
      </el-select>
      <el-select v-model="query.machine_model" placeholder="机型" clearable filterable style="width: 130px" @change="load">
        <el-option v-for="m in machineOptions" :key="m" :label="m" :value="m" />
      </el-select>
      <el-button type="primary" @click="load">查询</el-button>
      <el-button type="success" style="margin-left: auto" @click="openCreate">新建项目</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" border stripe @sort-change="onSortChange">
      <el-table-column prop="name" label="项目名称" min-width="200" sortable="custom">
        <template #default="{ row }">
          <el-link type="primary" @click="goDetail(row)">{{ row.name }}</el-link>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="项目描述" min-width="220" sortable="custom" show-overflow-tooltip>
        <template #default="{ row }">{{ row.description || '—' }}</template>
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
      style="margin-top: 12px; justify-content: flex-end"
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
const query = useViewFilterStore().projectList

// 项目状态：手动配置（未开始/进行中/延期/已完成/暂停），已完成即终态
const statusOptions = [
  { value: 'not_started', label: '未开始' },
  { value: 'in_progress', label: '进行中' },
  { value: 'delayed', label: '延期' },
  { value: 'completed', label: '已完成' },
  { value: 'suspended', label: '暂停' },
]
const statusMap = Object.fromEntries(statusOptions.map((o) => [o.value, o.label]))
// 五种状态各一种颜色（chip 背景/文字/圆点统一取色）
const statusColor = (s) => ({ not_started: '#8a94a6', in_progress: '#4f6ef7', delayed: '#e64545', completed: '#1aad70', suspended: '#e09000' }[s] || '#8a94a6')

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
.toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
.status-chip { display: inline-flex; align-items: center; gap: 2px; padding: 1px 10px; border-radius: 10px; font-size: 12px; line-height: 18px; border: 1px solid; cursor: pointer; }
.status-chip.st-not_started { background: #eef1f6; color: #5c6b84; border-color: #d8dfe9; }
.status-chip.st-in_progress { background: #edf1ff; color: #3a63f0; border-color: #c8d5ff; }
.status-chip.st-delayed { background: #fdeeee; color: #e64545; border-color: #f5bdbd; }
.status-chip.st-completed { background: #eafaf2; color: #149a66; border-color: #b5ecd4; }
.status-chip.st-suspended { background: #fff6e8; color: #d98200; border-color: #f7dbb1; }
.status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
</style>
