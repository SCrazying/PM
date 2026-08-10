<template>
  <div class="pm-card">
    <div class="sec-title" style="margin-bottom:6px">看板报工提醒排除</div>
    <p class="pm-sub" style="margin:0 0 14px">
      选中的人员在<strong>项目看板 · 昨日进展/今日计划缺报</strong>面板中不再提示（不参与早会点名）；
      其余在研项目成员与负责人照常提示。保存后立即生效。
    </p>
    <el-select v-model="exemptIds" multiple filterable clearable placeholder="选择不提示的人员"
               style="width: 520px; max-width: 100%">
      <el-option v-for="u in users" :key="u.id" :label="u.display_name" :value="u.id" />
    </el-select>
    <el-button type="primary" style="margin-left:10px" :loading="saving" @click="save">保存</el-button>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listConfig, listUserOptions, setConfig } from '../../api'

const CONFIG_KEY = 'board.report_exempt_users'
const users = ref([])
const exemptIds = ref([])
const saving = ref(false)

async function load() {
async function load() {
  try {
    users.value = await listUserOptions()
    const rows = await listConfig()
    const row = rows.find((r) => r.key === CONFIG_KEY)
    try {
      exemptIds.value = row && row.value ? JSON.parse(row.value) : []
    } catch {
      exemptIds.value = []
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '加载配置失败')
  }
}

async function save() {
  saving.value = true
  try {
    await setConfig(CONFIG_KEY, JSON.stringify(exemptIds.value))
    ElMessage.success('已保存看板报工提醒排除配置')
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '保存失败')
  } finally {
    saving.value = false
  }
}
onMounted(load)
</script>

<style scoped>
.sec-title { font-weight: 700; font-size: 15px; }
</style>
