<template>
  <div>
    <div class="pm-toolbar">
      <span class="pm-page-title">工作台</span>
      <span class="pm-sub">{{ today }}</span>
    </div>

    <el-row :gutter="16">
      <!-- 待填报 -->
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
                <div class="pm-sub">{{ p.code }}</div>
              </div>
            </div>
            <el-tag size="small" :type="p.filled_today ? 'success' : 'warning'" effect="plain">
              {{ p.filled_today ? '已填报' : '待填报' }}
            </el-tag>
          </div>
        </div>

        <!-- 我的任务 -->
        <div class="pm-card" style="margin-top:16px">
          <div class="card-title" style="margin-bottom:12px">我的待办任务</div>
          <div v-if="!todo.tasks.length" class="empty">暂无待办任务</div>
          <div v-for="t in todo.tasks" :key="t.id" class="todo-task">
            <span class="pm-dot" :class="t.overdue ? 'danger' : (t.status==='in_progress' ? 'primary' : 'info')"></span>
            <span class="tt-title">{{ t.title }}</span>
            <span class="pm-sub" style="margin-left:auto">{{ t.planned_end || '' }}</span>
          </div>
        </div>
      </el-col>

      <!-- 填报表单 / 时间线 -->
      <el-col :span="14">
        <div class="pm-card" v-if="fillProject">
          <div class="card-title" style="margin-bottom:14px">填报进展 · {{ fillProject.name }}</div>
          <el-form label-width="80px">
            <el-form-item label="日期">
              <el-date-picker v-model="fillForm.progress_date" type="date" value-format="YYYY-MM-DD" style="width:160px" />
            </el-form-item>
            <el-form-item label="所属节点">
              <el-select v-model="fillForm.project_node_id" clearable placeholder="项目级（默认）" style="width:220px">
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

        <div class="pm-card" v-else>
          <div class="card-title" style="margin-bottom:12px">填报说明</div>
          <p class="pm-sub">从左侧选择一个项目开始填报今日进展。进展会自动汇总到项目周报与周会视图。</p>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createProgress, listNodes, listTasks, myTodo } from '../api'

const today = new Date().toISOString().slice(0, 10)
const todo = reactive({ projects: [], tasks: [] })
const fillProject = ref(null)
const nodes = ref([])
const projTasks = ref([])
const saving = ref(false)
const fillForm = reactive({ progress_date: today, project_node_id: null, today_work: '', tomorrow_plan: '', risk: '', task_ids: [] })

const filledCount = computed(() => todo.projects.filter((p) => p.filled_today).length)

async function load() {
  const data = await myTodo()
  todo.projects = data.projects
  todo.tasks = data.tasks
}

async function openFill(p) {
  fillProject.value = p
  Object.assign(fillForm, { progress_date: today, project_node_id: null, today_work: '', tomorrow_plan: '', risk: '', task_ids: [] })
  nodes.value = await listNodes(p.id)
  projTasks.value = await listTasks(p.id, {})
}

async function submitFill() {
  if (!fillForm.today_work) { ElMessage.warning('请填写今日进展'); return }
  saving.value = true
  try {
    await createProgress(fillProject.value.id, fillForm)
    ElMessage.success('已提交')
    fillProject.value = null
    load()
  } finally { saving.value = false }
}

onMounted(load)
</script>

<style scoped>
.card-title { font-weight: 700; font-size: 15px; }
.empty { color: var(--pm-text-3); text-align: center; padding: 24px 0; font-size: 13px; }
.todo-proj { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; border-radius: 8px; cursor: pointer; transition: background .12s; }
.todo-proj:hover { background: var(--pm-primary-light); }
.tp-left { display: flex; align-items: center; gap: 8px; }
.tp-name { font-weight: 600; font-size: 14px; }
.todo-task { display: flex; align-items: center; gap: 8px; padding: 8px 4px; border-bottom: 1px solid var(--pm-border); }
.todo-task:last-child { border-bottom: none; }
.tt-title { font-size: 14px; }
</style>
