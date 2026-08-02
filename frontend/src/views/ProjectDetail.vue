<template>
  <div v-loading="loading">
    <!-- 头部卡片 -->
    <div v-if="project" class="pm-card head-card">
      <div class="pm-flex-between">
        <div>
          <div class="pname">
            {{ project.name }}
            <el-tag size="small" effect="plain" style="margin-left:8px">{{ project.machine_model || '无机型' }}</el-tag>
            <el-tag size="small" :type="healthTag(project.health)" style="margin-left:6px">{{ healthText(project.health) }}</el-tag>
          </div>
          <div class="pmeta">编号 {{ project.code }} ｜ 负责人 {{ ownerName }} ｜ {{ statusMap[project.status] }}</div>
        </div>
        <div class="pm-flex pm-gap">
          <div class="proj-comp">
            <div class="proj-comp-num">{{ projComp.percent }}<span class="pc-pct">%</span></div>
            <div class="proj-comp-label">项目完成度 {{ projComp.passed }}/{{ projComp.total }} 节点</div>
          </div>
          <el-button @click="openProjectEdit">编辑</el-button>
          <el-button @click="$router.back()">返回</el-button>
        </div>
      </div>

      <!-- TR 节点进度条 -->
      <el-steps :active="activeStep" align-center finish-status="success" class="steps">
        <el-step v-for="n in nodes" :key="n.id" :title="n.node_key" :description="nodeDesc(n)"
                 :status="stepStatus(n)" @click="selectNode(n)" class="step" :class="{ active: currentNode && currentNode.id === n.id }" />
      </el-steps>
      <el-alert v-if="overdueNodes.length" class="node-alert" type="warning" :closable="false" show-icon>
        {{ overdueNodes.length }} 个节点已超过计划完成日期，请及时更新节点进度。
      </el-alert>
    </div>

    <el-row :gutter="14" style="margin-top:14px">
      <!-- 左：节点任务 -->
      <el-col :span="15">
        <div class="pm-card">
          <div class="pm-flex-between" style="margin-bottom:12px">
            <span class="card-title">
              节点任务{{ currentNode ? `（${currentNode.node_key} ${currentNode.name}）` : '' }}
              <el-tag v-if="currentNode && currentNode.status === 'passed'" size="small" type="success" style="margin-left:6px">已通过</el-tag>
            </span>
            <div class="pm-flex pm-gap">
              <el-button size="small" @click="openReview" v-if="currentNode && canReview">评审</el-button>
              <el-button size="small" type="success" @click="onAdvance" v-if="currentNode && currentNode.status === 'passed' && !isLastNode">进入下一节点</el-button>
              <el-button size="small" type="success" plain @click="onCompleteNode"
                         v-if="currentNode && canEdit && currentNode.status !== 'passed'">完成节点</el-button>
              <el-button size="small" type="primary" @click="openTask()">新建任务</el-button>
            </div>
          </div>

          <!-- 节点完成度 -->
          <div v-if="currentNode" class="comp-bar">
            <span class="comp-label">任务完成度</span>
            <el-progress :percentage="nodeComp.percent" :stroke-width="10" style="flex:1"
                         :status="nodeComp.percent === 100 ? 'success' : ''" />
            <span class="comp-num">{{ nodeComp.done }}/{{ nodeComp.total }}</span>
          </div>

          <el-table :data="tasks" size="small" border>
            <el-table-column prop="title" label="任务" min-width="150" />
            <el-table-column label="指派人" width="80">
              <template #default="{ row }">{{ userName(row.assignee_id) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="86">
              <template #default="{ row }"><el-tag :type="taskTag(row)" size="small">{{ taskStatusText(row) }}</el-tag></template>
            </el-table-column>
            <el-table-column label="计划完成" width="104">
              <template #default="{ row }">{{ row.planned_end || '—' }}</template>
            </el-table-column>
            <el-table-column label="实际完成" width="104">
              <template #default="{ row }">{{ row.actual_end || '—' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="170" fixed="right">
              <template #default="{ row }">
                <el-button v-if="row.status==='todo'" link type="primary" @click="setStatus(row,'in_progress')">开始</el-button>
                <el-button v-if="row.status==='in_progress'" link type="success" @click="setStatus(row,'done')">完成</el-button>
                <el-button v-if="row.status==='done'" link @click="setStatus(row,'in_progress')">重做</el-button>
                <el-button link type="primary" @click="openTask(row)">编辑</el-button>
                <el-button link type="danger" @click="onDelTask(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!tasks.length" description="该节点暂无任务" :image-size="60" />

          <!-- 评审记录 -->
          <div v-if="reviews.length" class="review-sec">
            <div class="sec-h">评审记录</div>
            <div v-for="r in reviews" :key="r.id" class="review-item">
              <el-tag size="small" :type="reviewTag(r.conclusion)">{{ reviewText(r.conclusion) }}</el-tag>
              <span class="pm-sub">{{ r.review_date }}</span>
              <span>{{ r.comment }}</span>
            </div>
          </div>
        </div>
      </el-col>

      <!-- 右：周目标 + 进展 + 成员 -->
      <el-col :span="9">
        <div class="pm-card">
          <div class="pm-flex-between" style="margin-bottom:8px">
            <span class="card-title">本周目标</span>
            <el-button size="small" link type="primary" @click="goalVisible = true" v-if="canEdit">设定</el-button>
          </div>
          <div v-if="weeklyGoal" class="goal-text">{{ weeklyGoal }}</div>
          <div v-else class="empty">未设定本周目标</div>
        </div>

        <div class="pm-card" style="margin-top:14px">
          <div class="pm-flex-between" style="margin-bottom:8px">
            <span class="card-title">项目成员</span>
            <el-button size="small" link type="primary" @click="memberVisible = true" v-if="canEdit">添加</el-button>
          </div>
          <div v-for="m in members" :key="m.id" class="member-item">
            <span class="avatar-sm">{{ (m.display_name||'?').slice(0,1) }}</span>
            <span class="m-name">{{ m.display_name }}</span>
            <el-tag size="small" effect="plain">{{ m.project_role || '成员' }}</el-tag>
            <el-tag size="small" :type="m.is_invested ? 'success' : 'info'" effect="plain">{{ m.is_invested ? '投入' : '未投入' }}</el-tag>
          </div>
        </div>

        <div class="pm-card" style="margin-top:14px">
          <div class="card-title" style="margin-bottom:8px">进展时间线</div>
          <el-timeline v-if="progressList.length" class="ptl">
            <el-timeline-item v-for="p in progressList" :key="p.id" :timestamp="`${p.progress_date} · ${p.author_name}`" placement="top">
              <div class="progress-head">
                <div class="pl-work">{{ p.today_work }}</div>
                <el-button v-if="canEditProgress(p)" link type="primary" size="small" @click="openProgressEdit(p)">编辑</el-button>
              </div>
              <div v-if="p.tomorrow_plan" class="pm-sub progress-plan">明日：{{ p.tomorrow_plan }}</div>
              <div v-if="p.risk" class="risk">⚠ {{ p.risk }}</div>
            </el-timeline-item>
          </el-timeline>
          <div v-else class="empty">暂无进展</div>
        </div>
      </el-col>
    </el-row>

    <!-- 任务弹窗 -->
    <el-dialog v-model="taskVisible" :title="taskForm.id ? '编辑任务' : '新建任务'" width="480px">
      <el-form :model="taskForm" label-width="80px">
        <el-form-item label="任务" required><el-input v-model="taskForm.title" /></el-form-item>
        <el-form-item label="指派人">
          <el-select v-model="taskForm.assignee_id" clearable filterable style="width:100%">
            <el-option v-for="m in members" :key="m.user_id" :label="m.display_name" :value="m.user_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="计划开始"><el-date-picker v-model="taskForm.planned_start" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
        <el-form-item label="计划完成"><el-date-picker v-model="taskForm.planned_end" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="taskForm.description" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="taskVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTask">保存</el-button>
      </template>
    </el-dialog>

    <!-- 评审弹窗 -->
    <el-dialog v-model="reviewVisible" title="节点评审" width="440px">
      <el-form label-width="80px">
        <el-form-item label="节点"><b>{{ currentNode?.node_key }} {{ currentNode?.name }}</b></el-form-item>
        <el-form-item label="结论">
          <el-radio-group v-model="reviewForm.conclusion">
            <el-radio-button value="pass">通过</el-radio-button>
            <el-radio-button value="conditional_pass">有条件通过</el-radio-button>
            <el-radio-button value="fail">不通过</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="意见">
          <el-input v-model="reviewForm.comment" type="textarea" :rows="3" placeholder="评审意见 / 遗留问题" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reviewVisible = false">取消</el-button>
        <el-button type="primary" @click="saveReview">提交评审</el-button>
      </template>
    </el-dialog>

    <!-- 周目标弹窗 -->
    <el-dialog v-model="goalVisible" title="设定本周目标" width="440px">
      <el-input v-model="goalText" type="textarea" :rows="3" placeholder="本周项目目标" />
      <template #footer>
        <el-button @click="goalVisible = false">取消</el-button>
        <el-button type="primary" @click="saveGoal">保存</el-button>
      </template>
    </el-dialog>

    <!-- 添加成员弹窗 -->
    <el-dialog v-model="memberVisible" title="添加成员" width="420px">
      <el-form label-width="80px">
        <el-form-item label="成员">
          <el-select v-model="memberForm.user_id" filterable style="width:100%">
            <el-option v-for="u in candidateUsers" :key="u.id" :label="u.display_name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目角色"><el-input v-model="memberForm.project_role" placeholder="开发/测试/…" /></el-form-item>
        <el-form-item label="是否投入"><el-switch v-model="memberForm.is_invested" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="memberVisible = false">取消</el-button>
        <el-button type="primary" @click="saveMember">添加</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="progressVisible" title="编辑进展" width="520px">
      <el-form :model="progressForm" label-width="80px">
        <el-form-item label="日期"><span>{{ progressForm.progress_date }}</span></el-form-item>
        <el-form-item label="所属节点"><span>{{ progressForm.node_name || '项目级' }}</span></el-form-item>
        <el-form-item label="今日进展" required>
          <el-input v-model="progressForm.today_work" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="明日计划">
          <el-input v-model="progressForm.tomorrow_plan" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="风险问题">
          <el-input v-model="progressForm.risk" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="progressVisible = false">取消</el-button>
        <el-button type="primary" :loading="progressSaving" @click="saveProgressEdit">保存</el-button>
      </template>
    </el-dialog>

    <ProjectForm ref="editFormRef" @saved="loadAll" />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  addMember, addReview, createTask, deleteTask, getProject, getWeeklyGoal, listMembers, listProgress,
  listReviews, listTasks, listUserOptions, nodeAdvance, nodeComplete, nodeCompletion, projectCompletion,
  removeMember, setTaskStatus, setWeeklyGoal, updateProgress, updateTask,
} from '../api'
import { useUserStore } from '../store/user'
import ProjectForm from '../components/ProjectForm.vue'

