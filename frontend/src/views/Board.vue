<template>
  <div>
    <div class="pm-toolbar">
      <span class="pm-page-title">项目看板</span>
      <div style="flex:1"></div>
      <el-select v-model="filters.machine_model" placeholder="机型" clearable filterable style="width: 140px" @change="load">
        <el-option v-for="m in machineOptions" :key="m" :label="m" :value="m" />
      </el-select>
      <el-select v-model="filters.granularity" style="width: 110px" @change="load">
        <el-option label="按月" value="month" />
        <el-option label="按年" value="year" />
      </el-select>
      <el-button @click="load"><el-icon><Refresh /></el-icon></el-button>
    </div>

    <div class="board" v-loading="loading">
      <div v-for="col in columns" :key="col.key" class="board-col">
        <div class="col-head" :style="{ borderTopColor: col.color }">
          <span class="col-title"><span class="pm-dot" :style="{ background: col.color }"></span>{{ col.title }}</span>
          <span class="col-count">{{ col.items.length }}</span>
        </div>
        <div class="col-body">
          <transition-group name="list">
            <div v-for="p in col.items" :key="p.id" class="proj-card" @click="goDetail(p)">
              <div class="pc-top">
                <span class="pc-name">{{ p.name }}</span>
                <el-tag size="small" effect="plain" :type="healthTag(p.health)">{{ healthText(p.health) }}</el-tag>
              </div>
              <div class="pc-meta">
                <span v-if="p.machine_model" class="pc-model">{{ p.machine_model }}</span>
                <span class="pc-code">{{ p.code }}</span>
              </div>
              <div class="pc-node" v-if="p.current_node"><el-icon><Flag /></el-icon>{{ p.current_node }}</div>
            </div>
          </transition-group>
          <div v-if="!col.items.length" class="col-empty">暂无项目</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getBoard, listMachineOptions } from '../api'
import { useViewFilterStore } from '../store/filters'

const router = useRouter()
const loading = ref(false)
const machineOptions = ref([])
const filters = useViewFilterStore().board
const columns = ref([
  { key: 'not_started', title: '未开始', color: '#9099a6', items: [] },
  { key: 'in_progress', title: '进行中', color: '#4f6ef7', items: [] },
  { key: 'delayed', title: '延期', color: '#f0534f', items: [] },
  { key: 'completed', title: '已完成', color: '#22c07a', items: [] },
  { key: 'suspended', title: '暂停', color: '#f5a623', items: [] },
])

const healthTag = (h) => ({ on_track: 'success', at_risk: 'warning', delayed: 'danger' }[h] || 'info')
const healthText = (h) => ({ on_track: '正常', at_risk: '风险', delayed: '延期' }[h] || h)

async function load() {
  loading.value = true
  try {
    const data = await getBoard({ granularity: filters.granularity, machine_model: filters.machine_model || undefined })
    const cols = data.columns || {}
    columns.value.forEach((c) => { c.items = cols[c.key] || [] })
  } finally { loading.value = false }
}
function goDetail(p) { router.push({ name: 'project-detail', params: { id: p.id } }) }
onMounted(async () => {
  machineOptions.value = await listMachineOptions()
  load()
})
</script>

<style scoped>
.board { display: flex; gap: 14px; overflow-x: auto; padding-bottom: 8px; }
.board-col { flex: 1; min-width: 230px; display: flex; flex-direction: column; }
.col-head { background: var(--pm-card); border-radius: var(--pm-radius) var(--pm-radius) 0 0; border-top: 3px solid; padding: 10px 14px; display: flex; justify-content: space-between; align-items: center; box-shadow: var(--pm-shadow); }
.col-title { font-weight: 700; font-size: 14px; display: flex; align-items: center; }
.col-count { background: #eef1f6; color: var(--pm-text-2); border-radius: 10px; padding: 1px 9px; font-size: 12px; font-weight: 600; }
.col-body { background: #eceff4; border-radius: 0 0 var(--pm-radius) var(--pm-radius); padding: 10px; min-height: 300px; flex: 1; }
.proj-card { background: var(--pm-card); border-radius: var(--pm-radius); padding: 12px 14px; margin-bottom: 10px; cursor: pointer; border: 1px solid transparent; transition: all .15s ease; box-shadow: var(--pm-shadow); }
.proj-card:hover { transform: translateY(-2px); box-shadow: var(--pm-shadow-lg); border-color: var(--pm-primary-light); }
.pc-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 6px; }
.pc-name { font-weight: 600; font-size: 14px; }
.pc-meta { display: flex; gap: 8px; margin-top: 8px; align-items: center; }
.pc-model { background: var(--pm-primary-light); color: var(--pm-primary); font-size: 12px; padding: 1px 8px; border-radius: 6px; }
.pc-code { color: var(--pm-text-3); font-size: 12px; }
.pc-node { margin-top: 8px; color: var(--pm-text-2); font-size: 12px; display: flex; align-items: center; gap: 4px; }
.col-empty { text-align: center; color: var(--pm-text-3); padding: 40px 0; font-size: 13px; }
.list-move { transition: transform .2s; }
</style>
