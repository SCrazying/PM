<template>
  <div>
    <div class="pm-toolbar">
      <span class="pm-page-title">项目看板</span>
      <div style="flex:1"></div>
      <el-select v-model="filters.machine_model" placeholder="机型" clearable filterable style="width: 150px" @change="load">
        <el-option v-for="m in machineOptions" :key="m" :label="m" :value="m" />
      </el-select>
      <el-button @click="load"><el-icon><Refresh /></el-icon></el-button>
    </div>

    <!-- 统计卡片 -->
    <div class="dash-stats" v-loading="loading">
      <div v-for="s in statCards" :key="s.label" class="stat-card" :style="{ borderTopColor: s.color }">
        <div class="stat-num" :style="{ color: s.color }">{{ s.value }}</div>
        <div class="stat-label">{{ s.label }}</div>
      </div>
    </div>

    <!-- 状态分布 -->
    <div v-if="summary" class="dash-section">
      <div class="dash-h">状态分布</div>
      <div class="dist-bar">
        <div v-for="seg in distSegs" :key="seg.key" class="dist-seg"
             :style="{ width: seg.width, background: seg.color }"
             :title="`${seg.label} ${seg.count}`"></div>
      </div>
      <div class="dist-legend">
        <span v-for="seg in distSegs" :key="'l' + seg.key" class="dist-item">
          <span class="dist-dot" :style="{ background: seg.color }"></span>{{ seg.label }} {{ seg.count }}
        </span>
      </div>
    </div>

    <!-- 待关注项目 + 未关闭风险 -->
    <el-row :gutter="14" v-if="summary" class="dash-row">
      <el-col :span="12">
        <div class="dash-section">
          <div class="dash-h">待关注项目（当前节点超期 {{ summary.overdue_count }}）</div>
          <div v-if="summary.overdue_projects.length" class="dash-list">
            <div v-for="p in summary.overdue_projects" :key="p.id" class="dash-item" @click="goDetail(p)">
              <span class="status-chip" :class="'st-' + p.status">{{ statusMap[p.status] || p.status }}</span>
              <span class="dash-name">{{ p.name }}</span>
              <span class="dash-sub">{{ p.node_key }} {{ p.node_name }}</span>
              <span class="dash-date">{{ p.planned_end }}</span>
              <el-tag size="small" type="danger" effect="plain">超期</el-tag>
            </div>
          </div>
          <div v-else class="dash-empty">暂无超期节点项目</div>
        </div>
      </el-col>
      <el-col :span="12">
        <div class="dash-section">
          <div class="dash-h">未关闭风险（近 30 天 {{ summary.risk_count }}）</div>
          <div v-if="summary.risks.length" class="dash-list">
            <div v-for="r in summary.risks" :key="r.progress_id" class="dash-item risk-item">
              <span class="dash-tag">{{ r.project_name }}</span>
              <span class="dash-risk">{{ r.risk }}</span>
              <span class="dash-sub">[{{ r.date }}] {{ r.author }}</span>
            </div>
          </div>
          <div v-else class="dash-empty">最近 30 天无未关闭风险</div>
        </div>
      </el-col>
    </el-row>

    <!-- 昨日进展 / 今日计划缺报（早会提醒） -->
    <el-row :gutter="14" v-if="summary" class="dash-row">
      <el-col :span="24">
        <div class="dash-section">
          <div class="dash-h">昨日进展 / 今日计划缺报（{{ fmtTarget(summary.report_target_date) }}）
            <span class="dash-h-sub">不参与早会点名的人员：系统管理 → 看板提醒</span>
          </div>
          <el-row :gutter="14">
            <el-col :span="12">
              <div class="dash-sub-h">未更新昨日进展（{{ summary.missing_progress.length }}）</div>
              <div v-if="summary.missing_progress.length" class="dash-list">
                <div v-for="m in summary.missing_progress" :key="'pr' + m.user_id" class="dash-item no-click">
                  <span class="pc-avatar">{{ (m.display_name || '?').slice(0, 1) }}</span>
                  <span class="dash-name">{{ m.display_name || '—' }}</span>
                  <span class="dash-sub" :title="m.projects.map(p => p.name).join('、')">{{ m.projects.map(p => p.name).join('、') }}</span>
                  <el-tag size="small" type="warning" effect="plain">缺进展</el-tag>
                </div>
              </div>
              <div v-else class="dash-empty">昨日进展均已更新</div>
            </el-col>
            <el-col :span="12">
              <div class="dash-sub-h">未更新今日计划（{{ summary.missing_plan.length }}）</div>
              <div v-if="summary.missing_plan.length" class="dash-list">
                <div v-for="m in summary.missing_plan" :key="'pl' + m.user_id" class="dash-item no-click">
                  <span class="pc-avatar">{{ (m.display_name || '?').slice(0, 1) }}</span>
                  <span class="dash-name">{{ m.display_name || '—' }}</span>
                  <span class="dash-sub" :title="m.projects.map(p => p.name).join('、')">{{ m.projects.map(p => p.name).join('、') }}</span>
                  <el-tag size="small" type="danger" effect="plain">缺计划</el-tag>
                </div>
              </div>
              <div v-else class="dash-empty">今日计划均已更新</div>
            </el-col>
          </el-row>
        </div>
      </el-col>
    </el-row>

    <!-- 状态列看板（可拖拽换状态） -->
    <div class="board" v-loading="loading">
      <div v-for="col in columns" :key="col.key" class="board-col"
           :class="{ 'drag-over': dragOverCol === col.key }"
           @dragover.prevent="onColDragOver(col.key)"
           @dragleave="onColDragLeave(col.key)"
           @drop="onColDrop(col.key)">
        <div class="col-head" :style="{ borderTopColor: col.color }">
          <span class="col-title"><span class="pm-dot" :style="{ background: col.color }"></span>{{ col.title }}</span>
          <span class="col-count">{{ col.items.length }}</span>
        </div>
        <div class="col-body">
          <transition-group name="list">
            <div v-for="p in col.items" :key="p.id" class="proj-card"
                 :class="{ draggable: canEdit(p), dragging: draggingId === p.id }"
                 :draggable="canEdit(p)"
                 @dragstart="onDragStart(p, $event)"
                 @dragend="onDragEnd"
                 @click="goDetail(p)">
              <div class="pc-top">
                <span class="pc-name">{{ p.name }}</span>
                <span v-if="p.node_overdue" class="pc-overdue"><el-icon :size="11"><WarningFilled /></el-icon>超期</span>
              </div>
              <div class="pc-meta">
                <span v-if="p.machine_model" class="pc-model">{{ p.machine_model }}</span>
                <span class="pc-code">{{ p.code }}</span>
              </div>
              <div class="pc-node" v-if="p.current_node"><el-icon><Flag /></el-icon>{{ p.current_node }}</div>
              <div class="pc-foot">
                <span v-if="p.start_date || p.end_date" class="pc-date">
                  <el-icon :size="11"><Calendar /></el-icon>{{ fmtRange(p) }}
                </span>
                <span v-else></span>
                <span class="pc-owner" :title="p.owner_name || '未设置负责人'">
                  <span class="pc-avatar">{{ (p.owner_name || '?').slice(0, 1) }}</span>
                  <span class="pc-owner-name">{{ p.owner_name || '—' }}</span>
                </span>
              </div>
            </div>
          </transition-group>
          <div v-if="!col.items.length" class="col-empty">拖项目到此处，或暂无项目</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getBoard, getBoardSummary, listMachineOptions, updateProject } from '../api'
