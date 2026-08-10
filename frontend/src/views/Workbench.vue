<template>
  <div>
    <div class="pm-toolbar">
      <span class="pm-page-title">个人工作台</span>
      <span class="pm-sub">{{ today }}</span>
    </div>

    <el-row :gutter="16">
      <el-col :span="10">
        <div class="pm-card">
          <div class="pm-flex-between" style="margin-bottom:12px">
            <span class="card-title">今日进展填报</span>
            <el-tag size="small" type="info">{{ filledCount }}/{{ todo.projects.length }} 已填</el-tag>
          </div>
          <div v-if="!todo.projects.length" class="empty">暂无参与的在研项目</div>
          <div v-for="p in todo.projects" :key="p.id" class="todo-proj" @click="openFill(p)">
            <div class="tp-left">
              <span class="pm-dot" :class="p.filled_today ? 'success' : 'warning'"></span>
              <div>
                <div class="tp-name">{{ p.name }}</div>
                <div class="pm-sub">{{ p.code }} · {{ p.project_role || '成员' }}</div>
                <div class="pm-sub" v-if="p.current_node_name">
                  当前节点：{{ p.current_node_key }} {{ p.current_node_name }}
                  <span v-if="p.node_planned_end"> · 计划至 {{ p.node_planned_end }}</span>
                </div>
              </div>
            </div>
            <el-tag v-if="p.node_overdue" size="small" type="warning" effect="plain">节点超期</el-tag>
            <el-tag v-else size="small" :type="p.filled_today ? 'success' : 'warning'" effect="plain">
              {{ p.filled_today ? '已填报' : '待填报' }}
            </el-tag>
          </div>
        </div>

        <div class="pm-card" style="margin-top:16px">
          <div class="card-title" style="margin-bottom:12px">我的待办任务</div>
          <div v-if="!todo.tasks.length" class="empty">暂无待办任务</div>
          <div v-for="t in todo.tasks" :key="t.id" class="todo-task">
            <span class="pm-dot" :class="t.overdue ? 'danger' : (t.status==='in_progress' ? 'primary' : 'info')"></span>
            <span class="tt-title">{{ t.title }}</span>
            <span class="pm-sub" style="margin-left:auto">{{ t.planned_end || '' }}</span>
          </div>
        </div>

        <div class="pm-card" style="margin-top:16px">
          <div class="pm-flex-between" style="margin-bottom:12px">
            <span class="card-title">最近进展</span>
            <el-tag size="small" type="info">{{ todo.recent_progress.length }}</el-tag>
          </div>
          <div v-if="!todo.recent_progress.length" class="empty">暂无进展记录</div>
          <div v-for="p in todo.recent_progress" :key="p.id" class="recent-progress">
            <div class="recent-head">
              <div>
                <b>{{ p.project_name }}</b>
                <span class="pm-sub"> · {{ p.progress_date }}</span>
              </div>
              <el-button link type="primary" size="small" @click="openRecentEdit(p)">编辑</el-button>
            </div>
            <div class="recent-node pm-sub">{{ p.node_name || '项目级进展' }}</div>
            <div class="recent-work">{{ p.today_work }}</div>
            <div v-if="p.risk" class="risk">⚠ {{ p.risk }}</div>
          </div>
        </div>
      </el-col>

      <el-col :span="14">
        <div class="pm-card" v-if="fillProject">
          <div class="card-title" style="margin-bottom:14px">填报进展 · {{ fillProject.name }}</div>
          <el-form label-width="80px">
            <el-form-item label="日期">
              <el-date-picker v-model="fillForm.progress_date" type="date" value-format="YYYY-MM-DD" style="width:160px" />
            </el-form-item>
            <el-form-item label="所属节点">
              <el-select v-model="fillForm.project_node_id" clearable placeholder="项目级（默认）" style="width:260px">
                <el-option v-for="n in nodes" :key="n.id" :label="`${n.node_key} ${n.name}`" :value="n.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="今日进展" required>
              <el-input v-model="fillForm.today_work" type="textarea" :rows="3" placeholder="今天做了什么" />
            </el-form-item>
            <el-form-item label="明日计划">
              <el-input v-model="fillForm.tomorrow_plan" type="textarea" :rows="2" placeholder="明天计划做什么" />
            </el-form-item>
            <el-form-item label="风险问题">
              <el-input v-model="fillForm.risk" type="textarea" :rows="2" placeholder="遇到的风险/阻塞（可选）" />
            </el-form-item>
            <el-form-item label="关联任务">
              <el-select v-model="fillForm.task_ids" multiple clearable placeholder="选择相关任务" style="width:100%">
                <el-option v-for="t in projTasks" :key="t.id" :label="t.title" :value="t.id" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="saving" @click="submitFill">提交进展</el-button>
              <el-button @click="fillProject = null">取消</el-button>
            </el-form-item>
          </el-form>
        </div>

        <div class="pm-card fill-placeholder" v-else>
          <div class="fp-icon"><el-icon :size="30"><EditPen /></el-icon></div>
          <div class="card-title">填报今日进展</div>
          <p class="pm-sub">从左侧选择一个项目开始填报。进展会自动汇总到项目周报与周会视图，最近进展可直接编辑。</p>
        </div>
      </el-col>
    </el-row>

    <el-dialog v-model="progressEditVisible" title="编辑进展" width="620px" :close-on-click-modal="false">
      <el-form :model="progressEditForm" label-width="80px">
        <el-form-item label="日期"><span>{{ progressEditForm.progress_date }}</span></el-form-item>
        <el-form-item label="所属节点"><span>{{ progressEditForm.node_name || '项目级' }}</span></el-form-item>
        <el-form-item label="今日进展" required>
          <el-input v-model="progressEditForm.today_work" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="明日计划"><el-input v-model="progressEditForm.tomorrow_plan" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="风险问题"><el-input v-model="progressEditForm.risk" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="progressEditVisible = false">取消</el-button>
        <el-button type="primary" :loading="progressSaving" @click="saveRecentEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createProgress, listNodes, listTasks, myTodo, updateProgress } from '../api'
