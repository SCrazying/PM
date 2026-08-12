<template>
  <div v-loading="loading">
    <!-- 头部卡片 -->
    <div v-if="project" class="pm-card head-card">
      <div class="pm-flex-between head-top">
        <div class="head-left">
          <div class="pname">
            {{ project.name }}
            <span class="status-chip" :class="'st-' + project.status" style="margin-left:10px">{{ statusMap[project.status] }}</span>
            <el-tag size="small" effect="plain" style="margin-left:8px">{{ project.machine_model || '无机型' }}</el-tag>
          </div>
          <div class="pmeta">编号 {{ project.code }}<span class="pmeta-sep">·</span>负责人 {{ ownerName }}</div>
        </div>
        <div class="pm-flex pm-gap">
          <div class="proj-comp">
            <div class="proj-comp-num">{{ projComp.percent }}<span class="pc-pct">%</span></div>
            <div class="proj-comp-label">完成度 {{ projComp.passed }}/{{ projComp.total }} 节点</div>
            <div class="proj-comp-track"><div class="proj-comp-fill" :style="{ width: projComp.percent + '%' }"></div></div>
          </div>
          <div class="head-actions">
            <el-button @click="openProjectEdit">编辑</el-button>
            <el-button @click="$router.back()">返回</el-button>
          </div>
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

          <!-- M6 子节点 -->
          <div v-if="currentNode" class="subnode-box">
            <div class="pm-flex-between" style="margin-bottom:8px">
              <span class="subnode-title">子节点
                <el-tag v-if="subnodes.length && subnodes.filter(s=>s.status==='done').length===subnodes.length"
                        size="small" type="success" style="margin-left:6px">子项全部完成</el-tag>
              </span>
              <el-button size="small" link type="primary" @click="openSubnode()" v-if="canEdit">+ 添加子节点</el-button>
            </div>
            <div v-if="!subnodes.length" class="empty subnode-empty">暂无子节点</div>
            <div v-for="s in subnodes" :key="s.id" class="subnode-row" :class="{ done: s.status==='done' }">
              <el-checkbox :model-value="s.status==='done'" @change="() => onToggleSubnode(s)">
                <span class="sn-name">{{ s.name }}</span>
              </el-checkbox>
              <el-tag v-if="s.status==='done'" size="small" type="success">已完成 {{ s.actual_end }}</el-tag>
              <el-tag v-else-if="s.overdue" size="small" type="danger">已延期</el-tag>
              <el-tag v-else-if="s.planned_end" size="small" effect="plain">{{ s.planned_end }}</el-tag>
              <el-tag v-else size="small" effect="plain">未设截止</el-tag>
              <span class="sn-ops" v-if="canEdit">
                <el-button link size="small" type="primary" @click="openSubnode(s)">编辑</el-button>
                <el-button link size="small" type="danger" @click="onDelSubnode(s)">删除</el-button>
              </span>
            </div>
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
            <span class="card-title">周目标
              <el-date-picker v-model="goalWeek" type="week" format="YYYY 第 ww 周" value-format="YYYY-MM-DD"
                              :first-day-of-week="1" style="width:165px; margin-left:8px; vertical-align: middle" @change="loadGoal" />
              <el-tag v-if="goalItems.length && goalItems.filter(g=>g.done).length===goalItems.length" size="small" type="success" style="margin-left:6px">全部完成</el-tag>
            </span>
            <el-button size="small" link type="primary" @click="openGoalItem()" v-if="canEdit">+ 添加</el-button>
          </div>
          <div v-if="goalItems.length" class="goal-items">
            <div v-for="g in goalItems" :key="g.id" class="goal-item" :class="{ done: g.done }" @click="onToggleGoalItem(g)"
                 :title="`${g.goal}（点击切换完成）`">
              <el-icon :size="13"><Select v-if="g.done" /><CircleCheck v-else /></el-icon>
              <span v-if="g.user_name" class="gi-owner">{{ g.user_name }}</span>
              <span class="gi-goal">{{ g.goal }}</span>
              <span v-if="g.done" class="gi-date">{{ g.done_at }}</span>
              <span v-else-if="g.overdue" class="gi-date gi-overdue">超期 {{ g.deadline }}</span>
              <span v-else-if="g.deadline" class="gi-date">{{ g.deadline }}</span>
              <span v-if="canEdit" class="gi-ops" @click.stop>
                <el-button link size="small" type="primary" @click="openGoalItem(g)">编</el-button>
                <el-button link size="small" type="danger" @click="onDelGoalItem(g)">删</el-button>
              </span>
            </div>
          </div>
          <div v-else-if="legacyGoal" class="goal-cell">{{ legacyGoal }}</div>
          <div v-else class="empty">该周未设定目标</div>
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

        <ProjectFiles :project-id="pid" :owner-id="project?.owner_id" />

        <div class="pm-card" style="margin-top:14px">
          <div class="pm-flex-between" style="margin-bottom:8px">
            <span class="card-title">风险管理
              <el-tag v-if="openRiskCount" size="small" type="warning" effect="plain" style="margin-left:6px">{{ openRiskCount }} 未解决</el-tag>
            </span>
            <el-button v-if="canEdit" size="small" link type="primary" @click="openRiskAdd">+ 添加</el-button>
          </div>
          <div v-if="risks.length" class="risk-list">
            <div v-for="r in risks" :key="r.key" class="risk-item" :class="{ resolved: r.resolved }"
                 @click="onToggleRisk(r)" :title="r.resolved ? '点击重新打开风险' : '点击关闭风险'">
              <el-icon :size="14" class="risk-ico"><CircleCheckFilled v-if="r.resolved" /><WarningFilled v-else /></el-icon>
              <div class="risk-body">
                <div class="risk-txt">{{ r.risk }}</div>
                <div class="risk-meta">[{{ r.date }}] {{ r.author }}</div>
              </div>
              <span class="risk-ops" @click.stop>
                <el-tag v-if="r.resolved" size="small" type="success" effect="plain">已解决</el-tag>
                <el-button v-if="r.can_delete && canEdit" link size="small" type="danger" @click="onDeleteRisk(r)">删</el-button>
              </span>
            </div>
          </div>
          <div v-else class="empty">暂无风险</div>
        </div>

        <el-dialog v-model="riskVisible" title="添加风险" width="580px" :close-on-click-modal="false">
          <el-form label-width="70px">
            <el-form-item label="风险" required>
              <el-input v-model="riskForm.risk" type="textarea" :rows="3" placeholder="描述当前风险/阻塞（可在进展中随时关闭）" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="riskVisible = false">取消</el-button>
            <el-button type="primary" :loading="riskSaving" @click="saveRisk">保存</el-button>
          </template>
        </el-dialog>

        <div class="pm-card" style="margin-top:14px">
          <div class="card-title" style="margin-bottom:8px">进展时间线</div>
          <el-timeline v-if="progressList.length" class="ptl">
            <el-timeline-item v-for="p in progressList" :key="p.id" :timestamp="`${p.progress_date} · ${p.author_name}`" placement="top">
              <div class="progress-head">
                <div class="pl-work">{{ p.today_work }}</div>
                <el-button v-if="canEditProgress(p)" link type="primary" size="small" @click="openProgressEdit(p)">编辑</el-button>
              </div>
            </el-timeline-item>
          </el-timeline>
          <div v-else class="empty">暂无进展</div>
        </div>

        <div class="pm-card" style="margin-top:14px">
          <div class="pm-flex-between" style="margin-bottom:8px">
            <span class="card-title">操作流水</span>
            <el-button v-if="activity.list.length < activity.total" size="small" link type="primary" :loading="activity.loading" @click="loadMoreActivity">加载更多</el-button>
          </div>
          <el-timeline v-if="activity.list.length" class="actl">
            <el-timeline-item v-for="a in activity.list" :key="a.id" :timestamp="fmtActTime(a.time)" placement="top" :type="actTag(a.action)">
              <div class="act-row">
                <span class="act-actor">{{ a.actor_name }}</span>
                <el-tag size="small" effect="plain" :type="actTag(a.action)">{{ a.action_label }}{{ a.target_label }}</el-tag>
                <div class="act-summary">{{ a.summary }}</div>
              </div>
            </el-timeline-item>
          </el-timeline>
          <div v-else class="empty">暂无操作记录</div>
        </div>
      </el-col>
    </el-row>

    <!-- 任务弹窗 -->
    <el-dialog v-model="taskVisible" :title="taskForm.id ? '编辑任务' : '新建任务'" width="680px" :close-on-click-modal="false">
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

    <!-- 子节点弹窗 -->
    <el-dialog v-model="subnodeVisible" :title="subnodeForm.id ? '编辑子节点' : '添加子节点'" width="600px" :close-on-click-modal="false">
      <el-form :model="subnodeForm" label-width="80px">
        <el-form-item label="名称" required><el-input v-model="subnodeForm.name" placeholder="子节点名称" /></el-form-item>
        <el-form-item label="截止时间">
          <el-date-picker v-model="subnodeForm.planned_end" type="date" value-format="YYYY-MM-DD" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="subnodeVisible = false">取消</el-button>
        <el-button type="primary" @click="saveSubnode">保存</el-button>
      </template>
    </el-dialog>

    <!-- 评审弹窗 -->
    <el-dialog v-model="reviewVisible" title="节点评审" width="660px" :close-on-click-modal="false">
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

    <!-- 周目标条目弹窗 -->
    <el-dialog v-model="goalVisible" :title="goalForm.id ? '编辑目标条目' : '添加目标条目'" width="660px" :close-on-click-modal="false">
      <el-form label-width="80px">
        <el-form-item label="目标" required>
          <el-input v-model="goalForm.goal" type="textarea" :rows="2" placeholder="本周目标条目" />
        </el-form-item>
        <el-form-item label="归属周次">
          <el-select v-model="goalForm.weekStart" filterable style="width:100%">
            <el-option v-for="w in weekOptions" :key="w.value" :label="w.label" :value="w.value" />
          </el-select>
          <span class="pm-sub" style="margin-top:4px">可调整目标所在周（含前几周，修正填错的周次）</span>
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="goalForm.user_id" clearable filterable placeholder="选择项目成员（可不选）" style="width:100%">
            <el-option v-for="m in members" :key="m.user_id" :label="m.display_name" :value="m.user_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="截止时间">
          <el-date-picker v-model="goalForm.deadline" type="date" value-format="YYYY-MM-DD" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="goalVisible = false">取消</el-button>
        <el-button type="primary" @click="saveGoal">保存</el-button>
      </template>
    </el-dialog>

    <!-- 添加成员弹窗 -->
    <el-dialog v-model="memberVisible" title="添加成员" width="600px" :close-on-click-modal="false">
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

    <el-dialog v-model="progressVisible" title="编辑进展" width="740px" :close-on-click-modal="false">
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
  addMember, addReview, addSubnode, addWeeklyGoalItem, createTask, deleteSubnode, deleteTask,
  deleteWeeklyGoalItem, addProjectRisk, deleteProjectRisk, getProject, getProjectActivity, getReportWeeks,
  listMembers, listProgress, listProjectRisks, listReviews, listTasks,
  listUserOptions, nodeAdvance, nodeComplete, nodeCompletion, projectCompletion,
  projectWeekly, removeMember, setProgressRiskResolved, setProjectRiskResolved, setSubnodeStatus, setTaskStatus, setWeeklyGoalItemDone,
  updateProgress, updateSubnode, updateTask, updateWeeklyGoalItem,
} from '../api'
import { useUserStore } from '../store/user'
import ProjectForm from '../components/ProjectForm.vue'
import ProjectFiles from '../components/ProjectFiles.vue'
import { buildWeekOptions, fmtDate, mergeWeekOptions, mondayOf, thisWeekStart } from '../utils/date'

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
const risks = ref([])
const openRiskCount = computed(() => risks.value.filter((r) => !r.resolved).length)
const riskVisible = ref(false)
const riskSaving = ref(false)
const riskForm = reactive({ risk: '' })
const progressVisible = ref(false)
const progressSaving = ref(false)
const progressForm = reactive({ id: null, progress_date: '', node_name: '', today_work: '', tomorrow_plan: '', risk: '' })
const weeklyGoal = ref('')
const goalItems = ref([])
const nodeComp = ref({ total: 0, done: 0, percent: 100 })
const projComp = ref({ total: 0, passed: 0, percent: 0 })
const subnodes = ref([])
const subnodeVisible = ref(false)
const subnodeForm = reactive({ id: null, name: '', planned_end: null })
// 操作流水（V1.0.5）
const activity = reactive({ list: [], total: 0, page: 1, loading: false })

