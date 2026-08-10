<template>
  <div>
    <div class="pm-flex-between" style="margin-bottom:12px">
      <span class="sec-title">操作日志</span>
    </div>
    <div class="filter-bar" style="margin-bottom:12px">
      <el-input v-model="query.actor" placeholder="操作者姓名/用户名" clearable style="width:160px" @keyup.enter="load(1)" />
      <el-select v-model="query.action" placeholder="动作" clearable style="width:130px">
        <el-option v-for="a in meta.actions" :key="a" :label="actionText(a)" :value="a" />
      </el-select>
      <el-select v-model="query.target_type" placeholder="对象类型" clearable style="width:140px">
        <el-option v-for="t in meta.target_types" :key="t" :label="targetText(t)" :value="t" />
      </el-select>
      <el-input v-model="query.target_id" placeholder="对象ID(如项目号)" clearable style="width:150px" @keyup.enter="load(1)" />
      <el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始" end-placeholder="结束" style="width:240px" />
      <el-button type="primary" @click="load(1)">查询</el-button>
      <el-button @click="onReset">重置</el-button>
      <el-button type="success" plain :loading="exporting" @click="exportCsv">导出</el-button>
      <el-button type="danger" plain :loading="cleaning" @click="cleanup">清理过期</el-button>
    </div>
    <el-table :data="rows" v-loading="loading" border stripe size="small">
      <el-table-column label="时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.time) }}</template>
      </el-table-column>
      <el-table-column label="操作者" width="110">
        <template #default="{ row }">{{ row.actor_name || '—' }}</template>
      </el-table-column>
      <el-table-column label="动作" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="actionTag(row.action)">{{ actionText(row.action) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="对象" width="130">
        <template #default="{ row }">{{ targetText(row.target_type) }}{{ row.target_id ? ` #${row.target_id}` : '' }}</template>
      </el-table-column>
      <el-table-column label="详情" min-width="280">
        <template #default="{ row }">
          <el-tooltip v-if="row.detail && Object.keys(row.detail).length" :content="JSON.stringify(row.detail, null, 2)" placement="top" :show-after="300">
            <div class="detail-cell">{{ detailText(row.detail) }}</div>
          </el-tooltip>
          <span v-else class="pm-sub">—</span>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination class="page-pager" background layout="total, prev, pager, next" :total="total"
                   :page-size="query.size" :current-page="query.page" @current-change="(p) => load(p)" />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { cleanupAuditLogs, exportAuditLogs, getAuditMeta, listAuditLogs } from '../../api'

const loading = ref(false)
const exporting = ref(false)
const cleaning = ref(false)
const rows = ref([])
const total = ref(0)
const meta = reactive({ actions: [], target_types: [] })
const query = reactive({ actor: '', action: '', target_type: '', target_id: '', page: 1, size: 20 })
const dateRange = ref(null)

const actionMap = {
  create: '新增', update: '修改', delete: '删除', review: '评审', export: '导出', import: '导入',
  backup: '备份', restore: '恢复', purge: '彻底删除', config_change: '配置变更',
  login: '登录', logout: '登出', login_failed: '登录失败', account_locked: '账号锁定',
  reset_password: '重置密码', force_transition: '强制流转',
}
const targetMap = {
  project: '项目', project_risk: '项目风险', task: '任务', node: '节点', user: '用户', machine_model: '机型',
  tr_template: '模板', member: '成员', progress: '进展', weekly_goal: '周目标', attachment: '附件',
  config: '配置', project_ledger: '台账', system: '系统', ai_summary: 'AI总结', subnode: '子节点',
  role: '角色', notification: '通知',
}
const actionText = (a) => actionMap[a] || a
const targetText = (t) => targetMap[t] || t
const actionTag = (a) => ({ create: 'success', update: 'primary', delete: 'danger', review: 'warning' }[a] || 'info')

function fmtTime(t) {
  if (!t) return '—'
  const d = new Date(t)
  if (isNaN(d.getTime())) return t.replace('T', ' ').slice(0, 19)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
function detailText(d) {
  // detail 可能是 {field: {before, after}} 或 {key: value}，转成可读文本
  const parts = Object.entries(d).map(([k, v]) => {
    if (v && typeof v === 'object' && 'before' in v && 'after' in v) {
      return `${k}: ${v.before ?? '∅'} → ${v.after ?? '∅'}`
    }
    const val = typeof v === 'object' ? JSON.stringify(v) : String(v ?? '')
    return `${k}: ${val}`
  })
  return parts.join('；')
}

async function load(page) {
  query.page = page || 1
  loading.value = true
  try {
    const params = { ...query, date_from: dateRange.value?.[0], date_to: dateRange.value?.[1] }
    const data = await listAuditLogs(params)
    rows.value = data.list
    total.value = data.total
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function onReset() {
  Object.assign(query, { actor: '', action: '', target_type: '', target_id: '', page: 1, size: 20 })
  dateRange.value = null
  load(1)
}

async function cleanup() {
  cleaning.value = true
  try {
    const r = await cleanupAuditLogs()
    ElMessage.success(r?.message || '已清理')
    load(1)
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '清理失败')
  } finally {
    cleaning.value = false
  }
}

async function exportCsv() {
  exporting.value = true
  try {
    const params = { ...query, date_from: dateRange.value?.[0], date_to: dateRange.value?.[1] }
    const blob = await exportAuditLogs(params)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '操作日志.csv'
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

onMounted(async () => {
  try {
    const m = await getAuditMeta()
    meta.actions = m.actions || []
    meta.target_types = m.target_types || []
  } catch { /* 忽略 */ }
  load(1)
})
</script>

<style scoped>
.sec-title { font-weight: 700; font-size: 15px; }
.filter-bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.detail-cell { color: var(--pm-text-2); font-size: 12px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
.page-pager { margin-top: 14px; justify-content: flex-end; }
</style>
