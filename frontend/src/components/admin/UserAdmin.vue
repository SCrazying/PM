<template>
  <div>
    <div class="pm-flex-between" style="margin-bottom:12px">
      <span class="sec-title">用户列表</span>
      <el-button type="success" @click="openForm()">新建用户</el-button>
    </div>
    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column prop="username" label="用户名" width="140" />
      <el-table-column prop="display_name" label="姓名" width="140" />
      <el-table-column prop="email" label="邮箱" min-width="160">
        <template #default="{ row }">{{ row.email || '—' }}</template>
      </el-table-column>
      <el-table-column label="角色" width="100">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : 'primary'" size="small">{{ row.role === 'admin' ? '管理员' : '成员' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status === 'active' ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="300" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openForm(row)">编辑</el-button>
          <el-button link type="warning" @click="onReset(row)">重置密码</el-button>
          <el-button link :type="row.status === 'active' ? 'info' : 'success'" @click="onToggle(row)">
            {{ row.status === 'active' ? '停用' : '启用' }}
          </el-button>
          <el-button link type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="visible" :title="form.id ? '编辑用户' : '新建用户'" width="440px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="用户名" required><el-input v-model="form.username" :disabled="!!form.id" /></el-form-item>
        <el-form-item label="姓名" required><el-input v-model="form.display_name" /></el-form-item>
        <el-form-item v-if="!form.id" label="初始密码" required><el-input v-model="form.password" show-password /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="form.role">
            <el-radio value="member">成员</el-radio>
            <el-radio value="admin">管理员</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createUser, deleteUser, listUsers, resetPassword, setUserStatus, updateUser } from '../../api'

const loading = ref(false)
const rows = ref([])
const visible = ref(false)
const form = reactive({ id: null, username: '', display_name: '', password: '', email: '', role: 'member' })

async function load() { loading.value = true; try { rows.value = await listUsers() } finally { loading.value = false } }
function openForm(row) {
  if (row) Object.assign(form, { id: row.id, username: row.username, display_name: row.display_name, password: '', email: row.email, role: row.role })
  else Object.assign(form, { id: null, username: '', display_name: '', password: '', email: '', role: 'member' })
  visible.value = true
}
async function save() {
  if (!form.username || !form.display_name) { ElMessage.warning('请填写完整'); return }
  if (form.id) await updateUser(form.id, { display_name: form.display_name, email: form.email, role: form.role })
  else { if (!form.password) { ElMessage.warning('请设置初始密码'); return } await createUser(form) }
  ElMessage.success('已保存'); visible.value = false; load()
}
async function onReset(row) {
  const { value } = await ElMessageBox.prompt(`为「${row.display_name}」设置新密码`, '重置密码', { inputPattern: /.{6,}/, inputErrorMessage: '至少 6 位' })
  await resetPassword(row.id, value); ElMessage.success('已重置')
}
async function onToggle(row) {
  await setUserStatus(row.id, row.status === 'active' ? 'disabled' : 'active'); ElMessage.success('已更新'); load()
}
async function onDelete(row) {
  await ElMessageBox.confirm(
    `确定删除用户「${row.display_name}」？其项目/任务等关联数据将阻止删除，建议使用「停用」。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', confirmButtonClass: 'el-button--danger' },
  )
  await deleteUser(row.id); ElMessage.success('已删除'); load()
}
onMounted(load)
</script>
<style scoped>
.sec-title { font-weight: 700; font-size: 15px; }
</style>
