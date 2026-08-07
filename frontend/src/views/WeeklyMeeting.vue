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
              <div v-if="p.node_subnodes && p.node_subnodes.length" class="rb-sec">
                <div class="rb-h">子节点（点击勾选完成）</div>
                <div v-for="g in p.node_subnodes" :key="g.node_id" class="node-subnode-group">
                  <div class="nsg-head">
                    <el-tag size="small" effect="plain">{{ g.node_key }}</el-tag>
                    <span class="nsg-name">{{ g.name }}</span>
                    <span class="nsg-count">{{ g.subnodes.filter(s=>s.status==='done').length }}/{{ g.subnodes.length }} 完成</span>
                  </div>
                  <div class="subnode-grid">
                    <span v-for="s in g.subnodes" :key="s.id" class="subnode-chip" :class="{ done: s.status==='done' }"
                          @click="onToggleSub(g, s)">
                      <el-icon><Select v-if="s.status==='done'" /><CircleCheck v-else /></el-icon>
                      <span class="sn-txt">{{ s.name }}</span>
                      <el-tag v-if="s.status==='done'" size="small" type="success">{{ s.actual_end }}</el-tag>
                      <el-tag v-else-if="s.overdue" size="small" type="danger">延期 {{ s.planned_end }}</el-tag>
                      <el-tag v-else-if="s.planned_end" size="small" effect="plain">截止 {{ s.planned_end }}</el-tag>
                    </span>
                  </div>
                </div>
              </div>
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
                  <div class="rb-h">风险问题</div>
                  <div v-if="p.risks.length">
                    <div v-for="(r, i) in p.risks" :key="i" class="risk-item">⚠ [{{ r.date }}] {{ r.author }}：{{ r.risk }}</div>
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
        <el-table-column label="当前节点" min-width="170">
          <template #default="{ row }">
            <template v-if="row.project.current_node">
              <el-tag size="small" effect="plain">{{ row.project.current_node.node_key }} {{ row.project.current_node.name }}</el-tag>
              <el-tag v-if="row.project.current_node.overdue" size="small" type="warning" style="margin-left:4px">超期</el-tag>
              <div v-if="row.project.current_node.planned_end" class="pm-sub node-deadline">计划至 {{ row.project.current_node.planned_end }}</div>
            </template>
            <span v-else class="pm-sub">未设置</span>
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
import { groupWeekly, projectWeekly, listProjects, exportLedger, setSubnodeStatus } from '../api'
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

async function onToggleSub(group, s) {
  const target = s.status === 'done' ? 'in_progress' : 'done'
  const updated = await setSubnodeStatus(s.id, target)
  ElMessage.success(target === 'done' ? `子节点「${s.name}」已完成` : `已取消「${s.name}」完成`)
  // 局部同步更新，不整页重载
  if (group && updated) {
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
.daily-item { font-size: 13px; margin-bottom: 6px; }
.risk { color: var(--pm-danger); font-size: 12px; }
.risk-item { color: var(--pm-danger); font-size: 13px; margin-bottom: 8px; }
.empty { color: var(--pm-text-3); font-size: 13px; padding: 8px 0; }
.pp-item { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.subnode-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.node-subnode-group { margin-bottom: 10px; padding: 8px 10px; background: #f7f9fc; border-radius: 8px; }
.nsg-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.nsg-name { font-weight: 600; font-size: 13px; }
.nsg-count { margin-left: auto; font-size: 12px; color: var(--pm-text-3); white-space: nowrap; }
.subnode-chip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; background: #f2f5fb; border: 1px solid var(--pm-border); border-radius: 20px; cursor: pointer; font-size: 13px; transition: all .15s; }
.subnode-chip:hover { border-color: var(--pm-primary); background: var(--pm-primary-light); }
.subnode-chip.done { background: #e9f9f0; border-color: #bfe8d4; }
.subnode-chip.done .sn-txt { color: var(--pm-text-3); text-decoration: line-through; }
</style>