const statusMap = { not_started: '未开始', in_progress: '进行中', delayed: '延期', suspended: '暂停', completed: '已完成' }
const taskVisible = ref(false)
const taskForm = reactive({ id: null, title: '', assignee_id: null, planned_start: null, planned_end: null, description: '' })
const memberVisible = ref(false)
const memberForm = reactive({ user_id: null, project_role: '', is_invested: true })
const reviewVisible = ref(false)
const reviewForm = reactive({ conclusion: 'pass', comment: '' })
const goalVisible = ref(false)
const goalForm = reactive({ id: null, goal: '', deadline: null, user_id: null, weekStart: null })
// 周目标查看周（date-picker 日历选周；value 规整到周一，与后端周一口径一致）
const goalWeekRaw = ref(thisWeekStart())
const goalWeek = computed({
  get: () => goalWeekRaw.value,
  set: (v) => { goalWeekRaw.value = v ? fmtDate(mondayOf(v)) : v },
})
const goalWeekStart = computed(() => goalWeek.value)
// 周次下拉选项：前 12 周 ~ 未来 12 周（含本周），编辑时可下拉调整归属周次（修正填错的周）
const weekOptions = ref(buildWeekOptions())
function ensureWeekOption(ws) {
  if (ws && !weekOptions.value.some((o) => o.value === ws)) {
    const m = mondayOf(ws); const e = new Date(m); e.setDate(e.getDate() + 6)
    weekOptions.value.push({ value: fmtDate(m), label: `${fmtDate(m).slice(5)}~${fmtDate(e).slice(5)}` })
  }
}
const editFormRef = ref()

