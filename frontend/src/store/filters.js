import { reactive, watch } from 'vue'
import { defineStore } from 'pinia'

// 下拉筛选持久化：跨视图切换 + 刷新页面均保留；提供 reset(key) 重置回默认值
// columns：各列表/视图的列显示配置（独立于筛选，reset 不清空，恢复默认用 resetColumns）
const STORAGE_KEY = 'pm-view-filters'

const DEFAULTS = () => ({
  board: { machine_model: '' },
  projectList: { keyword: '', status: '', machine_model: '', page: 1, size: 10, sort_field: 'id', sort_order: 'desc' },
  weekly: { weekStart: new Date().toISOString().slice(0, 10), filterMachine: '', view: 'project', filterPerson: '', filterRole: '', filterStatus: 'in_progress', dailyTodayOnly: false },
})

// 各视图默认可见列（操作列/展开列固定展示，不进列表）
const DEFAULT_COLUMNS = {
  projectList: ['name', 'description', 'machine_model', 'current_node', 'status'],
  weekly: ['machine', 'name', 'description', 'status', 'roles', 'current_node', 'subnodes', 'goals', 'today_plan', 'daily'],
}

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
  // 列显示配置：有历史值用之，否则回默认全显示
  const columns = reactive({
    projectList: Array.isArray(saved.columns?.projectList) ? [...saved.columns.projectList] : [...DEFAULT_COLUMNS.projectList],
    weekly: Array.isArray(saved.columns?.weekly) ? [...saved.columns.weekly] : [...DEFAULT_COLUMNS.weekly],
  })

  // 任一筛选变化 → 写入 localStorage
  watch([board, projectList, weekly, columns], () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ board, projectList, weekly, columns }))
  }, { deep: true })

  // 重置指定页面筛选为默认值（周会视图周次重置为本周）
  function reset(key) {
    Object.assign({ board, projectList, weekly }[key], DEFAULTS()[key])
  }

  // 恢复某视图的列显示为默认（全显示）
  function resetColumns(key) {
    columns[key] = [...DEFAULT_COLUMNS[key]]
  }

  return { board, projectList, weekly, columns, reset, resetColumns }
})