import { useViewFilterStore } from '../store/filters'
import { useUserStore } from '../store/user'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const machineOptions = ref([])
const filters = useViewFilterStore().board
const columns = ref([
  { key: 'not_started', title: '未开始', color: '#5b6b7c', items: [] },
  { key: 'in_progress', title: '进行中', color: '#0ea5e9', items: [] },
  { key: 'delayed', title: '延期', color: '#ef4444', items: [] },
  { key: 'completed', title: '已完成', color: '#10b981', items: [] },
  { key: 'suspended', title: '暂停', color: '#f59e0b', items: [] },
])
const summary = ref(null)

const statusMap = { not_started: '未开始', in_progress: '进行中', delayed: '延期', completed: '已完成', suspended: '暂停' }

// 统计卡片：在研 / 已完成 / 延期 / 未开始 / 未关闭风险 / 我的待办任务
const statCards = computed(() => {
  const s = summary.value || {}
  return [
    { label: '在研项目', value: s.active ?? '—', color: '#0ea5e9' },
    { label: '已完成', value: s.completed ?? '—', color: '#10b981' },
    { label: '延期', value: (s.status_counts || {}).delayed ?? '—', color: '#ef4444' },
    { label: '未开始', value: (s.status_counts || {}).not_started ?? '—', color: '#5b6b7c' },
    { label: '未关闭风险', value: s.risk_count ?? '—', color: '#f59e0b' },
    { label: '我的待办任务', value: s.my_task_count ?? '—', color: '#6366f1' },
  ]
})