const route = useRoute()
const store = useUserStore()
const pid = Number(route.params.id)

const loading = ref(false)
const project = ref(null)
const nodes = ref([])
const tasks = ref([])
const members = ref([])
const users = ref([])
const currentNode = ref(null)
const reviews = ref([])
const progressList = ref([])
const progressVisible = ref(false)
const progressSaving = ref(false)
const progressForm = reactive({ id: null, progress_date: '', node_name: '', today_work: '', tomorrow_plan: '', risk: '' })
const weeklyGoal = ref('')
const nodeComp = ref({ total: 0, done: 0, percent: 100 })
const projComp = ref({ total: 0, passed: 0, percent: 0 })

const statusMap = { not_started: '未开始', in_progress: '进行中', suspended: '暂停', completed: '已完成', archived: '已归档' }
const taskVisible = ref(false)
const taskForm = reactive({ id: null, title: '', assignee_id: null, planned_start: null, planned_end: null, description: '' })
const memberVisible = ref(false)
const memberForm = reactive({ user_id: null, project_role: '', is_invested: true })
const reviewVisible = ref(false)
const reviewForm = reactive({ conclusion: 'pass', comment: '' })
const goalVisible = ref(false)
const goalText = ref('')
const editFormRef = ref()

const ownerName = computed(() => userName(project.value?.owner_id))
const activeStep = computed(() => nodes.value.filter((n) => n.status === 'passed').length)
const overdueNodes = computed(() => nodes.value.filter((n) => n.overdue))
const candidateUsers = computed(() => users.value.filter((u) => !members.value.some((m) => m.user_id === u.id)))
const isLastNode = computed(() => currentNode.value && nodes.value.length && currentNode.value.sequence === Math.max(...nodes.value.map((n) => n.sequence)))
const canEdit = computed(() => store.isAdmin || project.value?.owner_id === store.userInfo?.id)
const canReview = computed(() => canEdit.value && currentNode.value && ['in_progress', 'pending_review'].includes(currentNode.value.status))

