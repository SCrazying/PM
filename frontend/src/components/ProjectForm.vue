<template>
  <el-dialog v-model="visible" :title="isEdit ? '编辑项目' : '新建项目'" width="640px" :close-on-click-modal="false">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
      <el-form-item label="项目名称" prop="name">
        <el-input v-model="form.name" placeholder="如：X 机型控制器" />
      </el-form-item>
      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="项目编号" prop="code">
            <el-input v-model="form.code" :disabled="isEdit" placeholder="如：P2026001" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="机型">
            <el-input v-model="form.machine_model" placeholder="如：X100" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="负责人" prop="owner_id">
        <el-select v-model="form.owner_id" filterable placeholder="选择负责人" style="width: 100%">
          <el-option v-for="u in users" :key="u.id" :label="u.display_name" :value="u.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="项目角色">
        <el-row :gutter="10" class="role-grid">
          <el-col v-for="role in roleOptions" :key="role.key" :span="12">
            <div class="role-field">
              <span class="role-label">{{ role.label }}</span>
              <el-select
                v-model="form.role_assignments[role.key]"
                :multiple="role.multiple"
                :collapse-tags="role.multiple"
                :collapse-tags-tooltip="role.multiple"
                clearable filterable
                :placeholder="role.multiple ? '可多选用户' : '可选 1 名用户'"
                style="width: 100%"
              >
                <el-option v-for="u in users" :key="u.id" :label="u.display_name" :value="u.id" />
              </el-select>
            </div>
          </el-col>
        </el-row>
      </el-form-item>
      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="开始日期">
            <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="结束日期">
            <el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="2" />
      </el-form-item>

      <el-form-item v-if="!isEdit" label="TR 节点">
        <div class="node-box">
          <el-select v-model="form.template_id" placeholder="选择节点模板" style="width: 220px" @change="onTemplateChange">
            <el-option v-for="t in templates" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
          <el-checkbox-group v-model="form.node_ids" class="node-checks" @change="onNodeChange">
            <el-checkbox v-for="n in templateNodes" :key="n.id" :value="n.id">
              {{ n.node_key }} {{ n.name }}
            </el-checkbox>
          </el-checkbox-group>
          <div v-if="selectedTemplateNodes.length" class="node-plans">
            <div class="node-plan-title">节点计划完成时间（截止日期必填）</div>
            <div v-for="n in selectedTemplateNodes" :key="n.id" class="node-plan-row">
              <span class="node-plan-name">{{ n.node_key }} {{ n.name }}</span>
              <el-date-picker v-model="form.node_plans[n.id].planned_end" type="date" value-format="YYYY-MM-DD" placeholder="计划完成" />
              <el-tag v-if="isNodePlanOverdue(form.node_plans[n.id])" size="small" type="warning">已超期</el-tag>
            </div>
          </div>
          <div class="node-tip">勾选本项目需要做的 TR 节点（默认全选）</div>
        </div>
      </el-form-item>
      <el-form-item v-if="isEdit && editableProjectNodes.length" label="节点">
        <div class="node-box">
          <div class="node-plan-title">勾选启用节点；未勾选将停用；可修改计划完成日期</div>
          <div v-for="n in editableProjectNodes" :key="n.id" class="node-plan-row">
            <el-checkbox v-model="form.node_ids" :value="n.id">
              {{ n.node_key }} {{ n.name }}
            </el-checkbox>
            <el-date-picker v-model="form.node_deadlines[n.id]" type="date" value-format="YYYY-MM-DD" placeholder="计划完成"
                            clearable :disabled="!form.node_ids.includes(n.id)" />
            <el-tag v-if="isDeadlineOverdue(form.node_deadlines[n.id])" size="small" type="warning">已超期</el-tag>
          </div>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="onSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createProject, listTemplates, listUserOptions, updateProject } from '../api'

const emit = defineEmits(['saved'])

const visible = ref(false)
const saving = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const formRef = ref()
const users = ref([])
const templates = ref([])
const projectNodes = ref([])
const roleOptions = [
  { key: 'SE', label: 'SE', multiple: false },
  { key: 'TPM', label: 'TPM', multiple: false },
  { key: 'TL/FO', label: 'TL/FO', multiple: true },
  { key: 'CodeReview', label: 'CodeReview', multiple: true },
]

function emptyRoleAssignments() {
  return { SE: null, TPM: null, 'TL/FO': [], CodeReview: [] }
}

function roleAssignmentPayload() {
  const result = {}
  for (const role of roleOptions) {
    const value = form.role_assignments[role.key]
    result[role.key] = role.multiple
      ? (Array.isArray(value) ? [...value] : [])
      : (value === null || value === undefined || value === '' ? [] : [value])
  }
  return result
}

function setRoleAssignments(value) {
  const source = value || {}
  const next = emptyRoleAssignments()
  for (const role of roleOptions) {
    const ids = Array.isArray(source[role.key]) ? source[role.key] : []
    next[role.key] = role.multiple ? [...ids] : (ids[0] ?? null)
  }
  form.role_assignments = next
}

const form = reactive({
  name: '', code: '', machine_model: '', owner_id: null,
  start_date: null, end_date: null, description: '',
  template_id: null, node_ids: [], node_plans: {}, node_deadlines: {}, role_assignments: emptyRoleAssignments(),
})

