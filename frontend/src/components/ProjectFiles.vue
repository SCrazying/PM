<template>
  <div class="pm-card" style="margin-top:14px">
    <div class="pm-flex-between" style="margin-bottom:8px">
      <span class="card-title">项目资料</span>
      <el-button v-if="canEdit" size="small" type="primary" plain @click="dialogVisible = true">
        <el-icon style="margin-right:3px"><Upload /></el-icon>上传资料
      </el-button>
    </div>
    <div v-if="files.length" class="file-list">
      <div v-for="f in files" :key="f.id" class="file-item">
        <el-icon class="fi-ico" :size="16"><Document /></el-icon>
        <span class="fi-cat">{{ f.category || '附件' }}</span>
        <span class="fi-name" :title="f.file_name" @click="onDownload(f)">{{ f.file_name }}</span>
        <span class="fi-size">{{ fmtSize(f.file_size) }}</span>
        <span class="fi-meta">{{ f.uploaded_by_name || '—' }} · {{ fmtDate(f.uploaded_at) }}</span>
        <span class="fi-ops">
          <el-button link size="small" type="primary" @click="onDownload(f)">下载</el-button>
          <el-button v-if="canDel(f)" link size="small" type="danger" @click="onDelete(f)">删除</el-button>
        </span>
      </div>
    </div>
    <div v-else class="empty">暂无资料</div>

    <el-dialog v-model="dialogVisible" title="上传项目资料" width="620px" :close-on-click-modal="false">
      <el-form label-width="80px">
        <el-form-item label="分类">
          <el-select v-model="category" style="width:100%">
            <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="文件">
          <input ref="fileInput" type="file" class="file-input" @change="onPick" />
          <div class="pm-sub" style="margin-top:6px">支持常见文档/图片/压缩包，单文件 ≤ 50MB</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="onUpload">上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteAttachment, downloadAttachment, listAttachments, uploadAttachment } from '../api'
import { useUserStore } from '../store/user'

const props = defineProps({
  projectId: { type: Number, required: true },
  ownerId: { type: Number, default: null },
})

const store = useUserStore()
const files = ref([])
const dialogVisible = ref(false)
const category = ref('需求矩阵')
const categories = ['需求矩阵', '方案设计', '验证报告', '其他']
const uploading = ref(false)
const picked = ref(null)
const fileInput = ref(null)

const canEdit = computed(() => store.isAdmin || store.userInfo?.user_id === props.ownerId)
const canDel = (f) => canEdit.value || f.uploaded_by === store.userInfo?.user_id

const fmtSize = (n) => (n == null ? '' : n > 1048576 ? `${(n / 1048576).toFixed(1)}MB` : n > 1024 ? `${(n / 1024).toFixed(0)}KB` : `${n}B`)
const fmtDate = (d) => (d ? String(d).slice(0, 10) : '')

async function load() { files.value = await listAttachments(props.projectId).catch(() => []) }
function onPick(e) { picked.value = e.target.files?.[0] || null }

async function onUpload() {
  if (!picked.value) { ElMessage.warning('请选择文件'); return }
  const fd = new FormData()
  fd.append('project_id', props.projectId)
  fd.append('category', category.value)
  fd.append('file', picked.value)
  uploading.value = true
  try {
    await uploadAttachment(fd)
    ElMessage.success('已上传')
    dialogVisible.value = false
    picked.value = null
    if (fileInput.value) fileInput.value.value = ''
    load()
  } catch (e) {
    ElMessage.error(errMsg(e, '上传失败'))
  } finally {
    uploading.value = false
  }
}

async function onDownload(f) {
  try {
    // 走 axios（带 Authorization），避免 <a href> 直接跳转 401
    const blob = await downloadAttachment(f.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = f.file_name
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error(e?.response?.data?.message || '下载失败')
  }
}

async function onDelete(f) {
  try {
    await ElMessageBox.confirm(`确认删除资料「${f.file_name}」？`, '删除确认', { type: 'warning', confirmButtonText: '删除' })
  } catch {
    return  // 取消
  }
  try {
    await deleteAttachment(f.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    ElMessage.error(errMsg(e, '删除失败'))
  }
}

function errMsg(e, fallback) {
  return e?.response?.data?.message || fallback
}

onMounted(load)
</script>

<style scoped>
.file-list { display: flex; flex-direction: column; gap: 5px; max-height: 320px; overflow-y: auto; }
.file-item { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 6px; border: 1px solid var(--pm-border); }
.file-item:hover { background: var(--pm-bg); }
.fi-ico { color: var(--pm-primary); flex-shrink: 0; }
.fi-cat { background: var(--pm-primary-light); color: var(--pm-primary); font-size: 11px; padding: 1px 7px; border-radius: 5px; flex-shrink: 0; }
.fi-name { font-weight: 600; font-size: 13px; cursor: pointer; flex: 0 1 auto; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fi-name:hover { color: var(--pm-primary); }
.fi-size { color: var(--pm-text-3); font-size: 11.5px; flex-shrink: 0; }
.fi-meta { color: var(--pm-text-3); font-size: 11.5px; flex-shrink: 0; }
.fi-ops { margin-left: auto; flex-shrink: 0; }
.empty { color: var(--pm-text-3); font-size: 13px; padding: 8px 0; }
.file-input { font-size: 13px; }
</style>
