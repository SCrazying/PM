<template>
  <div>
    <div class="pm-card toolbar-card">
      <div class="pm-toolbar weekly-toolbar" style="margin-bottom:0">
        <div class="tb-left">
          <span class="pm-page-title">周会视图</span>
          <el-date-picker v-model="weekStart" type="week" format="YYYY 第 ww 周" value-format="YYYY-MM-DD"
                          style="width: 180px" @change="load" />
          <el-select v-model="filterMachine" clearable filterable placeholder="按机型筛选" style="width: 150px">
            <el-option v-for="m in machineOptions" :key="m" :label="m" :value="m" />
          </el-select>
          <template v-if="view === 'project'">
            <el-select v-model="filterStatus" clearable placeholder="状态筛选" style="width: 130px">
              <el-option v-for="o in statusOptions" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <el-select v-model="filterRole" clearable placeholder="角色（默认 FO/TL）" style="width: 150px">
              <el-option v-for="r in roleFilterOptions" :key="r.value" :label="r.label" :value="r.value" />
            </el-select>
            <el-select v-model="filterPerson" clearable filterable placeholder="按人筛选" style="width: 130px">
              <el-option v-for="u in memberUsers" :key="u.id" :label="u.display_name" :value="u.id" />
            </el-select>
          </template>
          <template v-if="view === 'person'">
            <el-select v-model="filterPerson" clearable filterable placeholder="按人筛选" style="width: 130px">
              <el-option v-for="u in personUsers" :key="u.user_id" :label="u.display_name" :value="u.user_id" />
            </el-select>
            <el-select v-model="filterRole" clearable placeholder="角色（默认 FO/TL）" style="width: 150px">
              <el-option v-for="r in roleFilterOptions" :key="r.value" :label="r.label" :value="r.value" />
            </el-select>
          </template>
        </div>
        <div class="tb-right">
          <el-button @click="onReset">重置</el-button>
          <el-popover v-if="view === 'project'" placement="bottom-end" :width="200" trigger="click">
            <template #reference>
              <el-button><el-icon style="margin-right:4px"><Setting /></el-icon>设置</el-button>
            </template>
            <div class="col-settings">
              <div class="cs-h">显示选项</div>
              <el-checkbox v-model="dailyTodayOnly">仅显示今日每日进展</el-checkbox>
              <el-divider style="margin:6px 0" />
              <div class="cs-h">列显示</div>
              <el-checkbox v-for="c in colOptions" :key="c.key"
                           :model-value="visibleCols.includes(c.key)"
                           @change="(v) => toggleCol(c.key, v)">{{ c.label }}</el-checkbox>
              <el-divider style="margin:6px 0" />
              <el-button size="small" type="primary" plain style="width:100%" @click="onResetCols">恢复默认</el-button>
            </div>
          </el-popover>
          <el-dropdown @command="downloadLedger">
            <el-button type="success" :loading="exporting">
              <el-icon style="margin-right:5px"><Download /></el-icon>导出台账<el-icon><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="weekly">导出本周台账</el-dropdown-item>
                <el-dropdown-item command="project">导出项目台账（每周任务合集）</el-dropdown-item>
                <el-dropdown-item command="completion">导出项目完成台账</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-radio-group v-model="view" @change="load">
            <el-radio-button value="project">按项目</el-radio-button>
            <el-radio-button value="person">按人</el-radio-button>
          </el-radio-group>
        </div>
      </div>
    </div>

    <!-- Excel 风格项目台账：默认不展开，展开行查看周报详情。 -->
    <div v-if="view === 'project'" v-loading="loading" class="pm-card table-card">
      <el-table
        :data="filteredReports"
        row-key="project.id"
        border
        stripe
        :expand-row-keys="expandedProjects"
        @expand-change="onExpand"
      >
        <el-table-column type="expand" width="46">
          <template #default="{ row: p }">
            <div class="report-body">
              <div class="rb-sec">
                <div class="rb-h">本周任务（{{ p.tasks.length }}）</div>
                <el-table :data="p.tasks" size="small" border>
                  <el-table-column prop="title" label="任务" min-width="180" />
                  <el-table-column label="状态" width="90">
                    <template #default="{ row }">
                      <el-tag size="small" :type="taskTag(row)">{{ taskText(row) }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="planned_end" label="计划完成" width="110" />
                  <el-table-column prop="actual_end" label="实际完成" width="110">
                    <template #default="{ row }">{{ row.actual_end || '—' }}</template>
                  </el-table-column>
                </el-table>
              </div>
              <el-row :gutter="16" style="margin-top:12px">
                <el-col :span="14">
                  <div class="rb-h">每日进展</div>
                  <el-timeline v-if="Object.keys(p.daily).length">
                    <el-timeline-item v-for="(items, d) in p.daily" :key="d" :timestamp="d" placement="top">
                      <div v-for="(it, i) in items" :key="i" class="daily-item">
                        <b>{{ it.author }}</b>：{{ it.today_work }}
                        <div v-if="it.risk" class="risk">⚠ {{ it.risk }}</div>
                      </div>
                    </el-timeline-item>
                  </el-timeline>
                  <div v-else class="empty">本周暂无进展记录</div>
                </el-col>
                <el-col :span="10">
                  <div class="rb-h">风险问题（点击可关闭/重新打开）</div>
                  <div v-if="p.risks.length">
                    <div v-for="(r, i) in p.risks" :key="i" class="risk-item" :class="{ resolved: r.resolved }"
                         @click="onToggleRisk(r)">
                      <el-icon :size="14" class="risk-ico"><CircleCheckFilled v-if="r.resolved" /><WarningFilled v-else /></el-icon>
                      <span class="risk-txt">{{ r.risk }}</span>
                      <span class="risk-meta">[{{ r.date }}] {{ r.author }}</span>
                      <el-tag v-if="r.resolved" size="small" type="success" effect="plain">已解决</el-tag>
                    </div>
                  </div>
                  <div v-else class="empty">无</div>
                </el-col>
              </el-row>
            </div>
          </template>
        </el-table-column>
        <el-table-column v-if="visibleCols.includes('machine')" label="机型" width="120" sortable :sort-by="(row) => row.project?.machine_model || ''">
          <template #default="{ row }">{{ row.project.machine_model || '—' }}</template>
        </el-table-column>
        <el-table-column v-if="visibleCols.includes('name')" label="项目名称" min-width="180" sortable :sort-by="(row) => row.project?.name || ''">
          <template #default="{ row }">
            <span class="project-name" @click="goDetail(row.project)">{{ row.project.name }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="visibleCols.includes('description')" label="项目描述" min-width="220" sortable :sort-by="(row) => row.project?.description || ''">
          <template #default="{ row }">
            <div class="desc-cell">{{ row.project.description || '—' }}</div>
          </template>
        </el-table-column>
        <el-table-column v-if="visibleCols.includes('status')" label="状态" width="104" sortable :sort-by="(row) => row.project?.status || ''">
          <template #default="{ row }">
            <span class="status-chip" :class="'st-' + row.project.status">{{ statusMap[row.project.status] || row.project.status }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="visibleCols.includes('roles')" label="项目角色" min-width="180">
          <template #default="{ row }">
            <span class="role-summary">{{ row.project.project_roles || '未分配' }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="visibleCols.includes('current_node')" label="当前节点" min-width="200">
          <template #default="{ row }">
            <div v-if="currentNodeList(row).length" class="cn-list">
              <div v-for="n in currentNodeList(row)" :key="n.id" class="cn-row" :class="{ current: n.is_current }">
                <span class="cn-key">{{ n.node_key }}</span>
                <span class="cn-date">{{ n.planned_end || '—' }}</span>
                <span v-if="n.overdue" class="cn-overdue">超期</span>
              </div>
            </div>
            <span v-else class="pm-sub">未设置</span>
          </template>
        </el-table-column>
        <el-table-column v-if="visibleCols.includes('subnodes')" label="子节点" min-width="200">
          <template #default="{ row }">
            <div v-if="row.subnodes && row.subnodes.length" class="sub-inline-list">
              <div v-for="s in row.subnodes" :key="s.id" class="sub-inline" :class="{ done: s.status==='done' }"
                   @click="onToggleSub(s)" :title="`${s.name}（点击切换完成）`">
                <el-icon :size="13"><Select v-if="s.status==='done'" /><CircleCheck v-else /></el-icon>
                <span v-if="s.status==='done'" class="si-date">{{ shortDate(s.actual_end) }}</span>
                <span v-else-if="s.overdue" class="si-date si-overdue">{{ shortDate(s.planned_end) }} 延期</span>
                <span v-else-if="s.planned_end" class="si-date">{{ shortDate(s.planned_end) }}</span>
                <span class="si-name">{{ s.name }}</span>
              </div>
            </div>
            <span v-else class="pm-sub">无</span>
          </template>
        </el-table-column>
        <el-table-column v-if="visibleCols.includes('goals')" label="周目标" min-width="200">
          <template #default="{ row }">
            <div v-if="row.weekly_goal_items && row.weekly_goal_items.length" class="goal-items">
              <div v-for="g in row.weekly_goal_items" :key="g.id" class="goal-item" :class="{ done: g.done }"
                   @click="onToggleGoalItem(g)" :title="`${g.goal}（点击切换完成）`">
                <el-icon :size="13"><Select v-if="g.done" /><CircleCheck v-else /></el-icon>
                <span v-if="g.done" class="gi-date">{{ g.done_at }}</span>
                <span v-else-if="g.overdue" class="gi-date gi-overdue">超期 {{ g.deadline }}</span>
                <span v-else-if="g.deadline" class="gi-date">{{ g.deadline }}</span>
                <span v-if="g.user_name" class="gi-owner">{{ g.user_name }}</span>
                <span class="gi-goal">{{ g.goal }}</span>
              </div>
            </div>
            <div v-else class="goal-cell">{{ row.weekly_goal || '（未设周目标）' }}</div>
          </template>
        </el-table-column>
        <el-table-column v-if="visibleCols.includes('today_plan')" label="今日目标" min-width="180">
          <template #default="{ row }">
            <div v-if="(row.today_plan || []).length" class="plan-inline">
              <div v-for="(it, i) in row.today_plan" :key="i" class="plan-inline-item">
                <span class="di-author">{{ it.author }}</span>
                <span class="di-work">{{ it.plan }}</span>
              </div>
            </div>
            <span v-else class="pm-sub">无</span>
          </template>
        </el-table-column>
        <el-table-column v-if="visibleCols.includes('daily')" label="每日进展" min-width="220">
          <template #default="{ row }">
            <div v-if="dailyItems(row).length" class="daily-inline">
              <div v-for="(it, i) in dailyItems(row)" :key="i" class="daily-inline-item">
                <span class="di-date">{{ it.date }}</span>
                <span class="di-author">{{ it.author }}</span>
                <span class="di-work">{{ it.today_work }}</span>
                <el-tag v-if="it.risk && !it.risk_resolved" size="small" type="warning" effect="plain">风险</el-tag>
              </div>
            </div>
            <span v-else class="pm-sub">无</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!projectReports.length" description="暂无在研项目" />
    </div>

    <!-- 按人视图 -->
    <div v-else v-loading="loading" class="pm-card table-card">
      <el-table :data="filteredPersonReports" border stripe v-if="filteredPersonReports.length">
        <el-table-column prop="display_name" label="成员" width="110" fixed />
        <el-table-column label="项目（角色/投入/进展数）" min-width="320">
          <template #default="{ row }">
            <div v-for="p in row.projects" :key="p.project_id" class="pp-item">
              <el-tag size="small" effect="plain">{{ p.name }}</el-tag>
              <span class="pm-sub">{{ p.project_role || '成员' }}</span>
              <el-tag size="small" :type="p.is_invested ? 'success' : 'info'" effect="plain">{{ p.is_invested ? '投入' : '未投入' }}</el-tag>
              <span class="pm-sub">{{ p.progress_count }}条进展</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="每日进展" min-width="380">
          <template #default="{ row }">
            <el-popover width="480" trigger="click">
              <template #reference>
                <el-link type="primary">查看明细（{{ Object.keys(row.daily).length }}天）</el-link>
              </template>
              <el-timeline>
                <el-timeline-item v-for="(items, d) in row.daily" :key="d" :timestamp="d" placement="top">
                  <div v-for="(it, i) in items" :key="i" class="daily-item">
                    <el-tag size="small" effect="plain">{{ it.project }}</el-tag> {{ it.today_work }}
                    <div v-if="it.risk" class="risk">⚠ {{ it.risk }}</div>
                  </div>
                </el-timeline-item>
              </el-timeline>
            </el-popover>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无数据" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { groupWeekly, projectWeekly, listProjects, listUserOptions, exportLedger, setSubnodeStatus, setProgressRiskResolved, setWeeklyGoalItemDone } from '../api'
import { todayStr } from '../utils/date'
import { ElMessage } from 'element-plus'
import { useViewFilterStore } from '../store/filters'

const router = useRouter()
const viewFilters = useViewFilterStore()
const weekStart = computed({ get: () => viewFilters.weekly.weekStart, set: (v) => { viewFilters.weekly.weekStart = v } })
const view = computed({ get: () => viewFilters.weekly.view, set: (v) => { viewFilters.weekly.view = v } })

// 重置筛选回默认值（机型/状态/角色/按人/周次回本周）
function onReset() {
  viewFilters.reset('weekly')
  load()
}

// 列显示/隐藏（按项目视图；展开列固定展示；配置持久化到 localStorage）
const colOptions = [
  { key: 'machine', label: '机型' },
  { key: 'name', label: '项目名称' },
  { key: 'description', label: '项目描述' },
  { key: 'status', label: '状态' },
  { key: 'roles', label: '项目角色' },
  { key: 'current_node', label: '当前节点' },
  { key: 'subnodes', label: '子节点' },
  { key: 'goals', label: '周目标' },
  { key: 'today_plan', label: '今日目标' },
  { key: 'daily', label: '每日进展' },
]
const visibleCols = computed(() => viewFilters.columns.weekly)
// 显示选项：仅今日每日进展（持久化）
const dailyTodayOnly = computed({
  get: () => viewFilters.weekly.dailyTodayOnly ?? false,
  set: (v) => { viewFilters.weekly.dailyTodayOnly = v },
})
function toggleCol(key, on) {
  const cur = new Set(viewFilters.columns.weekly)
  if (on) cur.add(key); else cur.delete(key)
  viewFilters.columns.weekly = [...cur]
}
function onResetCols() { viewFilters.resetColumns('weekly') }
const loading = ref(false)
const projectReports = ref([])
const filterMachine = computed({ get: () => viewFilters.weekly.filterMachine, set: (v) => { viewFilters.weekly.filterMachine = v } })
const machineOptions = computed(() => {
  const set = new Set()
  projectReports.value.forEach((p) => {
    if (p.project?.machine_model) set.add(p.project.machine_model)
  })
  return [...set]
})
const filteredReports = computed(() => {
  let list = projectReports.value
  if (filterMachine.value) list = list.filter((p) => p.project?.machine_model === filterMachine.value)
  if (filterStatus.value) list = list.filter((p) => p.project?.status === filterStatus.value)
  if (filterRole.value) list = list.filter((p) => roleHasMember(p.project, filterRole.value))
  if (filterPerson.value) {
    const name = memberUsers.value.find((u) => u.id === filterPerson.value)?.display_name
    if (name) list = list.filter((p) => hasPerson(p.project, name))
  }
  return list
})
const personReports = ref([])
const expandedProjects = ref([])
const exporting = ref(false)
// 项目视图按人筛选用的全部用户（/users/options）
const memberUsers = ref([])

// FO/TL 筛选：按人 + 角色，方便查看某个人投入了哪些项目
const filterPerson = computed({ get: () => viewFilters.weekly.filterPerson, set: (v) => { viewFilters.weekly.filterPerson = v } })
const filterRole = computed({ get: () => viewFilters.weekly.filterRole, set: (v) => { viewFilters.weekly.filterRole = v } })
const filterStatus = computed({ get: () => viewFilters.weekly.filterStatus, set: (v) => { viewFilters.weekly.filterStatus = v } })
const roleFilterOptions = [
  { value: 'TL/FO', label: 'FO/TL' },
  { value: 'SE', label: 'SE' },
  { value: 'TPM', label: 'TPM' },
  { value: 'CodeReview', label: 'CodeReview' },
  { value: '负责人', label: '负责人' },
]
const personUsers = computed(() => personReports.value.map((p) => ({ user_id: p.user_id, display_name: p.display_name })))
// project_role 可能是 "TL/FO" 或合并串（如 "TL/FO、CodeReview"），按分隔符精确匹配
const matchRole = (roleStr, role) => (roleStr || '').split(/[、,，;；]/).some((r) => r.trim() === role)
// 项目视图：项目周报的 project_roles 是"角色: 姓名、姓名"多行文本，按角色/成员过滤项目
const roleHasMember = (project, role) => (project?.project_roles || '').split('\n').some((line) => {
  const i = line.indexOf(':')
  return i > 0 && line.slice(0, i).trim() === role && line.slice(i + 1).trim()
})
const hasPerson = (project, name) => Boolean(name && (project?.project_roles || '').includes(name))
const filteredPersonReports = computed(() => {
  let list = personReports.value
  if (filterPerson.value) list = list.filter((p) => p.user_id === filterPerson.value)
  if (filterRole.value) {
    list = list
      .map((p) => ({ ...p, projects: p.projects.filter((pj) => matchRole(pj.project_role, filterRole.value)) }))
      .filter((p) => p.projects.length)
  }
  return list
})

// 项目状态（手动配置）显示
const statusOptions = [
  { value: 'not_started', label: '未开始' },
  { value: 'in_progress', label: '进行中' },
  { value: 'delayed', label: '延期' },
  { value: 'completed', label: '已完成' },
  { value: 'suspended', label: '暂停' },
]
const statusMap = Object.fromEntries(statusOptions.map((o) => [o.value, o.label]))
const statusColor = (s) => ({ not_started: '#5b6b7c', in_progress: '#0284c7', delayed: '#dc3c3c', completed: '#0d9d6c', suspended: '#cf8207' }[s] || '#5b7180')
const taskTag = (t) => (t.status === 'done' ? 'success' : t.overdue ? 'danger' : t.status === 'in_progress' ? 'primary' : 'info')
const taskText = (t) => (t.status === 'done' ? '已完成' : t.overdue ? '逾期' : t.status === 'in_progress' ? '进行中' : '未开始')
const doneTaskCount = (tasks) => tasks.filter((t) => t.status === 'done').length

// 当前节点列：隐藏已完成的节点，只显示进行中/待开始的
const currentNodeList = (row) => (row.project.nodes || []).filter((n) => n.status !== 'passed')

// 跳转项目详情
function goDetail(project) {
  router.push({ name: 'project-detail', params: { id: project.id } })
}

// 短日期 MM-DD
const shortDate = (d) => (d ? String(d).slice(5) : '')

// 每日进展列：把 p.daily 展平成有序列表（日期正序，周一~周日）；有风险的进展固定排最后一行，且不被截断
function dailyItems(row) {
  const todayIso = todayStr()
  let dates = Object.keys(row.daily || {}).sort()
  if (dailyTodayOnly.value) dates = dates.filter((d) => d === todayIso)
  const items = []
  for (const d of dates) {
    for (const it of row.daily[d] || []) {
      items.push({ date: d.slice(5), author: it.author, today_work: it.today_work, risk: it.risk, risk_resolved: it.risk_resolved })
    }
  }
  const safe = items.filter((it) => !(it.risk && !it.risk_resolved))
  const risks = items.filter((it) => it.risk && !it.risk_resolved)
  return [...safe.slice(0, Math.max(0, 4 - risks.length)), ...risks]
}

async function onToggleRisk(r) {
  const target = !r.resolved
  const updated = await setProgressRiskResolved(r.progress_id, target)
  ElMessage.success(target ? '已关闭风险' : '已重新打开风险')
  if (updated) {
    r.resolved = updated.resolved
  }
}

async function onToggleGoalItem(g) {
  const updated = await setWeeklyGoalItemDone(g.id, !g.done)
  ElMessage.success(g.done ? `「${g.goal}」已取消完成` : `「${g.goal}」已完成`)
  if (updated) {
    Object.assign(g, { done: updated.done, done_at: updated.done_at })
  }
}

function onExpand(row, expandedRows) {
  const opened = expandedRows.some((item) => item.project.id === row.project.id)
  expandedProjects.value = opened ? [row.project.id] : []
}

// 分页拉全量项目（后端 size 上限 100，逐个翻页直至取完）
async function fetchAllProjects() {
  const all = []
  const size = 100
  let page = 1
  for (;;) {
    const data = await listProjects({ page, size })
    all.push(...data.list)
    if (!data.list.length || all.length >= data.total) break
    page += 1
  }
  return all
}

// 加载序号守卫：重置/切周会并发触发 load，旧请求晚返回会覆盖新数据（显示错乱）。
// 每次 load 自增序号，任一 await 返回后发现序号过期即放弃本次写入。
let loadSeq = 0

async function load() {
  const seq = ++loadSeq
  const ws = weekStart.value  // 稳定周次：reset 在循环中改 store 也不会污染本次请求
  loading.value = true
  try {
    if (view.value === 'project') {
      const projects = await fetchAllProjects()
      if (seq !== loadSeq) return
      const reports = []
      for (const p of projects) {
        reports.push(await projectWeekly(p.id, ws))
        if (seq !== loadSeq) return  // 已有更新的 load，放弃本次
      }
      projectReports.value = reports
      expandedProjects.value = []
    } else {
      personReports.value = await groupWeekly('person', ws)
      if (seq !== loadSeq) return
    }
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

async function onToggleSub(s) {
  const target = s.status === 'done' ? 'in_progress' : 'done'
  const updated = await setSubnodeStatus(s.id, target)
  ElMessage.success(target === 'done' ? `子节点「${s.name}」已完成` : `已取消「${s.name}」完成`)
  if (updated) {
    Object.assign(s, { status: updated.status, actual_end: updated.actual_end, overdue: updated.overdue })
  }
}

async function downloadLedger(type = 'weekly') {
  exporting.value = true
  try {
    // 本周台账按当前列启用状态导出（含今日目标列是否勾选）
    const cols = type === 'weekly' ? visibleCols.value.join(',') : undefined
    const response = await exportLedger(weekStart.value, type, cols)
    const blob = new Blob([response], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = type === 'completion' ? '项目完成台账.xlsx'
      : type === 'project' ? '项目台账.xlsx'
      : `本周台账_${weekStart.value}.xlsx`
    link.click()
    URL.revokeObjectURL(url)
  } finally {
    exporting.value = false
  }
}

onMounted(async () => {
  memberUsers.value = await listUserOptions()
  load()
})
</script>

<style scoped>
.toolbar-card { padding: 14px 18px; margin-bottom: 14px; }
.weekly-toolbar { justify-content: space-between; align-items: center; gap: 12px; }
.weekly-toolbar .tb-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; flex: 1; min-width: 0; }
.weekly-toolbar .tb-right { display: flex; align-items: center; gap: 10px; flex-wrap: nowrap; flex-shrink: 0; }
.weekly-toolbar .tb-right .el-button + .el-button { margin-left: 0; }
.table-card { padding: 6px 18px 16px; }
.project-name { font-weight: 700; cursor: pointer; color: var(--pm-primary); }
.project-name:hover { text-decoration: underline; }
.desc-cell { white-space: pre-wrap; word-break: break-word; line-height: 1.5; color: var(--pm-text-2); font-size: 12.5px; }
.col-settings { display: flex; flex-direction: column; gap: 6px; }
.col-settings .el-checkbox { margin-right: 0; }
.cs-h { font-size: 12px; font-weight: 600; color: var(--pm-text-3); margin: 2px 0; }
.plan-inline { display: flex; flex-direction: column; gap: 4px; }
.plan-inline-item { display: flex; align-items: flex-start; gap: 5px; font-size: 12.5px; line-height: 1.5; }
.role-summary { white-space: pre-line; line-height: 1.45; font-size: 12px; }
.node-deadline { margin-top: 3px; }
.report-body { padding: 6px 4px; }
.rb-sec { margin-bottom: 8px; }
.rb-h { font-weight: 700; font-size: 13px; margin-bottom: 8px; color: var(--pm-text-2); }
.daily-item { font-size: 13px; margin-bottom: 6px; white-space: pre-wrap; word-break: break-word; overflow-wrap: break-word; line-height: 1.6; }
.risk { color: var(--pm-danger); font-size: 12px; white-space: pre-wrap; word-break: break-word; }
.empty { color: var(--pm-text-3); font-size: 13px; padding: 8px 0; }
.pp-item { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.subnode-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.sub-inline-list, .cn-list { display: flex; flex-direction: column; gap: 3px; }
.cn-row, .sub-inline { display: flex; align-items: center; gap: 6px; font-size: 12.5px; padding: 2px 4px; border-radius: 6px; min-height: 26px; box-sizing: border-box; }
.cn-row.current { background: var(--pm-primary-light); }
.cn-key { font-weight: 700; flex-shrink: 0; }
.cn-row.current .cn-key { color: var(--pm-primary); }
.cn-date { color: var(--pm-text-3); white-space: nowrap; flex-shrink: 0; }
.cn-overdue { color: var(--pm-danger); font-size: 12px; font-weight: 600; flex-shrink: 0; }
.goal-cell { white-space: pre-wrap; word-break: break-word; overflow-wrap: break-word; line-height: 1.5; }
.goal-items { display: flex; flex-direction: column; gap: 3px; }
.goal-item { display: flex; align-items: flex-start; gap: 6px; padding: 3px 6px; border-radius: 6px; cursor: pointer; font-size: 12.5px; line-height: 1.5; min-height: 24px; }
.goal-item:hover { background: var(--pm-primary-light); }
.goal-item.done { background: var(--pm-st-completed-bg); }
.goal-item.done .gi-goal { color: var(--pm-success); text-decoration: line-through; }
.goal-item .el-icon { flex-shrink: 0; height: 18px; display: inline-flex; align-items: center; color: var(--pm-primary); }
.goal-item.done .el-icon { color: var(--pm-success); }
.gi-goal { flex: 1; min-width: 0; white-space: pre-wrap; word-break: break-word; }
.gi-owner { color: var(--pm-primary); font-weight: 600; flex-shrink: 0; }
.gi-date { color: var(--pm-text-3); white-space: nowrap; flex-shrink: 0; }
.gi-overdue { color: var(--pm-danger); font-weight: 600; }
.sub-inline { cursor: pointer; }
.sub-inline:hover { background: var(--pm-primary-light); }
.sub-inline.done { background: var(--pm-st-completed-bg); }
.sub-inline.done .si-name { color: var(--pm-success); text-decoration: line-through; }
.sub-inline.done .el-icon { color: var(--pm-success); }
.sub-inline .el-icon { color: var(--pm-primary); flex-shrink: 0; }
.si-name { flex: 1; min-width: 0; white-space: pre-wrap; word-break: break-word; overflow-wrap: break-word; line-height: 1.4; }
.si-date { color: var(--pm-text-3); font-size: 11.5px; white-space: nowrap; flex-shrink: 0; }
.si-overdue { color: var(--pm-danger); font-weight: 600; }

.daily-inline { display: flex; flex-direction: column; gap: 4px; }
.daily-inline-item { display: flex; align-items: flex-start; gap: 5px; font-size: 12.5px; line-height: 1.5; }
.di-date { color: var(--pm-text-3); font-size: 11px; white-space: nowrap; background: var(--pm-st-notstarted-bg); padding: 0 5px; border-radius: 4px; flex-shrink: 0; }
.di-author { color: var(--pm-primary); font-weight: 600; font-size: 12px; white-space: nowrap; flex-shrink: 0; }
.di-work { flex: 1; min-width: 0; white-space: pre-wrap; word-break: break-word; overflow-wrap: break-word; }

.risk-item { display: flex; align-items: center; gap: 6px; font-size: 13px; margin-bottom: 8px; padding: 5px 8px; border-radius: 6px; cursor: pointer; background: var(--pm-st-delayed-bg); }
.risk-item:hover { outline: 1px solid var(--pm-danger); }
.risk-item.resolved { background: var(--pm-st-completed-bg); }
.risk-ico { color: var(--pm-danger); flex-shrink: 0; }
.risk-item.resolved .risk-ico { color: var(--pm-success); }
.risk-txt { flex: 1; min-width: 0; }
.risk-item.resolved .risk-txt { color: var(--pm-text-3); text-decoration: line-through; }
.risk-meta { color: var(--pm-text-3); font-size: 11.5px; white-space: nowrap; }
.subnode-chip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; background: var(--pm-fill-light, #f4f7f8); border: 1px solid var(--pm-border); border-radius: 20px; cursor: pointer; font-size: 13px; transition: all .15s; }
.subnode-chip:hover { border-color: var(--pm-primary); background: var(--pm-primary-light); }
.subnode-chip.done { background: var(--pm-st-completed-bg); border-color: var(--pm-st-completed-bd); }
.subnode-chip.done .sn-txt { color: var(--pm-text-3); text-decoration: line-through; }
</style>
