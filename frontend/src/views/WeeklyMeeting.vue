<template>
  <div>
    <div class="pm-toolbar">
      <span class="pm-page-title">周会视图</span>
      <el-date-picker v-model="weekStart" type="week" format="YYYY 第 ww 周" value-format="YYYY-MM-DD"
                      style="width: 180px" @change="load" />
      <div style="flex:1"></div>
      <el-button type="success" :loading="exporting" @click="downloadLedger">
        <el-icon style="margin-right:5px"><Download /></el-icon>导出项目台账
      </el-button>
      <el-radio-group v-model="view" @change="load">
        <el-radio-button value="project">按项目</el-radio-button>
        <el-radio-button value="person">按人</el-radio-button>
      </el-radio-group>
    </div>

    <!-- Excel 风格项目台账：默认不展开，展开行查看周报详情。 -->
    <div v-if="view === 'project'" v-loading="loading">
      <el-table
        :data="projectReports"
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
        <el-table-column label="型号" width="120">
          <template #default="{ row }">{{ row.project.machine_model || '—' }}</template>
        </el-table-column>
        <el-table-column label="项目" min-width="180">
          <template #default="{ row }">
            <div class="project-name">{{ row.project.name }}</div>
            <div class="pm-sub">{{ row.project.code }}</div>
          </template>
        </el-table-column>
        <el-table-column label="项目角色" min-width="180">
          <template #default="{ row }">
            <span class="role-summary">{{ row.project.project_roles || '未分配' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="当前节点" min-width="200">
          <template #default="{ row }">
            <div v-if="row.project.nodes && row.project.nodes.length" class="cn-list">
              <div v-for="n in row.project.nodes" :key="n.id" class="cn-row" :class="{ current: n.is_current, done: n.status==='passed' }">
                <el-tag size="small" effect="plain"
                        :type="n.is_current ? 'primary' : (n.status==='passed' ? 'success' : 'info')">{{ n.node_key }}</el-tag>
                <el-tag v-if="n.overdue" size="small" type="warning">超期</el-tag>
                <span class="cn-date">{{ n.planned_end || '' }}</span>
              </div>
            </div>
            <span v-else class="pm-sub">未设置</span>
          </template>
        </el-table-column>
        <el-table-column label="子节点" min-width="200">
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
        <el-table-column label="每日进展" min-width="220">
          <template #default="{ row }">
            <div v-if="dailyItems(row).length" class="daily-inline">
              <div v-for="(it, i) in dailyItems(row)" :key="i" class="daily-inline-item">
                <span class="di-date">{{ it.date }}</span>
                <span class="di-author">{{ it.author }}</span>
                <span class="di-work">{{ it.today_work }}</span>
                <el-tag v-if="it.risk && !it.risk_resolved" size="small" type="warning" effect="plain">风险</el-tag>
                <el-tag v-else-if="it.risk && it.risk_resolved" size="small" type="success" effect="plain">风险已解决</el-tag>
              </div>
            </div>
            <span v-else class="pm-sub">无</span>
          </template>
        </el-table-column>
        <el-table-column label="周目标" min-width="180">
          <template #default="{ row }">{{ row.weekly_goal || '（未设周目标）' }}</template>
        </el-table-column>
        <el-table-column label="任务概况" width="100" align="center">
          <template #default="{ row }">{{ doneTaskCount(row.tasks) }}/{{ row.tasks.length }}</template>
        </el-table-column>
        <el-table-column label="健康度" width="90" align="center">
          <template #default="{ row }">
            <span class="health-cell"><span class="pm-dot" :class="healthDot(row.project.health)"></span>{{ healthText(row.project.health) }}</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!projectReports.length" description="暂无在研项目" />
    </div>

    <!-- 按人视图 -->
    <div v-else v-loading="loading">
      <el-table :data="personReports" border stripe v-if="personReports.length">
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
import { onMounted, ref } from 'vue'
import { groupWeekly, projectWeekly, listProjects, exportLedger, setSubnodeStatus, setProgressRiskResolved } from '../api'
import { ElMessage } from 'element-plus'

const today = new Date().toISOString().slice(0, 10)
const weekStart = ref(today)
const view = ref('project')
const loading = ref(false)
const projectReports = ref([])
const personReports = ref([])
const expandedProjects = ref([])
const exporting = ref(false)

const healthDot = (h) => ({ on_track: 'success', at_risk: 'warning', delayed: 'danger' }[h] || 'info')
const healthText = (h) => ({ on_track: '正常', at_risk: '风险', delayed: '延期' }[h] || h)
const taskTag = (t) => (t.status === 'done' ? 'success' : t.overdue ? 'danger' : t.status === 'in_progress' ? 'primary' : 'info')
const taskText = (t) => (t.status === 'done' ? '已完成' : t.overdue ? '逾期' : t.status === 'in_progress' ? '进行中' : '未开始')
const doneTaskCount = (tasks) => tasks.filter((t) => t.status === 'done').length

// 短日期 MM-DD
const shortDate = (d) => (d ? String(d).slice(5) : '')

// 每日进展列：把 p.daily 展平成有序列表（日期倒序，取最近 3 天）
function dailyItems(row) {
  const dates = Object.keys(row.daily || {}).sort().reverse()
  const items = []
  for (const d of dates) {
    for (const it of row.daily[d] || []) {
      items.push({ date: d.slice(5), author: it.author, today_work: it.today_work, risk: it.risk, risk_resolved: it.risk_resolved })
    }
  }
  return items.slice(0, 4)
}

async function onToggleRisk(r) {
  const target = !r.resolved
  const updated = await setProgressRiskResolved(r.progress_id, target)
  ElMessage.success(target ? '已关闭风险' : '已重新打开风险')
  if (updated) {
    r.resolved = updated.resolved
  }
}

function onExpand(row, expandedRows) {
  const opened = expandedRows.some((item) => item.project.id === row.project.id)
  expandedProjects.value = opened ? [row.project.id] : []
}

async function load() {
  loading.value = true
  try {
    if (view.value === 'project') {
      const projects = await listProjects({ status: 'in_progress', size: 100 })
      const reports = []
      for (const p of projects.list) reports.push(await projectWeekly(p.id, weekStart.value))
      projectReports.value = reports
      expandedProjects.value = []
    } else {
      personReports.value = await groupWeekly('person', weekStart.value)
    }
  } finally {
    loading.value = false
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

async function downloadLedger() {
  exporting.value = true
  try {
    const response = await exportLedger(weekStart.value)
    const blob = new Blob([response], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `项目台账_${weekStart.value}.xlsx`
    link.click()
    URL.revokeObjectURL(url)
  } finally {
    exporting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.project-name { font-weight: 700; }
.role-summary { white-space: pre-line; line-height: 1.45; font-size: 12px; }
.node-deadline { margin-top: 3px; }
.health-cell { display: inline-flex; align-items: center; gap: 6px; }
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
.cn-row.done .cn-date { color: var(--pm-success); }
.cn-date { color: var(--pm-text-3); white-space: nowrap; flex-shrink: 0; }
.sub-inline { cursor: pointer; }
.sub-inline:hover { background: var(--pm-primary-light); }
.sub-inline.done { background: #e9f9f0; }
.sub-inline.done .si-name { color: var(--pm-success); text-decoration: line-through; }
.sub-inline.done .el-icon { color: var(--pm-success); }
.sub-inline .el-icon { color: var(--pm-primary); flex-shrink: 0; }
.si-name { flex: 1; min-width: 0; white-space: pre-wrap; word-break: break-word; overflow-wrap: break-word; line-height: 1.4; }
.si-date { color: var(--pm-text-3); font-size: 11.5px; white-space: nowrap; flex-shrink: 0; }
.si-overdue { color: var(--pm-danger); font-weight: 600; }

.daily-inline { display: flex; flex-direction: column; gap: 4px; }
.daily-inline-item { display: flex; align-items: flex-start; gap: 5px; font-size: 12.5px; line-height: 1.5; }
.di-date { color: var(--pm-text-3); font-size: 11px; white-space: nowrap; background: #eef1f6; padding: 0 5px; border-radius: 4px; flex-shrink: 0; }
.di-author { color: var(--pm-primary); font-weight: 600; font-size: 12px; white-space: nowrap; flex-shrink: 0; }
.di-work { flex: 1; min-width: 0; white-space: pre-wrap; word-break: break-word; overflow-wrap: break-word; }

.risk-item { display: flex; align-items: center; gap: 6px; font-size: 13px; margin-bottom: 8px; padding: 5px 8px; border-radius: 6px; cursor: pointer; background: #fef3f2; }
.risk-item:hover { outline: 1px solid var(--pm-danger); }
.risk-item.resolved { background: #e9f9f0; }
.risk-ico { color: var(--pm-danger); flex-shrink: 0; }
.risk-item.resolved .risk-ico { color: var(--pm-success); }
.risk-txt { flex: 1; min-width: 0; }
.risk-item.resolved .risk-txt { color: var(--pm-text-3); text-decoration: line-through; }
.risk-meta { color: var(--pm-text-3); font-size: 11.5px; white-space: nowrap; }
.subnode-chip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; background: #f2f5fb; border: 1px solid var(--pm-border); border-radius: 20px; cursor: pointer; font-size: 13px; transition: all .15s; }
.subnode-chip:hover { border-color: var(--pm-primary); background: var(--pm-primary-light); }
.subnode-chip.done { background: #e9f9f0; border-color: #bfe8d4; }
.subnode-chip.done .sn-txt { color: var(--pm-text-3); text-decoration: line-through; }
</style>