const ownerName = computed(() => userName(project.value?.owner_id))
const activeStep = computed(() => nodes.value.filter((n) => n.status === 'passed').length)
const overdueNodes = computed(() => nodes.value.filter((n) => n.overdue))
const candidateUsers = computed(() => users.value.filter((u) => !members.value.some((m) => m.user_id === u.id)))
const isLastNode = computed(() => currentNode.value && nodes.value.length && currentNode.value.sequence === Math.max(...nodes.value.map((n) => n.sequence)))
const canEdit = computed(() => store.isAdmin || project.value?.owner_id === store.userInfo?.id)
const canReview = computed(() => canEdit.value && currentNode.value && ['in_progress', 'pending_review'].includes(currentNode.value.status))

function userName(id) { return users.value.find((u) => u.id === id)?.display_name || (id ? `#${id}` : '—') }
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
    // 展示仅用启用节点（详情返回全部含停用，供编辑弹窗勾选恢复）
    nodes.value = (project.value.nodes || []).filter((n) => !n.is_deleted)
    members.value = await listMembers(pid)
    if (!users.value.length) users.value = await listUserOptions()
    if (!currentNode.value && nodes.value.length) {
      currentNode.value = nodes.value.find((n) => n.id === project.value.current_node_id) || nodes.value[0]
    }
    await Promise.all([loadTasks(), loadProgress(), loadGoal(), loadProjComp(), loadRisks(), loadActivity()])
  } finally { loading.value = false }
}

