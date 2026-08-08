<template>
  <div>
    <div class="pm-toolbar">
      <span class="pm-page-title">项目看板</span>
      <div style="flex:1"></div>
      <el-select v-model="filters.machine_model" placeholder="机型" clearable filterable style="width: 140px" @change="load">
        <el-option v-for="m in machineOptions" :key="m" :label="m" :value="m" />
      </el-select>
      <el-select v-model="filters.granularity" style="width: 110px" @change="load">
        <el-option label="按月" value="month" />
        <el-option label="按年" value="year" />
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

    <!-- 状态列看板 -->
    <div class="board" v-loading="loading">
      <div v-for="col in columns" :key="col.key" class="board-col">
        <div class="col-head" :style="{ borderTopColor: col.color }">
          <span class="col-title"><span class="pm-dot" :style="{ background: col.color }"></span>{{ col.title }}</span>
          <span class="col-count">{{ col.items.length }}</span>
        </div>
        <div class="col-body">
          <transition-group name="list">
            <div v-for="p in col.items" :key="p.id" class="proj-card" @click="goDetail(p)">
              <div class="pc-top">
                <span class="pc-name">{{ p.name }}</span>
              </div>
              <div class="pc-meta">
                <span v-if="p.machine_model" class="pc-model">{{ p.machine_model }}</span>
                <span class="pc-code">{{ p.code }}</span>
              </div>
              <div class="pc-node" v-if="p.current_node"><el-icon><Flag /></el-icon>{{ p.current_node }}</div>
            </div>
          </transition-group>
          <div v-if="!col.items.length" class="col-empty">暂无项目</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getBoard, getBoardSummary, listMachineOptions } from '../api'
import { useViewFilterStore } from '../store/filters'

const router = useRouter()
const loading = ref(false)
const machineOptions = ref([])
const filters = useViewFilterStore().board
const columns = ref([
  { key: 'not_started', title: '未开始', color: '#8a94a6', items: [] },
  { key: 'in_progress', title: '进行中', color: '#4f6ef7', items: [] },
  { key: 'delayed', title: '延期', color: '#e64545', items: [] },
  { key: 'completed', title: '已完成', color: '#1aad70', items: [] },
  { key: 'suspended', title: '暂停', color: '#e09000', items: [] },
])
const summary = ref(null)

const statusMap = { not_started: '未开始', in_progress: '进行中', delayed: '延期', completed: '已完成', suspended: '暂停' }
const statusColor = { not_started: '#8a94a6', in_progress: '#4f6ef7', delayed: '#e64545', completed: '#1aad70', suspended: '#e09000' }