// 状态分布条
const distSegs = computed(() => {
  const counts = summary.value?.status_counts || {}
  const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1
  return columns.value.map((c) => ({
    key: c.key, label: c.title, color: c.color,
    count: counts[c.key] || 0,
    width: `${((counts[c.key] || 0) / total) * 100}%`,
  }))
})

// 项目周期：MM-DD ~ MM-DD
function fmtRange(p) {
  const f = (d) => (d ? String(d).slice(5) : '')
  const s = f(p.start_date), e = f(p.end_date)
  if (s && e) return `${s} ~ ${e}`
  return s || e || ''
}

// 缺报日期：YYYY-MM-DD → MM-DD
function fmtTarget(d) { return d ? String(d).slice(5) : '—' }

// 仅负责人/管理员可拖拽改状态（与后端 check_owner 一致）
const canEdit = (p) => userStore.isAdmin || p.owner_id === userStore.userInfo?.user_id

async function load() {
  loading.value = true
  try {
    const data = await getBoard({ machine_model: filters.machine_model || undefined })
    const cols = data.columns || {}
    columns.value.forEach((c) => { c.items = cols[c.key] || [] })
    summary.value = await getBoardSummary()
  } finally { loading.value = false }
}
onMounted(load)
function goDetail(p) { router.push({ name: 'project-detail', params: { id: p.id } }) }

// ---------- 拖拽换状态 ----------
const draggingId = ref(null)
const dragOverCol = ref(null)
const dragProj = ref(null) // 正在拖拽的项目对象

function onDragStart(p, e) {
  if (!canEdit(p)) { e.preventDefault(); return }
  draggingId.value = p.id
  dragProj.value = p
  e.dataTransfer.effectAllowed = 'move'
}
function onDragEnd() { draggingId.value = null; dragProj.value = null; dragOverCol.value = null }
function onColDragOver(key) { if (draggingId.value) dragOverCol.value = key }
function onColDragLeave(key) { if (dragOverCol.value === key) dragOverCol.value = null }

async function onColDrop(toKey) {
  const p = dragProj.value
  dragOverCol.value = null
  if (!p || p.status === toKey) { draggingId.value = null; dragProj.value = null; return }
  const fromKey = p.status
  // 乐观更新：先移动卡片，失败再回滚
  const fromCol = columns.value.find((c) => c.key === fromKey)
  const toCol = columns.value.find((c) => c.key === toKey)
  fromCol.items = fromCol.items.filter((x) => x.id !== p.id)
  toCol.items.unshift({ ...p, status: toKey })
  draggingId.value = null; dragProj.value = null
  try {
    await updateProject(p.id, { status: toKey })
    ElMessage.success(`「${p.name}」已移到「${statusMap[toKey]}」`)
    load() // 重新拉取，保证与后端一致
  } catch {
    ElMessage.error('状态更新失败')
    load()
  }
}
</script>

<style scoped>
.dash-stats { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 14px; }
.stat-card { background: var(--pm-card); border-radius: var(--pm-radius); border-top: 3px solid; padding: 14px 16px; box-shadow: var(--pm-shadow); transition: transform .18s ease, box-shadow .18s ease; }
.stat-card:hover { transform: translateY(-2px); box-shadow: var(--pm-shadow-lg); }
.stat-num { font-size: 26px; font-weight: 700; line-height: 1.2; }
.stat-label { color: var(--pm-text-2); font-size: 12.5px; margin-top: 4px; }

.dash-section { background: var(--pm-card); border-radius: var(--pm-radius); box-shadow: var(--pm-shadow); padding: 14px 16px; margin-bottom: 14px; }
.dash-h { font-weight: 700; font-size: 14px; margin-bottom: 10px; color: var(--pm-text); }
.dash-h-sub { font-weight: 400; font-size: 11.5px; color: var(--pm-text-3); margin-left: 8px; }
.dash-row { margin-bottom: 0; }

.dist-bar { display: flex; height: 14px; border-radius: 8px; overflow: hidden; background: var(--pm-st-notstarted-bg); }
.dist-seg { height: 100%; transition: width .3s; }
.dist-legend { display: flex; flex-wrap: wrap; gap: 6px 16px; margin-top: 8px; }
.dist-item { display: inline-flex; align-items: center; gap: 5px; font-size: 12.5px; color: var(--pm-text-2); }
.dist-dot { width: 8px; height: 8px; border-radius: 50%; }

