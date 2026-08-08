<template>
  <div>
    <div class="pm-flex-between" style="margin-bottom:12px">
      <span class="sec-title">机型管理（新建/编辑项目下拉选择）</span>
      <div class="mm-add">
        <el-input v-model="newName" placeholder="新机型名称" style="width: 200px" clearable @keyup.enter="onAdd" />
        <el-button type="primary" :loading="saving" @click="onAdd">添加</el-button>
      </div>
    </div>

    <el-table :data="rows" v-loading="loading" border stripe>
      <el-table-column type="index" width="60" />
      <el-table-column prop="name" label="机型" min-width="180" />
      <el-table-column label="来源" width="110">
        <template #default="{ row }">
          <el-tag size="small" :type="row.source === 'registered' ? 'success' : 'info'" effect="plain">
            {{ row.source === 'registered' ? '已登记' : '历史项目' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="110">
        <template #default="{ row }">
          <el-button v-if="row.source === 'registered'" link type="danger" @click="onDelete(row)">删除</el-button>
          <el-button v-else link type="primary" @click="onAdopt(row)">登记</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!rows.length && !loading" description="暂无机型，可在上方添加" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createMachineModel, deleteMachineModel, listMachineModels } from '../../api'

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const newName = ref('')

async function load() {
  loading.value = true
  try {
    rows.value = await listMachineModels()
  } finally {
    loading.value = false
  }
}

async function onAdd() {
  const name = newName.value.trim()
  if (!name) { ElMessage.warning('请输入机型名称'); return }
  saving.value = true
  try {
    await createMachineModel(name)
    ElMessage.success('已添加')
    newName.value = ''
    load()
  } finally {
    saving.value = false
  }
}

async function onAdopt(row) {
  await createMachineModel(row.name)
  ElMessage.success(`「${row.name}」已登记`)
  load()
}

async function onDelete(row) {
  await ElMessageBox.confirm(`确定删除机型「${row.name}」？删除后不再出现在下拉中（历史项目仍保留该机型值）。`, '删除确认', { type: 'warning' })
  await deleteMachineModel(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<style scoped>
.sec-title { font-weight: 700; font-size: 15px; }
.mm-add { display: flex; gap: 8px; }
</style>