// ---------- 操作流水（V1.0.5） ----------
function fmtActTime(t) { return t ? t.replace('T', ' ').slice(0, 19) : '—' }
const actTag = (a) => ({ create: 'success', update: 'primary', delete: 'danger', review: 'warning', restore: 'success', force_transition: 'warning' }[a] || 'info')
async function loadActivity() {
  if (activity.loading) return
  activity.loading = true
  try {
    const data = await getProjectActivity(pid, { page: activity.page, size: 20 })
    activity.list = activity.page === 1 ? data.list : activity.list.concat(data.list)
    activity.total = data.total
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '操作记录加载失败')
  } finally { activity.loading = false }
}
async function loadMoreActivity() {
  activity.page += 1
  await loadActivity()
}

async function loadTasks() {
  if (!currentNode.value) { tasks.value = []; return }
  tasks.value = await listTasks(pid, { node_id: currentNode.value.id })
  reviews.value = await listReviews(currentNode.value.id).catch(() => [])
  nodeComp.value = await nodeCompletion(currentNode.value.id).catch(() => ({ total: 0, done: 0, percent: 100 }))
  const cur = nodes.value.find((n) => n.id === currentNode.value.id)
  subnodes.value = cur?.subnodes || []
}
async function loadProgress() { progressList.value = (await listProgress(pid, {})).slice(0, 20) }

