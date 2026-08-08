import { defineStore } from 'pinia'

// 跨视图保留筛选/查询状态：项目看板 / 项目列表 / 周会视图 之间切换时不重置
export const useViewFilterStore = defineStore('viewFilters', {
  state: () => ({
    board: { machine_model: '', granularity: 'month' },
    projectList: { keyword: '', status: '', machine_model: '', page: 1, size: 10 },
    weekly: { weekStart: new Date().toISOString().slice(0, 10), filterMachine: '', view: 'project', filterPerson: '', filterRole: '', filterStatus: '' },
  }),
})