function userName(id) { return users.value.find((u) => u.id === id)?.display_name || (id ? `#${id}` : '—') }
const healthTag = (h) => ({ on_track: 'success', at_risk: 'warning', delayed: 'danger' }[h] || 'info')
const healthText = (h) => ({ on_track: '正常', at_risk: '风险', delayed: '延期' }[h] || h)
const reviewTag = (c) => ({ pass: 'success', conditional_pass: 'warning', fail: 'danger' }[c])
const reviewText = (c) => ({ pass: '通过', conditional_pass: '有条件通过', fail: '不通过' }[c])

function stepStatus(n) {
  if (n.status === 'passed') return 'success'
  if (['in_progress', 'pending_review'].includes(n.status)) return 'process'
  if (n.status === 'failed') return 'error'
  return 'wait'
}
function nodeDesc(n) {
  return n.planned_end ? `${n.name} · 计划至 ${n.planned_end}` : n.name
}
function taskTag(row) { if (row.status === 'done') return 'success'; if (row.overdue) return 'danger'; if (row.status === 'in_progress') return 'primary'; return 'info' }
function taskStatusText(row) { if (row.status === 'done') return '已完成'; if (row.overdue) return '延期'; return row.status === 'in_progress' ? '进行中' : '未开始' }

async function loadAll() {
  loading.value = true
  try {
    project.value = await getProject(pid)
    nodes.value = project.value.nodes || []
    members.value = await listMembers(pid)
    if (!users.value.length) users.value = await listUserOptions()
    if (!currentNode.value && nodes.value.length) {
      currentNode.value = nodes.value.find((n) => n.id === project.value.current_node_id) || nodes.value[0]
    }
    await Promise.all([loadTasks(), loadProgress(), loadGoal(), loadProjComp()])
  } finally { loading.value = false }
}

