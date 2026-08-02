<template>
  <div>
    <div class="pm-toolbar">
      <span class="pm-page-title">个人绩效</span>
      <div style="flex:1"></div>
      <el-radio-group v-model="period" @change="load">
        <el-radio-button value="month">月度</el-radio-button>
        <el-radio-button value="quarter">季度</el-radio-button>
        <el-radio-button value="year">年度</el-radio-button>
      </el-radio-group>
      <el-date-picker v-model="refDate" type="date" value-format="YYYY-MM-DD" style="width: 150px" @change="load" />
    </div>

    <el-row :gutter="16">
      <!-- 工作汇总 -->
      <el-col :span="11">
        <div class="pm-card">
          <div class="card-title" style="margin-bottom:12px">工作汇总
            <span class="pm-sub">（{{ summary.period_start }} ~ {{ summary.period_end }}）</span>
          </div>
          <div class="stat-row">
            <div class="stat"><div class="stat-num">{{ summary.projects.length }}</div><div class="stat-label">参与项目</div></div>
            <div class="stat"><div class="stat-num">{{ summary.total_progress }}</div><div class="stat-label">进展记录</div></div>
            <div class="stat"><div class="stat-num">{{ totalDoneTasks }}</div><div class="stat-label">完成任务</div></div>
          </div>
          <el-divider />
          <div v-if="!summary.projects.length" class="empty">该周期暂无工作记录</div>
          <el-collapse v-else>
            <el-collapse-item v-for="p in summary.projects" :key="p.project_id" :name="p.project_id">
              <template #title>
                <div class="sp-title">
                  <span class="pm-dot primary"></span>{{ p.name }}
                  <span class="pm-sub">{{ p.project_role || '成员' }}</span>
                  <span class="pm-sub" style="margin-left:auto">{{ p.progress_count }}进展 / {{ p.done_task_count }}任务</span>
                </div>
              </template>
              <div v-if="p.done_tasks.length" class="sec">
                <div class="sec-h">✓ 完成任务</div>
                <div v-for="t in p.done_tasks" :key="t.id" class="task-line">{{ t.title }} <span class="pm-sub">{{ t.actual_end }}</span></div>
              </div>
              <div v-if="p.progresses.length" class="sec">
                <div class="sec-h">进展记录</div>
                <el-timeline>
                  <el-timeline-item v-for="(pr, i) in p.progresses" :key="i" :timestamp="pr.date" placement="top">
                    {{ pr.today_work }}
                    <div v-if="pr.risk" class="risk">⚠ {{ pr.risk }}</div>
                  </el-timeline-item>
                </el-timeline>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </el-col>

      <!-- AI 绩效总结 -->
      <el-col :span="13">
        <div class="pm-card">
          <div class="pm-flex-between" style="margin-bottom:12px">
            <span class="card-title">AI 绩效总结</span>
            <el-button type="primary" :loading="generating" @click="generate">
              <el-icon style="margin-right:4px"><MagicStick /></el-icon>{{ aiSummary ? '重新生成' : '生成绩效总结' }}
            </el-button>
          </div>

          <div v-if="generating" class="ai-loading">
            <el-icon class="is-loading"><Loading /></el-icon> AI 正在汇总生成中…
          </div>

          <div v-else-if="aiSummary">
            <el-alert v-if="aiSummary.status === 'failed'" type="warning" :closable="false" style="margin-bottom:10px"
                      title="AI 服务不可用，已降级为模板汇总" :description="aiSummary.error" />
            <div class="ai-meta">
              <el-tag size="small" effect="plain">{{ aiSummary.model }}</el-tag>
              <el-tag size="small" :type="aiSummary.status === 'edited' ? 'warning' : 'success'" effect="plain">
                {{ aiSummary.status === 'edited' ? '已人工编辑' : '已生成' }}
              </el-tag>
              <el-link v-if="aiSummary.source_snapshot" type="info" @click="showSource = true">查看数据依据</el-link>
            </div>
            <el-input v-model="editContent" type="textarea" :rows="16" class="ai-content" />
            <div style="margin-top:12px; display:flex; gap:10px">
              <el-button type="primary" @click="saveEdit">保存编辑</el-button>
              <el-button @click="exportSummary">导出</el-button>
            </div>
          </div>

          <div v-else class="empty" style="padding:60px 0">
            <el-icon :size="40" style="color:var(--pm-text-3)"><MagicStick /></el-icon>
            <div style="margin-top:12px">点击"生成绩效总结"，AI 将基于本周期的工作数据自动生成</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 数据依据抽屉 -->
    <el-drawer v-model="showSource" title="生成依据" size="420px">
      <div v-if="aiSummary?.source_snapshot">
        <p class="pm-sub">模型：{{ aiSummary.source_snapshot.model }} ｜ 数据项：{{ aiSummary.source_snapshot.item_count }}</p>
        <el-divider />
        <div v-for="(it, i) in aiSummary.source_snapshot.items" :key="i" class="src-item">
          <el-tag size="small" effect="plain">{{ it.type }}</el-tag> {{ it.excerpt }}
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { editAiSummary, genAiSummary, getAiSummary, personalSummary } from '../api'
import { useUserStore } from '../store/user'

