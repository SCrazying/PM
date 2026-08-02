<template>
  <div>
    <div class="pm-flex-between" style="margin-bottom:12px">
      <span class="sec-title">TR 节点模板</span>
      <el-button type="success" @click="openForm()">新建模板</el-button>
    </div>
    <el-table :data="rows" v-loading="loading" border>
      <el-table-column prop="name" label="模板名" width="180">
        <template #default="{ row }">
          {{ row.name }} <el-tag v-if="row.is_builtin" size="small" type="warning" effect="plain">内置</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="200">
        <template #default="{ row }">{{ row.description || '—' }}</template>
      </el-table-column>
      <el-table-column label="节点" min-width="280">
        <template #default="{ row }">
          <el-tag v-for="n in row.nodes" :key="n.id" size="small" effect="plain" style="margin-right:4px">{{ n.node_key }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status === 'active' ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link :type="row.status === 'active' ? 'info' : 'success'" @click="onToggle(row)">
            {{ row.status === 'active' ? '停用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="visible" title="新建模板" width="560px">
      <el-form label-width="80px">
        <el-form-item label="模板名" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" /></el-form-item>
        <el-form-item label="节点">
          <div v-for="(n, i) in form.nodes" :key="i" class="node-row">
            <el-input v-model="n.node_key" placeholder="键 如 TR1" style="width:100px" />
            <el-input v-model="n.name" placeholder="名称" style="flex:1" />
            <el-button link type="danger" @click="form.nodes.splice(i, 1)">删</el-button>
          </div>
          <el-button size="small" @click="form.nodes.push({ node_key: '', name: '' })" style="margin-top:6px">+ 加节点</el-button>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="save">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createTemplate, listTemplates, updateTemplate } from '../../api'

const loading = ref(false)
const rows = ref([])
const visible = ref(false)
const form = reactive({ name: '', description: '', nodes: [{ node_key: 'TR1', name: '' }] })

async function load() { loading.value = true; try { rows.value = await listTemplates() } finally { loading.value = false } }
function openForm() { Object.assign(form, { name: '', description: '', nodes: [{ node_key: 'TR1', name: '' }] }); visible.value = true }
async function save() {
  if (!form.name) { ElMessage.warning('请输入模板名'); return }
  const nodes = form.nodes.filter((n) => n.node_key && n.name).map((n, i) => ({ ...n, sequence: i + 1 }))
  if (!nodes.length) { ElMessage.warning('至少一个有效节点'); return }
  await createTemplate({ name: form.name, description: form.description, nodes })
  ElMessage.success('已创建'); visible.value = false; load()
}
async function onToggle(row) {
  await updateTemplate(row.id, { status: row.status === 'active' ? 'disabled' : 'active' })
  ElMessage.success('已更新'); load()
}
onMounted(load)
</script>
<style scoped>
.sec-title { font-weight: 700; font-size: 15px; }
.node-row { display: flex; gap: 8px; margin-bottom: 6px; align-items: center; }
</style>