// ---------- 风险管理 ----------
async function loadRisks() {
  risks.value = await listProjectRisks(pid).catch(() => [])
}
function openRiskAdd() {
  riskForm.risk = ''
  riskVisible.value = true
}
async function saveRisk() {
  if (!riskForm.risk.trim()) { ElMessage.warning('请输入风险内容'); return }
  riskSaving.value = true
  try {
    await addProjectRisk(pid, { risk: riskForm.risk })
    ElMessage.success('已添加')
    riskVisible.value = false
    loadRisks()
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '添加失败')
  } finally {
    riskSaving.value = false
  }
}
async function onToggleRisk(r) {
  const target = !r.resolved
  try {
    if (r.source === 'risk') await setProjectRiskResolved(r.id, target)
    else await setProgressRiskResolved(r.id, target)
    r.resolved = target
    ElMessage.success(target ? '已关闭风险' : '已重新打开风险')
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '操作失败')
  }
}
async function onDeleteRisk(r) {
  try {
    await ElMessageBox.confirm(`确认删除风险「${r.risk.length > 20 ? r.risk.slice(0, 20) + '…' : r.risk}」？`, '删除确认', { type: 'warning', confirmButtonText: '删除' })
  } catch {
    return
  }
  try {
    await deleteProjectRisk(r.id)
    ElMessage.success('已删除')
    loadRisks()
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '删除失败')
  }
}
async function loadProjComp() { projComp.value = await projectCompletion(pid).catch(() => ({ total: 0, passed: 0, percent: 0 })) }
// 竞态守卫：快速切换本周/下周时，旧请求晚返回不覆盖新周数据
let goalLoadSeq = 0
const legacyGoal = ref('')  // 旧周目标文本（条目为空时回落显示，与周会视图一致）
async function loadGoal() {
  const seq = ++goalLoadSeq
  const ws = goalWeekStart.value
  // 与周会视图同一接口取周目标，保证两处显示一致
  const data = await projectWeekly(pid, ws).catch(() => null)
  if (seq === goalLoadSeq) {
    goalItems.value = data?.weekly_goal_items || []
    legacyGoal.value = data?.weekly_goal || ''
  }
}

// ---------- M7 周目标条目 ----------
function openGoalItem(g) {
  if (g) {
    Object.assign(goalForm, { id: g.id, goal: g.goal, deadline: g.deadline, user_id: g.user_id ?? null, weekStart: g.week_start })
    ensureWeekOption(g.week_start)  // 目标在历史周时补进下拉选项，便于修正
  } else {
    Object.assign(goalForm, { id: null, goal: '', deadline: null, user_id: null, weekStart: goalWeekStart.value })
  }
  goalVisible.value = true
}

async function saveGoal() {
  if (!goalForm.goal.trim()) { ElMessage.warning('请输入目标内容'); return }
  const payload = { goal: goalForm.goal, deadline: goalForm.deadline, user_id: goalForm.user_id || null }
  const ws = goalForm.weekStart || thisWeekStart()
  if (goalForm.id) await updateWeeklyGoalItem(goalForm.id, { ...payload, week_start: ws })
  else await addWeeklyGoalItem(pid, { week_start: ws, ...payload })
  ElMessage.success('已保存')
  goalVisible.value = false
  loadGoal()
}

async function onToggleGoalItem(g) {
  await setWeeklyGoalItemDone(g.id, !g.done)
  loadGoal()
}

