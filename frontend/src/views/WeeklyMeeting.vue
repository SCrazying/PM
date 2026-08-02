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

    <!-- 按项目视图 -->
    <div v-if="view === 'project'" v-loading="loading">
      <el-collapse v-model="activeProjects">
        <el-collapse-item v-for="p in projectReports" :key="p.project.id" :name="p.project.id">
          <template #title>
            <div class="proj-title">
              <span class="pm-dot" :class="healthDot(p.project.health)"></span>
              <span class="pt-model" v-if="p.project.machine_model">{{ p.project.machine_model }}</span>
              <span class="pt-name">{{ p.project.name }}</span>
              <el-tag size="small" effect="plain" v-if="p.project.current_node">{{ p.project.current_node.node_key }}</el-tag>
              <span class="pt-goal">{{ p.weekly_goal || '（未设周目标）' }}</span>
            </div>
          </template>
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
                <div class="rb-h">风险问题</div>
                <div v-if="p.risks.length">
                  <div v-for="(r, i) in p.risks" :key="i" class="risk-item">⚠ [{{ r.date }}] {{ r.author }}：{{ r.risk }}</div>
                </div>
                <div v-else class="empty">无</div>
              </el-col>
            </el-row>
          </div>
        </el-collapse-item>
      </el-collapse>
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
import { groupWeekly, projectWeekly, listProjects, exportLedger } from '../api'

const today = new Date().toISOString().slice(0, 10)
const weekStart = ref(today)
const view = ref('project')
const loading = ref(false)
const projectReports = ref([])
const personReports = ref([])
const activeProjects = ref([])
const exporting = ref(false)

const healthDot = (h) => ({ on_track: 'success', at_risk: 'warning', delayed: 'danger' }[h] || 'info')
const taskTag = (t) => (t.status === 'done' ? 'success' : t.overdue ? 'danger' : t.status === 'in_progress' ? 'primary' : 'info')
const taskText = (t) => (t.status === 'done' ? '已完成' : t.overdue ? '延期' : t.status === 'in_progress' ? '进行中' : '未开始')

async function load() {
  loading.value = true
  try {
    if (view.value === 'project') {
      const projects = await listProjects({ status: 'in_progress', size: 100 })
      const reports = []
      for (const p of projects.list) {
        reports.push(await projectWeekly(p.id, weekStart.value))
      }
      projectReports.value = reports
      activeProjects.value = reports.map((r) => r.project.id)
    } else {
      personReports.value = await groupWeekly('person', weekStart.value)
    }
  } finally { loading.value = false }
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
.proj-title { display: flex; align-items: center; gap: 8px; width: 100%; }
.pt-model { background: var(--pm-primary-light); color: var(--pm-primary); font-size: 12px; padding: 1px 8px; border-radius: 6px; }
.pt-name { font-weight: 700; }
.pt-goal { color: var(--pm-text-3); font-size: 12px; margin-left: auto; margin-right: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 40%; }
.report-body { padding: 6px 4px; }
.rb-sec { margin-bottom: 8px; }
.rb-h { font-weight: 700; font-size: 13px; margin-bottom: 8px; color: var(--pm-text-2); }
.daily-item { font-size: 13px; margin-bottom: 6px; }
.risk { color: var(--pm-danger); font-size: 12px; }
.risk-item { color: var(--pm-danger); font-size: 13px; margin-bottom: 8px; }
.empty { color: var(--pm-text-3); font-size: 13px; padding: 8px 0; }
.pp-item { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
</style>