const store = useUserStore()
const uid = computed(() => store.userInfo?.id)
const period = ref('month')
const refDate = ref(new Date().toISOString().slice(0, 10))
const summary = ref({ projects: [], total_progress: 0 })
const aiSummary = ref(null)
const editContent = ref('')
const generating = ref(false)
const showSource = ref(false)

const totalDoneTasks = computed(() => summary.value.projects.reduce((s, p) => s + p.done_task_count, 0))

async function load() {
  if (!uid.value) return
  summary.value = await personalSummary(uid.value, { period: period.value, date: refDate.value })
  aiSummary.value = await getAiSummary(uid.value, { period: period.value, date: refDate.value })
  editContent.value = aiSummary.value?.content || ''
}

async function generate() {
  generating.value = true
  try {
    await genAiSummary(uid.value, { period: period.value, date: refDate.value })
    aiSummary.value = await getAiSummary(uid.value, { period: period.value, date: refDate.value })
    editContent.value = aiSummary.value?.content || ''
    ElMessage.success('已生成')
  } finally { generating.value = false }
}

async function saveEdit() {
  if (!aiSummary.value) return
  await editAiSummary(aiSummary.value.id, { edited_content: editContent.value })
  ElMessage.success('已保存')
  load()
}

function exportSummary() {
  const blob = new Blob([editContent.value], { type: 'text/markdown;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `绩效总结_${store.userInfo?.display_name}_${period.value}_${refDate.value}.md`
  a.click()
}

onMounted(load)
</script>

<style scoped>
.card-title { font-weight: 700; font-size: 15px; }
.stat-row { display: flex; gap: 24px; }
.stat { text-align: center; flex: 1; }
.stat-num { font-size: 26px; font-weight: 800; color: var(--pm-primary); }
.stat-label { color: var(--pm-text-3); font-size: 12px; margin-top: 4px; }
.empty { color: var(--pm-text-3); text-align: center; padding: 24px 0; font-size: 13px; }
.sp-title { display: flex; align-items: center; gap: 8px; width: 100%; font-weight: 600; }
.sec { margin: 8px 0; }
.sec-h { font-weight: 700; font-size: 12px; color: var(--pm-text-2); margin-bottom: 6px; }
.task-line { font-size: 13px; padding: 3px 0; }
.risk { color: var(--pm-danger); font-size: 12px; }
.ai-meta { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.ai-loading { text-align: center; padding: 60px 0; color: var(--pm-primary); font-size: 14px; }
.ai-content :deep(textarea) { font-family: inherit; line-height: 1.7; }
.src-item { font-size: 13px; margin-bottom: 8px; }
</style>