async function onDelGoalItem(g) {
  await ElMessageBox.confirm(`删除目标条目「${g.goal}」？`, '提示', { type: 'warning' })
  await deleteWeeklyGoalItem(g.id)
  ElMessage.success('已删除')
  loadGoal()
}

function selectNode(n) { currentNode.value = n; loadTasks() }

// ---------- M6 子节点 ----------
function openSubnode(s) {
  if (s) Object.assign(subnodeForm, { id: s.id, name: s.name, planned_end: s.planned_end })
  else Object.assign(subnodeForm, { id: null, name: '', planned_end: null })
  subnodeVisible.value = true
}

async function saveSubnode() {
  if (!subnodeForm.name.trim()) { ElMessage.warning('请输入子节点名称'); return }
  if (subnodeForm.id) await updateSubnode(subnodeForm.id, subnodeForm)
  else await addSubnode(currentNode.value.id, subnodeForm)
  ElMessage.success('已保存')
  subnodeVisible.value = false
  loadAll()
}

async function onToggleSubnode(s) {
  await setSubnodeStatus(s.id, s.status === 'done' ? 'in_progress' : 'done')
  ElMessage.success(s.status === 'done' ? '已取消完成' : '子节点已完成')
  loadAll()
}

async function onDelSubnode(s) {
  await ElMessageBox.confirm(`删除子节点「${s.name}」？`, '提示', { type: 'warning' })
  await deleteSubnode(s.id)
  ElMessage.success('已删除')
  loadAll()
}

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

onMounted(async () => {
  try {
    // 并入所有有数据的周，超出固定范围的历史/未来周也能下拉选到
    weekOptions.value = mergeWeekOptions(weekOptions.value, await getReportWeeks())
  } catch { /* 保留固定范围 */ }
  loadAll()
})
</script>