// 统计卡片：在研 / 已完成 / 延期 / 未开始 / 未关闭风险 / 我的待办任务
const statCards = computed(() => {
  const s = summary.value || {}
  return [
    { label: '在研项目', value: s.active ?? '—', color: '#4f6ef7' },
    { label: '已完成', value: s.completed ?? '—', color: '#1aad70' },
    { label: '延期', value: (s.status_counts || {}).delayed ?? '—', color: '#e64545' },
    { label: '未开始', value: (s.status_counts || {}).not_started ?? '—', color: '#8a94a6' },
    { label: '未关闭风险', value: s.risk_count ?? '—', color: '#f5a623' },
    { label: '我的待办任务', value: s.my_task_count ?? '—', color: '#7a5ce0' },
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

async function load() {
  loading.value = true
  try {
    const data = await getBoard({ granularity: filters.granularity, machine_model: filters.machine_model || undefined })
    const cols = data.columns || {}
    columns.value.forEach((c) => { c.items = cols[c.key] || [] })
    summary.value = await getBoardSummary()
  } finally { loading.value = false }
}
function goDetail(p) { router.push({ name: 'project-detail', params: { id: p.id } }) }
onMounted(async () => {
  machineOptions.value = await listMachineOptions()
  load()
})
</script>

<style scoped>
.dash-stats { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 14px; }
.stat-card { background: var(--pm-card); border-radius: var(--pm-radius); border-top: 3px solid; padding: 14px 16px; box-shadow: var(--pm-shadow); }
.stat-num { font-size: 26px; font-weight: 700; line-height: 1.2; }
.stat-label { color: var(--pm-text-2); font-size: 12.5px; margin-top: 4px; }

.dash-section { background: var(--pm-card); border-radius: var(--pm-radius); box-shadow: var(--pm-shadow); padding: 14px 16px; margin-bottom: 14px; }
.dash-h { font-weight: 700; font-size: 14px; margin-bottom: 10px; color: var(--pm-text-1); }
.dash-row { margin-bottom: 0; }

.dist-bar { display: flex; height: 14px; border-radius: 8px; overflow: hidden; background: #eef1f6; }
.dist-seg { height: 100%; transition: width .3s; }
.dist-legend { display: flex; flex-wrap: wrap; gap: 6px 16px; margin-top: 8px; }
.dist-item { display: inline-flex; align-items: center; gap: 5px; font-size: 12.5px; color: var(--pm-text-2); }
.dist-dot { width: 8px; height: 8px; border-radius: 50%; }

.dash-list { display: flex; flex-direction: column; gap: 6px; max-height: 260px; overflow-y: auto; }
.dash-item { display: flex; align-items: center; gap: 8px; padding: 7px 8px; border-radius: 8px; cursor: pointer; border: 1px solid var(--pm-border); background: var(--pm-bg); }
.dash-item:hover { border-color: var(--pm-primary-light); background: var(--pm-primary-light); }
.dash-name { font-weight: 600; font-size: 13px; flex: 0 1 auto; max-width: 40%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dash-sub { color: var(--pm-text-2); font-size: 12px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dash-date { color: var(--pm-text-3); font-size: 12px; flex-shrink: 0; }
.dash-tag { background: var(--pm-primary-light); color: var(--pm-primary); font-size: 12px; padding: 1px 8px; border-radius: 6px; flex-shrink: 0; }
.dash-risk { font-size: 12.5px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.risk-item .dash-tag { background: #fdeeee; color: #e64545; }
.dash-empty { color: var(--pm-text-3); font-size: 13px; padding: 12px 0; text-align: center; }

.status-chip { display: inline-flex; align-items: center; padding: 1px 10px; border-radius: 10px; font-size: 12px; line-height: 18px; border: 1px solid; flex-shrink: 0; }
.status-chip.st-not_started { background: #eef1f6; color: #5c6b84; border-color: #d8dfe9; }
.status-chip.st-in_progress { background: #edf1ff; color: #3a63f0; border-color: #c8d5ff; }
.status-chip.st-delayed { background: #fdeeee; color: #e64545; border-color: #f5bdbd; }
.status-chip.st-completed { background: #eafaf2; color: #149a66; border-color: #b5ecd4; }
.status-chip.st-suspended { background: #fff6e8; color: #d98200; border-color: #f7dbb1; }

.board { display: flex; gap: 14px; overflow-x: auto; padding-bottom: 8px; }
.board-col { flex: 1; min-width: 230px; display: flex; flex-direction: column; }
.col-head { background: var(--pm-card); border-radius: var(--pm-radius) var(--pm-radius) 0 0; border-top: 3px solid; padding: 10px 14px; display: flex; justify-content: space-between; align-items: center; box-shadow: var(--pm-shadow); }
.col-title { font-weight: 700; font-size: 14px; display: flex; align-items: center; }
.col-count { background: #eef1f6; color: var(--pm-text-2); border-radius: 10px; padding: 1px 9px; font-size: 12px; font-weight: 600; }
.col-body { background: #eceff4; border-radius: 0 0 var(--pm-radius) var(--pm-radius); padding: 10px; min-height: 300px; flex: 1; }
.proj-card { background: var(--pm-card); border-radius: var(--pm-radius); padding: 12px 14px; margin-bottom: 10px; cursor: pointer; border: 1px solid transparent; transition: all .15s ease; box-shadow: var(--pm-shadow); }
.proj-card:hover { transform: translateY(-2px); box-shadow: var(--pm-shadow-lg); border-color: var(--pm-primary-light); }
.pc-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 6px; }
.pc-name { font-weight: 600; font-size: 14px; }
.pc-meta { display: flex; gap: 8px; margin-top: 8px; align-items: center; }
.pc-model { background: var(--pm-primary-light); color: var(--pm-primary); font-size: 12px; padding: 1px 8px; border-radius: 6px; }
.pc-code { color: var(--pm-text-3); font-size: 12px; }
.pc-node { margin-top: 8px; color: var(--pm-text-2); font-size: 12px; display: flex; align-items: center; gap: 4px; }
.col-empty { text-align: center; color: var(--pm-text-3); padding: 40px 0; font-size: 13px; }
.list-move { transition: transform .2s; }
@media (max-width: 1400px) { .dash-stats { grid-template-columns: repeat(3, 1fr); } }
</style>