const rules = {
  name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入项目编号', trigger: 'blur' }],
  owner_id: [{ required: true, message: '请选择负责人', trigger: 'change' }],
}

const templateNodes = computed(() => {
  const t = templates.value.find((x) => x.id === form.template_id)
  return t ? t.nodes : []
})

const selectedTemplateNodes = computed(() => templateNodes.value.filter((n) => form.node_ids.includes(n.id)))
const editableProjectNodes = computed(() => projectNodes.value)

function ensureNodePlans() {
  const next = {}
  for (const n of selectedTemplateNodes.value) {
    const current = form.node_plans[n.id] || {}
    next[n.id] = {
      template_node_id: n.id,
      planned_end: current.planned_end || null,
    }
  }
  form.node_plans = next
}

function onTemplateChange() {
  form.node_ids = templateNodes.value.map((n) => n.id) // 默认全选
  ensureNodePlans()
}

function onNodeChange() {
  ensureNodePlans()
}

function isNodePlanOverdue(plan) {
  return Boolean(plan?.planned_end && plan.planned_end < new Date().toISOString().slice(0, 10))
}

function isDeadlineOverdue(deadline) {
  return Boolean(deadline && deadline < new Date().toISOString().slice(0, 10))
}

function nodePlanPayload() {
  return selectedTemplateNodes.value.map((n) => ({ ...form.node_plans[n.id], template_node_id: n.id }))
}

function nodeDeadlinePayload() {
  // 仅提交启用节点（勾选的）的截止时间，避免停用节点报"节点不属于当前项目"
  return editableProjectNodes.value
    .filter((n) => form.node_ids.includes(n.id))
    .map((n) => ({
      project_node_id: n.id,
      planned_end: form.node_deadlines[n.id] || null,
    }))
}

function validateNodePlans() {
  const invalid = selectedTemplateNodes.value.find((n) => {
    const plan = form.node_plans[n.id]
    return !plan?.planned_end
  })
  if (invalid) {
    ElMessage.warning(`请补齐节点“${invalid.node_key} ${invalid.name}”的计划完成日期`)
    return false
  }
  return true
}

async function open(project) {
  isEdit.value = !!project
  if (!users.value.length) users.value = await listUserOptions()
  if (!project && !templates.value.length) templates.value = await listTemplates()
  visible.value = true

  if (project) {
    editId.value = project.id
    projectNodes.value = project.nodes || []
    Object.assign(form, {
      name: project.name, code: project.code, machine_model: project.machine_model,
      owner_id: project.owner_id, start_date: project.start_date, end_date: project.end_date,
      description: project.description, template_id: null,
      node_ids: (project.nodes || []).filter((n) => !n.is_deleted).map((n) => n.id),  // 勾选启用节点
      node_plans: {},
      node_deadlines: Object.fromEntries((project.nodes || []).map((node) => [node.id, node.planned_end || null])),
    })
    setRoleAssignments(project.role_assignments)
  } else {
    editId.value = null
    projectNodes.value = []
    Object.assign(form, {
      name: '', code: '', machine_model: '', owner_id: null, start_date: null, end_date: null,
      description: '', template_id: templates.value[0]?.id || null, node_ids: [], node_plans: {}, node_deadlines: {},
    })
    setRoleAssignments()
    if (form.template_id) {
      onTemplateChange()
    }
  }
}

async function onSubmit() {
  await formRef.value.validate().catch(() => Promise.reject())
  if (!isEdit.value && !validateNodePlans()) return
  saving.value = true
  try {
    if (isEdit.value) {
      await updateProject(editId.value, {
        name: form.name, machine_model: form.machine_model, owner_id: form.owner_id,
        start_date: form.start_date, end_date: form.end_date, description: form.description,
        role_assignments: roleAssignmentPayload(), node_deadlines: nodeDeadlinePayload(),
        node_enabled_ids: [...form.node_ids],
      })
      ElMessage.success('已更新')
    } else {
      await createProject({
        name: form.name, code: form.code, machine_model: form.machine_model, owner_id: form.owner_id,
        start_date: form.start_date, end_date: form.end_date, description: form.description,
        node_ids: form.node_ids, node_plans: nodePlanPayload(), members: [], role_assignments: roleAssignmentPayload(),
      })
      ElMessage.success('已创建')
    }
    visible.value = false
    emit('saved')
  } finally {
    saving.value = false
  }
}

defineExpose({ open })
</script>

<style scoped>
.node-box { width: 100%; }
.node-checks { display: flex; flex-wrap: wrap; gap: 4px 16px; margin-top: 8px; }
.node-tip { color: #909399; font-size: 12px; margin-top: 4px; }
.node-plans { margin-top: 12px; border-top: 1px solid var(--pm-border); padding-top: 10px; }
.node-plan-title { color: var(--pm-text-2); font-size: 12px; margin-bottom: 8px; }
.node-plan-row { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }
.node-plan-row :deep(.el-date-editor) { width: 140px; }
.node-plan-name { width: 132px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
.node-plan-arrow { color: var(--pm-text-3); }
.role-grid { width: 100%; row-gap: 8px; }
.role-field { display: flex; align-items: center; gap: 6px; }
.role-label { width: 68px; color: var(--pm-text-2); font-size: 13px; flex: none; }
</style>
