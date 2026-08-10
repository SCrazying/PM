<template>
  <div>
    <div class="sec-title" style="margin-bottom:14px">Excel 台账导入</div>

    <!-- 上传 -->
    <el-upload v-if="!preview" drag :auto-upload="false" :limit="1" accept=".xlsx,.xls" :on-change="onFile" class="up">
      <el-icon :size="40" style="color:var(--pm-primary)"><UploadFilled /></el-icon>
      <div class="el-upload__text">拖拽 Excel 到此处，或 <em>点击选择</em></div>
      <div class="el-upload__tip">支持现有周报表格式（机型/项目/是否投入/项目角色/关键节点/周目标/本周任务）</div>
    </el-upload>

    <!-- 预览 -->
    <div v-else>
      <el-alert v-if="preview.warnings?.length" type="warning" :closable="false" style="margin-bottom:12px">
        <div v-for="(w, i) in preview.warnings" :key="i">⚠ {{ w }}</div>
      </el-alert>
      <div class="pm-flex-between" style="margin-bottom:12px">
        <span>解析出 <b>{{ preview.projects.length }}</b> 个项目（将迁入：项目/节点/任务骨架 + 当前周目标）</span>
        <div class="pm-flex pm-gap">
          <el-button @click="reset">重新选择</el-button>
          <el-button type="primary" :loading="confirming" @click="doConfirm">确认导入</el-button>
        </div>
      </div>
      <el-collapse>
        <el-collapse-item v-for="(p, i) in preview.projects" :key="i" :name="i">
          <template #title>
            <div class="pv-title">
              <span class="pm-dot" :class="p.warnings?.length ? 'warning' : 'success'"></span>
              <b>{{ p.name }}</b>
              <el-tag v-if="p.machine_model" size="small" effect="plain">{{ p.machine_model }}</el-tag>
              <el-tag v-if="p.current_node_key" size="small" type="success" effect="plain">{{ p.current_node_key }}</el-tag>
              <span class="pm-sub">{{ p.members.length }}人 / {{ p.tasks.length }}任务</span>
              <span v-if="p.warnings?.length" class="pv-warn">⚠ {{ p.warnings.length }} 项待确认</span>
            </div>
          </template>
          <div class="pv-body">
            <div v-for="(w, j) in p.warnings" :key="j" class="pv-warn-line">⚠ {{ w }}</div>
            <div class="pv-sec"><b>成员：</b>
              <span v-for="m in p.members" :key="m.name" class="pv-mem">
                {{ m.name }}({{ m.project_role }}){{ m.is_owner ? '★' : '' }}{{ m.matched ? '' : '❓' }}
              </span>
            </div>
            <div class="pv-sec" v-if="p.weekly_goal"><b>周目标：</b>{{ p.weekly_goal }}</div>
            <div class="pv-sec" v-if="p.tasks.length"><b>任务：</b>{{ p.tasks.join('；') }}</div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>

    <!-- 结果 -->
    <el-dialog v-model="resultVisible" title="导入结果" width="700px" :close-on-click-modal="false">
      <el-result icon="success" title="导入完成" :sub-title="`成功导入 ${result.created} 个项目${result.failed?.length ? `，失败 ${result.failed.length} 个` : ''}`" />
      <div v-for="(f, i) in result.failed" :key="i" class="pv-warn-line">✗ {{ f.project }}：{{ f.error }}</div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { importConfirm, importPreview } from '../../api'

const preview = ref(null)
const confirming = ref(false)
const resultVisible = ref(false)
const result = ref({ created: 0, failed: [] })

async function onFile(file) {
  const fd = new FormData()
  fd.append('file', file.raw)
  try {
    preview.value = await importPreview(fd)
  } catch { /* 拦截器提示 */ }
}

function reset() { preview.value = null }

async function doConfirm() {
  confirming.value = true
  try {
    result.value = await importConfirm(preview.value.projects)
    resultVisible.value = true
    preview.value = null
  } finally { confirming.value = false }
}
</script>

<style scoped>
.sec-title { font-weight: 700; font-size: 15px; }
.up { max-width: 560px; }
.pv-title { display: flex; align-items: center; gap: 8px; width: 100%; }
.pv-warn { color: var(--pm-warning); font-size: 12px; margin-left: auto; }
.pv-body { padding: 4px; }
.pv-sec { font-size: 13px; margin-bottom: 8px; }
.pv-mem { margin-right: 10px; }
.pv-warn-line { color: var(--pm-warning); font-size: 13px; margin-bottom: 4px; }
</style>