async function loadTasks() {
  if (!currentNode.value) { tasks.value = []; return }
  tasks.value = await listTasks(pid, { node_id: currentNode.value.id })
  reviews.value = await listReviews(currentNode.value.id).catch(() => [])
  nodeComp.value = await nodeCompletion(currentNode.value.id).catch(() => ({ total: 0, done: 0, percent: 100 }))
}
async function loadProgress() { progressList.value = (await listProgress(pid, {})).slice(0, 20) }
async function loadProjComp() { projComp.value = await projectCompletion(pid).catch(() => ({ total: 0, passed: 0, percent: 0 })) }
async function loadGoal() {
  const g = await getWeeklyGoal(pid, new Date().toISOString().slice(0, 10))
  weeklyGoal.value = g.goal || ''
  goalText.value = g.goal || ''
}

function selectNode(n) { currentNode.value = n; loadTasks() }

function canEditProgress(progress) {
  return store.isAdmin || progress.author_id === store.userInfo?.id
}

function openProgressEdit(progress) {
  Object.assign(progressForm, {
    id: progress.id,
    progress_date: progress.progress_date,
    node_name: progress.node_name,
    today_work: progress.today_work || '',
    tomorrow_plan: progress.tomorrow_plan || '',
    risk: progress.risk || '',
  })
  progressVisible.value = true
}

async function saveProgressEdit() {
  if (!progressForm.today_work.trim()) {
    ElMessage.warning('请填写今日进展')
    return
  }
  progressSaving.value = true
  try {
    await updateProgress(progressForm.id, {
      today_work: progressForm.today_work,
      tomorrow_plan: progressForm.tomorrow_plan,
      risk: progressForm.risk,
    })
    ElMessage.success('进展已更新')
    progressVisible.value = false
    await loadProgress()
  } finally {
    progressSaving.value = false
  }
}

async function onCompleteNode() {
  await ElMessageBox.confirm(
    `确认将节点「${currentNode.value.node_key} ${currentNode.value.name}」标记为已完成？` +
    (nodeComp.value.percent < 100 ? `（当前任务完成 ${nodeComp.value.done}/${nodeComp.value.total}）` : ''),
    '完成节点', { type: 'success', confirmButtonText: '完成节点', cancelButtonText: '取消' })
  await nodeComplete(currentNode.value.id)
  ElMessage.success('节点已完成')
  loadAll()
}

