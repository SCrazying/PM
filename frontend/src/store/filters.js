import { reactive, watch } from 'vue'
import { defineStore } from 'pinia'

// 下拉筛选持久化：跨视图切换 + 刷新页面均保留；提供 reset(key) 重置回默认值
const STORAGE_KEY = 'pm-view-filters'

const DEFAULTS = () => ({
  board: { machine_model: '' },
  projectList: { keyword: '', status: '', machine_model: '', page: 1, size: 10, sort_field: 'id', sort_order: 'desc' },
  weekly: { weekStart: new Date().toISOString().slice(0, 10), filterMachine: '', view: 'project', filterPerson: '', filterRole: '', filterStatus: 'in_progress' },
})

function loadSaved() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}
  } catch {
    return {}
  }
}

export const useViewFilterStore = defineStore('viewFilters', () => {
  const saved = loadSaved()
  const d = DEFAULTS()
  // 与上次持久化的值合并（saved 覆盖默认值），刷新后不丢筛选
  const board = reactive({ ...d.board, ...(saved.board || {}) })
  const projectList = reactive({ ...d.projectList, ...(saved.projectList || {}) })
  const weekly = reactive({ ...d.weekly, ...(saved.weekly || {}) })

  // 任一筛选变化 → 写入 localStorage
  watch([board, projectList, weekly], () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ board, projectList, weekly }))
  }, { deep: true })

  // 重置指定页面筛选为默认值（周会视图周次重置为本周）
  function reset(key) {
    Object.assign({ board, projectList, weekly }[key], DEFAULTS()[key])
  }

  return { board, projectList, weekly, reset }
})