<style scoped>
.head-card { padding: 20px 22px; }
.head-top { gap: 16px; flex-wrap: wrap; }
.head-left { min-width: 0; }
.pname { font-size: 22px; font-weight: 800; display: flex; align-items: center; flex-wrap: wrap; letter-spacing: .2px; }
.pmeta { color: var(--pm-text-3); margin-top: 10px; font-size: 13px; display: flex; align-items: center; }
.pmeta-sep { margin: 0 8px; color: var(--pm-border-strong); }
.steps { margin-top: 24px; }
.node-alert { margin-top: 14px; }
.step { cursor: pointer; }
.step.active :deep(.el-step__title) { color: var(--pm-primary); font-weight: 700; }
.head-actions { display: flex; gap: 10px; }
.proj-comp {
  text-align: center; padding: 6px 18px 10px;
  background: var(--pm-primary-lighter);
  border: 1px solid var(--pm-primary-light);
  border-radius: var(--pm-radius); min-width: 132px;
}
.proj-comp-num { font-size: 26px; font-weight: 800; color: var(--pm-primary); line-height: 1.1; }
.pc-pct { font-size: 14px; }
.proj-comp-label { font-size: 11px; color: var(--pm-text-2); margin-top: 3px; white-space: nowrap; }
.proj-comp-track { height: 4px; border-radius: 4px; background: #d3e9f5; margin-top: 8px; overflow: hidden; }
.proj-comp-fill { height: 100%; border-radius: 4px; background: var(--pm-gradient); transition: width .4s ease; }
.card-title { font-weight: 700; font-size: 15px; display: flex; align-items: center; }
.review-sec { margin-top: 14px; border-top: 1px solid var(--pm-border); padding-top: 10px; }
.sec-h { font-weight: 700; font-size: 13px; color: var(--pm-text-2); margin-bottom: 8px; }
.review-item { display: flex; align-items: center; gap: 8px; font-size: 13px; margin-bottom: 6px; }
.goal-text { font-size: 14px; line-height: 1.6; }
.goal-items { display: flex; flex-direction: column; gap: 3px; }
.goal-cell { white-space: pre-wrap; word-break: break-word; overflow-wrap: break-word; line-height: 1.5; color: var(--pm-text-2); font-size: 13px; }
.goal-item { display: flex; align-items: flex-start; gap: 6px; padding: 4px 8px; border-radius: 6px; cursor: pointer; font-size: 13px; line-height: 1.5; }
.goal-item:hover { background: var(--pm-primary-light); }
.goal-item.done { background: var(--pm-st-completed-bg); }
.goal-item.done .gi-goal { color: var(--pm-success); text-decoration: line-through; }
.goal-item .el-icon { flex-shrink: 0; height: 20px; display: inline-flex; align-items: center; color: var(--pm-primary); }
.goal-item.done .el-icon { color: var(--pm-success); }
.gi-goal { flex: 1; min-width: 0; white-space: pre-wrap; word-break: break-word; }
.gi-owner { color: var(--pm-primary); font-weight: 600; flex-shrink: 0; }
.gi-date { color: var(--pm-text-3); white-space: nowrap; flex-shrink: 0; }
.gi-overdue { color: var(--pm-danger); font-weight: 600; }
.gi-ops { display: flex; gap: 2px; flex-shrink: 0; }
.empty { color: var(--pm-text-3); font-size: 13px; padding: 8px 0; }
.risk-list { display: flex; flex-direction: column; gap: 5px; max-height: 260px; overflow-y: auto; }
.risk-item { display: flex; align-items: flex-start; gap: 8px; padding: 7px 9px; border-radius: 6px; cursor: pointer; background: var(--pm-st-delayed-bg); border: 1px solid transparent; }
.risk-item:hover { outline: 1px solid var(--pm-danger); }
.risk-item.resolved { background: var(--pm-st-completed-bg); }
.risk-ico { color: var(--pm-danger); flex-shrink: 0; margin-top: 2px; }
.risk-item.resolved .risk-ico { color: var(--pm-success); }
.risk-body { flex: 1; min-width: 0; }
.risk-txt { font-size: 12.5px; white-space: pre-wrap; word-break: break-word; }
.risk-item.resolved .risk-txt { color: var(--pm-text-3); text-decoration: line-through; }
.risk-meta { color: var(--pm-text-3); font-size: 11.5px; margin-top: 2px; }
.risk-ops { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.member-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid var(--pm-border); }
.member-item:last-child { border-bottom: none; }
.avatar-sm { width: 26px; height: 26px; border-radius: 50%; background: var(--pm-gradient); color: #fff; font-size: 12px; display: flex; align-items: center; justify-content: center; font-weight: 700; }
.m-name { font-size: 14px; font-weight: 600; }
.ptl { max-height: 320px; overflow-y: auto; }
.pl-work { font-size: 13px; white-space: pre-wrap; word-break: break-word; overflow-wrap: break-word; line-height: 1.6; }
.progress-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.progress-plan { margin-top: 4px; white-space: pre-wrap; word-break: break-word; }
.risk { color: var(--pm-danger); font-size: 12px; white-space: pre-wrap; word-break: break-word; }
.comp-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; padding: 10px 14px; background: var(--pm-primary-lighter); border: 1px solid var(--pm-primary-light); border-radius: 10px; }
.comp-label { font-size: 12px; color: var(--pm-text-2); white-space: nowrap; }
.comp-num { font-size: 12px; color: var(--pm-text-2); font-weight: 700; white-space: nowrap; }
.subnode-box { margin-bottom: 12px; padding: 12px 16px; background: #f7fafc; border: 1px solid var(--pm-border); border-radius: 10px; }
.subnode-title { font-weight: 700; font-size: 13px; display: flex; align-items: center; }
.subnode-row { display: flex; align-items: center; gap: 10px; padding: 6px 2px; border-bottom: 1px dashed var(--pm-border); }
.subnode-row:last-child { border-bottom: none; }
.subnode-row.done .sn-name { color: var(--pm-text-3); text-decoration: line-through; }
.sn-name { font-size: 14px; }
.sn-ops { margin-left: auto; display: flex; gap: 4px; }
.subnode-empty { padding: 4px 0; }
.actl { max-height: 420px; overflow-y: auto; }
.act-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.act-actor { font-size: 13px; font-weight: 600; color: var(--pm-text-1); }
.act-summary { flex-basis: 100%; font-size: 12.5px; color: var(--pm-text-2); white-space: pre-wrap; word-break: break-word; line-height: 1.5; }
</style>