.dash-list { display: flex; flex-direction: column; gap: 6px; max-height: 260px; overflow-y: auto; }
.dash-item { display: flex; align-items: center; gap: 8px; padding: 7px 8px; border-radius: 8px; cursor: pointer; border: 1px solid var(--pm-border); background: var(--pm-bg); transition: all .15s ease; }
.dash-item:hover { border-color: var(--pm-primary-light); background: var(--pm-primary-lighter); }
.dash-item.no-click { cursor: default; }
.dash-sub-h { font-weight: 600; font-size: 12.5px; color: var(--pm-text-2); margin-bottom: 8px; }
.dash-name { font-weight: 600; font-size: 13px; flex: 0 1 auto; max-width: 40%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dash-sub { color: var(--pm-text-2); font-size: 12px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dash-date { color: var(--pm-text-3); font-size: 12px; flex-shrink: 0; }
.dash-tag { background: var(--pm-primary-light); color: var(--pm-primary); font-size: 12px; padding: 1px 8px; border-radius: 6px; flex-shrink: 0; }
.dash-risk { font-size: 12.5px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.risk-item .dash-tag { background: var(--pm-st-delayed-bg); color: var(--pm-st-delayed-fg); }
.dash-empty { color: var(--pm-text-3); font-size: 13px; padding: 12px 0; text-align: center; }

.board { display: flex; gap: 14px; overflow-x: auto; padding-bottom: 8px; }
.board-col { flex: 1; min-width: 240px; display: flex; flex-direction: column; border-radius: var(--pm-radius); transition: background .15s ease, box-shadow .15s ease; }
.board-col.drag-over { background: var(--pm-primary-lighter); box-shadow: 0 0 0 2px var(--pm-primary-light) inset; }
.col-head { background: var(--pm-card); border-radius: var(--pm-radius) var(--pm-radius) 0 0; border-top: 3px solid; padding: 10px 14px; display: flex; justify-content: space-between; align-items: center; box-shadow: var(--pm-shadow); }
.col-title { font-weight: 700; font-size: 14px; display: flex; align-items: center; }
.col-count { background: var(--pm-st-notstarted-bg); color: var(--pm-text-2); border-radius: 10px; padding: 1px 9px; font-size: 12px; font-weight: 600; }
.col-body { background: #eaf1f6; border-radius: 0 0 var(--pm-radius) var(--pm-radius); padding: 10px; min-height: 300px; flex: 1; }
.board-col.drag-over .col-body { background: transparent; }

.proj-card { background: var(--pm-card); border-radius: var(--pm-radius); padding: 12px 14px; margin-bottom: 10px; cursor: pointer; border: 1px solid var(--pm-border); transition: all .15s ease; box-shadow: var(--pm-shadow); }
.proj-card:hover { transform: translateY(-2px); box-shadow: var(--pm-shadow-lg); border-color: var(--pm-primary-light); }
.proj-card.draggable { cursor: grab; }
.proj-card.dragging { opacity: .5; cursor: grabbing; border-style: dashed; }
.pc-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 6px; }
.pc-name { font-weight: 600; font-size: 14px; flex: 1; min-width: 0; }
.pc-overdue { display: inline-flex; align-items: center; gap: 2px; color: var(--pm-danger); background: var(--pm-st-delayed-bg); font-size: 11px; padding: 1px 7px; border-radius: 8px; font-weight: 600; flex-shrink: 0; }
.pc-meta { display: flex; gap: 8px; margin-top: 8px; align-items: center; }
.pc-model { background: var(--pm-primary-light); color: var(--pm-primary); font-size: 12px; padding: 1px 8px; border-radius: 6px; }
.pc-code { color: var(--pm-text-3); font-size: 12px; }
.pc-node { margin-top: 8px; color: var(--pm-text-2); font-size: 12px; display: flex; align-items: center; gap: 4px; }
.pc-foot { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; padding-top: 9px; border-top: 1px dashed var(--pm-border); }
.pc-date { display: inline-flex; align-items: center; gap: 4px; color: var(--pm-text-3); font-size: 11.5px; }
.pc-owner { display: inline-flex; align-items: center; gap: 6px; min-width: 0; }
.pc-avatar { width: 20px; height: 20px; border-radius: 50%; background: var(--pm-gradient); color: #fff; font-size: 11px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.pc-owner-name { color: var(--pm-text-2); font-size: 12px; max-width: 72px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-empty { text-align: center; color: var(--pm-text-3); padding: 36px 12px; font-size: 12.5px; border: 1.5px dashed var(--pm-border-strong); border-radius: var(--pm-radius); margin-top: 2px; }
.list-move { transition: transform .2s; }
@media (max-width: 1400px) { .dash-stats { grid-template-columns: repeat(3, 1fr); } }
</style>