function openTask(row) {
  if (row) Object.assign(taskForm, { id: row.id, title: row.title, assignee_id: row.assignee_id, planned_start: row.planned_start, planned_end: row.planned_end, description: row.description })
  else Object.assign(taskForm, { id: null, title: '', assignee_id: null, planned_start: null, planned_end: null, description: '' })
  taskVisible.value = true
}
async function saveTask() {
  if (!taskForm.title) { ElMessage.warning('请输入任务'); return }
  if (taskForm.id) await updateTask(taskForm.id, taskForm)
  else await createTask(currentNode.value.id, taskForm)
  ElMessage.success('已保存'); taskVisible.value = false; loadTasks()
}
async function setStatus(row, status) { await setTaskStatus(row.id, status); loadTasks() }
async function onDelTask(row) {
  await ElMessageBox.confirm(`删除任务「${row.title}」？`, '提示', { type: 'warning' })
  await deleteTask(row.id); ElMessage.success('已删除'); loadTasks()
}

function openReview() { reviewForm.conclusion = 'pass'; reviewForm.comment = ''; reviewVisible.value = true }
async function saveReview() {
  await addReview(currentNode.value.id, reviewForm)
  ElMessage.success('评审已提交'); reviewVisible.value = false; loadAll()
}
async function onAdvance() {
  try {
    await nodeAdvance(currentNode.value.id)
    ElMessage.success('已进入下一节点'); loadAll()
  } catch (e) { /* 拦截器提示（如整改未闭环） */ }
}

async function saveGoal() {
  await setWeeklyGoal(pid, { week_start: new Date().toISOString().slice(0, 10), goal: goalText.value })
  ElMessage.success('已保存'); goalVisible.value = false; loadGoal()
}

async function saveMember() {
  if (!memberForm.user_id) { ElMessage.warning('请选择成员'); return }
  await addMember(pid, memberForm)
  ElMessage.success('已添加'); memberVisible.value = false
  Object.assign(memberForm, { user_id: null, project_role: '', is_invested: true })
  members.value = await listMembers(pid)
}
async function onRemoveMember(row) {
  await ElMessageBox.confirm(`移除成员「${row.display_name}」？`, '提示', { type: 'warning' })
  await removeMember(pid, row.id); members.value = await listMembers(pid)
}

async function openProjectEdit() {
  if (project.value && editFormRef.value) await editFormRef.value.open(project.value)
}

onMounted(loadAll)
</script>

<style scoped>
.head-card { padding-top: 20px; }
.pname { font-size: 20px; font-weight: 800; display: flex; align-items: center; }
.pmeta { color: var(--pm-text-3); margin-top: 8px; font-size: 13px; }
.steps { margin-top: 22px; }
.node-alert { margin-top: 14px; }
.step { cursor: pointer; }
.step.active :deep(.el-step__title) { color: var(--pm-primary); font-weight: 700; }
.card-title { font-weight: 700; font-size: 15px; display: flex; align-items: center; }
.review-sec { margin-top: 14px; border-top: 1px solid var(--pm-border); padding-top: 10px; }
.sec-h { font-weight: 700; font-size: 13px; color: var(--pm-text-2); margin-bottom: 8px; }
.review-item { display: flex; align-items: center; gap: 8px; font-size: 13px; margin-bottom: 6px; }
.goal-text { font-size: 14px; line-height: 1.6; }
.empty { color: var(--pm-text-3); font-size: 13px; padding: 8px 0; }
.member-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid var(--pm-border); }
.member-item:last-child { border-bottom: none; }
.avatar-sm { width: 26px; height: 26px; border-radius: 50%; background: var(--pm-gradient); color: #fff; font-size: 12px; display: flex; align-items: center; justify-content: center; font-weight: 700; }
.m-name { font-size: 14px; font-weight: 600; }
.ptl { max-height: 320px; overflow-y: auto; }
.pl-work { font-size: 13px; }
.progress-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.progress-plan { margin-top: 4px; }
.risk { color: var(--pm-danger); font-size: 12px; }
.comp-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; padding: 8px 12px; background: #f7f9fc; border-radius: 8px; }
.comp-label { font-size: 12px; color: var(--pm-text-2); white-space: nowrap; }
.comp-num { font-size: 12px; color: var(--pm-text-2); font-weight: 700; white-space: nowrap; }
.proj-comp { text-align: center; padding-right: 14px; margin-right: 4px; border-right: 1px solid var(--pm-border); }
.proj-comp-num { font-size: 26px; font-weight: 800; color: var(--pm-primary); line-height: 1; }
.pc-pct { font-size: 14px; }
.proj-comp-label { font-size: 11px; color: var(--pm-text-3); margin-top: 4px; white-space: nowrap; }
</style>
