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
          <el-tag v-for="n in row.nodes" :key="n.id" size="small" effect="plain" style="margin-right:4px"
                  :title="n.subnodes?.length ? `默认子节点：${n.subnodes.map(s=>s.name).join('、')}` : ''">
            {{ n.node_key }}{{ n.subnodes?.length ? `(${n.subnodes.length})` : '' }}
          </el-tag>
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

    <el-dialog v-model="visible" title="新建模板" width="640px">
      <el-form label-width="80px">
        <el-form-item label="模板名" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" /></el-form-item>
        <el-form-item label="节点">
          <div v-for="(n, i) in form.nodes" :key="i" class="node-card">
            <div class="node-row">
              <el-input v-model="n.node_key" placeholder="键 如 TR1" style="width:100px" />
              <el-input v-model="n.name" placeholder="节点名称" style="flex:1" />
              <el-button link type="danger" @click="form.nodes.splice(i, 1)">删</el-button>
            </div>
            <div class="node-subs">
              <span class="ns-label">默认子节点：</span>
              <el-tag v-for="(s, k) in n.subnodes" :key="k" closable size="small" class="ns-tag"
                      @close="n.subnodes.splice(k, 1)">{{ s }}</el-tag>
              <el-input v-model="n._newSub" size="small" placeholder="子节点名称（回车添加）" style="width:160px"
                        @keyup.enter="addSub(n)" />
              <el-button size="small" link type="primary" @click="addSub(n)">添加</el-button>
              <span class="ns-tip">建项目时将自动生成这些子节点</span>
            </div>
          </div>
          <el-button size="small" @click="form.nodes.push({ node_key: '', name: '', subnodes: [], _newSub: '' })" style="margin-top:6px">+ 加节点</el-button>
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
const form = reactive({ name: '', description: '', nodes: [{ node_key: 'TR1', name: '', subnodes: [], _newSub: '' }] })

function newNode() { return { node_key: '', name: '', subnodes: [], _newSub: '' } }

async function load() { loading.value = true; try { rows.value = await listTemplates() } finally { loading.value = false } }
function openForm() { Object.assign(form, { name: '', description: '', nodes: [newNode()] }); visible.value = true }

function addSub(n) {
  const v = (n._newSub || '').trim()
  if (!v) return
  if (!n.subnodes) n.subnodes = []
  n.subnodes.push(v)
  n._newSub = ''
}

async function save() {
  if (!form.name) { ElMessage.warning('请输入模板名'); return }
  const nodes = form.nodes.filter((n) => n.node_key && n.name).map((n, i) => ({
    node_key: n.node_key, name: n.name, sequence: i + 1,
    subnodes: (n.subnodes || []).filter((s) => s && s.trim()).map((s) => ({ name: s.trim() })),
  }))
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
.node-card { border: 1px solid var(--pm-border); border-radius: 8px; padding: 8px 10px; margin-bottom: 8px; background: #fafbfd; }
.node-row { display: flex; gap: 8px; margin-bottom: 6px; align-items: center; }
.node-subs { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.ns-label { font-size: 12px; color: var(--pm-text-2); }
.ns-tag { }
.ns-tip { font-size: 11px; color: var(--pm-text-3); }
</style>