import { todayStr } from '../utils/date'

const today = todayStr()
const todo = reactive({ projects: [], tasks: [], recent_progress: [] })
const fillProject = ref(null)
const nodes = ref([])
const projTasks = ref([])
const saving = ref(false)
const progressEditVisible = ref(false)
const progressSaving = ref(false)
const fillForm = reactive({ progress_date: today, project_node_id: null, today_work: '', tomorrow_plan: '', risk: '', task_ids: [] })
const progressEditForm = reactive({ id: null, progress_date: '', node_name: '', today_work: '', tomorrow_plan: '', risk: '' })

const filledCount = computed(() => todo.projects.filter((p) => p.filled_today).length)

async function load() {
  const data = await myTodo()
  todo.projects = data.projects || []
  todo.tasks = data.tasks || []
  todo.recent_progress = data.recent_progress || []
}

async function openFill(p) {
  fillProject.value = p
  Object.assign(fillForm, { progress_date: today, project_node_id: p.current_node_id || null, today_work: '', tomorrow_plan: '', risk: '', task_ids: [] })
  nodes.value = await listNodes(p.id)
  projTasks.value = await listTasks(p.id, {})
}

async function submitFill() {
  if (!fillForm.today_work.trim()) {
    ElMessage.warning('请填写今日进展')
    return
  }
  saving.value = true
  try {
    await createProgress(fillProject.value.id, fillForm)
    ElMessage.success('已提交')
    fillProject.value = null
    await load()
  } finally {
    saving.value = false
  }
}

function openRecentEdit(progress) {
  Object.assign(progressEditForm, {
    id: progress.id,
    progress_date: progress.progress_date,
    node_name: progress.node_name,
    today_work: progress.today_work || '',
    tomorrow_plan: progress.tomorrow_plan || '',
    risk: progress.risk || '',
  })
  progressEditVisible.value = true
}

async function saveRecentEdit() {
  if (!progressEditForm.today_work.trim()) {
    ElMessage.warning('请填写今日进展')
    return
  }
  progressSaving.value = true
  try {
    await updateProgress(progressEditForm.id, {
      today_work: progressEditForm.today_work,
      tomorrow_plan: progressEditForm.tomorrow_plan,
      risk: progressEditForm.risk,
    })
    ElMessage.success('进展已更新')
    progressEditVisible.value = false
    await load()
  } finally {
    progressSaving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.card-title { font-weight: 700; font-size: 15px; }
.empty { color: var(--pm-text-3); text-align: center; padding: 24px 0; font-size: 13px; }
.todo-proj {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  padding: 11px 12px; border-radius: 10px; cursor: pointer;
  border: 1px solid var(--pm-border); background: #f7fafc; margin-bottom: 8px;
  transition: all .15s ease;
}
.todo-proj:last-of-type { margin-bottom: 0; }
.todo-proj:hover { border-color: var(--pm-primary-light); background: var(--pm-primary-lighter); transform: translateY(-1px); box-shadow: var(--pm-shadow); }
.tp-left { display: flex; align-items: flex-start; gap: 10px; min-width: 0; }
.tp-left .pm-dot { margin-top: 6px; }
.tp-name { font-weight: 600; font-size: 14px; }
.todo-task { display: flex; align-items: center; gap: 8px; padding: 9px 4px; border-bottom: 1px solid var(--pm-border); transition: background .12s; }
.todo-task:hover { background: var(--pm-primary-lighter); }
.todo-task:last-child { border-bottom: none; }
.tt-title { font-size: 14px; }
.recent-progress { padding: 10px 0; border-bottom: 1px solid var(--pm-border); }
.recent-progress:last-child { border-bottom: none; }
.recent-head { display: flex; align-items: center; justify-content: space-between; }
.recent-node { margin-top: 4px; }
.recent-work { font-size: 13px; line-height: 1.6; margin-top: 4px; white-space: pre-wrap; word-break: break-word; overflow-wrap: break-word; }
.risk { color: var(--pm-danger); font-size: 12px; margin-top: 3px; white-space: pre-wrap; word-break: break-word; }
.fill-placeholder { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 60px 24px; }
.fill-placeholder .card-title { margin-top: 14px; }
.fill-placeholder p { max-width: 380px; margin-top: 8px; line-height: 1.7; }
.fp-icon {
  width: 64px; height: 64px; border-radius: 50%;
  background: var(--pm-primary-lighter); border: 1px solid var(--pm-primary-light);
  color: var(--pm-primary); display: flex; align-items: center; justify-content: center;
}
</style>
