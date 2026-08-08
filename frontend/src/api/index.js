import request from './request'

// 项目
export const listProjects = (params) => request.get('/projects', { params })
export const createProject = (data) => request.post('/projects', data)
export const getProject = (id) => request.get(`/projects/${id}`)
export const updateProject = (id, data) => request.put(`/projects/${id}`, data)
export const archiveProject = (id) => request.post(`/projects/${id}/archive`)
export const unarchiveProject = (id) => request.post(`/projects/${id}/unarchive`)
export const deleteProject = (id) => request.delete(`/projects/${id}`)
export const listMembers = (id) => request.get(`/projects/${id}/members`)
export const addMember = (id, data) => request.post(`/projects/${id}/members`, data)
export const removeMember = (id, mid) => request.delete(`/projects/${id}/members/${mid}`)

// 模板 / 节点 / 任务
export const listTemplates = () => request.get('/tr-templates')
export const createTemplate = (data) => request.post('/tr-templates', data)
export const updateTemplate = (id, data) => request.put(`/tr-templates/${id}`, data)
export const listNodes = (projectId) => request.get(`/projects/${projectId}/nodes`)
export const updateNode = (id, data) => request.patch(`/nodes/${id}`, data)
export const nodeTransition = (id, target) => request.post(`/nodes/${id}/transition`, { target })
export const nodeAdvance = (id) => request.post(`/nodes/${id}/advance`)
export const nodeComplete = (id) => request.post(`/nodes/${id}/complete`)
export const nodeCompletion = (id) => request.get(`/nodes/${id}/completion`)
export const projectCompletion = (id) => request.get(`/projects/${id}/completion`)
export const nodeForceTransition = (id, target) => request.post(`/nodes/${id}/force-transition`, { target })
export const addSubnode = (nodeId, data) => request.post(`/nodes/${nodeId}/subnodes`, data)
export const updateSubnode = (id, data) => request.patch(`/subnodes/${id}`, data)
export const setSubnodeStatus = (id, status) => request.patch(`/subnodes/${id}/status`, { status })
export const deleteSubnode = (id) => request.delete(`/subnodes/${id}`)
export const addReview = (id, data) => request.post(`/nodes/${id}/reviews`, data)
export const listReviews = (id) => request.get(`/nodes/${id}/reviews`)
export const listTasks = (projectId, params) => request.get(`/projects/${projectId}/tasks`, { params })
export const createTask = (nodeId, data) => request.post(`/nodes/${nodeId}/tasks`, data)
export const updateTask = (id, data) => request.put(`/tasks/${id}`, data)
export const setTaskStatus = (id, status) => request.patch(`/tasks/${id}/status`, { status })
export const deleteTask = (id) => request.delete(`/tasks/${id}`)

// 进展 / 周目标
export const listProgress = (projectId, params) => request.get(`/projects/${projectId}/progress`, { params })
export const createProgress = (projectId, data) => request.post(`/projects/${projectId}/progress`, data)
export const updateProgress = (id, data) => request.put(`/progress/${id}`, data)
export const deleteProgress = (id) => request.delete(`/progress/${id}`)
export const setProgressRiskResolved = (id, resolved) => request.patch(`/progress/${id}/risk-resolve`, { resolved })
export const myTodo = () => request.get('/progress/mine/todo')
export const getWeeklyGoal = (projectId, week_start) => request.get(`/projects/${projectId}/weekly-goal`, { params: { week_start } })
export const setWeeklyGoal = (projectId, data) => request.put(`/projects/${projectId}/weekly-goal`, data)
export const listWeeklyGoalItems = (projectId, week_start) => request.get(`/projects/${projectId}/weekly-goal/items`, { params: { week_start } })
export const addWeeklyGoalItem = (projectId, data) => request.post(`/projects/${projectId}/weekly-goal/items`, data)
export const updateWeeklyGoalItem = (id, data) => request.patch(`/weekly-goal-items/${id}`, data)
export const setWeeklyGoalItemDone = (id, done) => request.patch(`/weekly-goal-items/${id}/done`, { done })
export const deleteWeeklyGoalItem = (id) => request.delete(`/weekly-goal-items/${id}`)

// 周报 / 看板
export const projectWeekly = (projectId, week_start) => request.get(`/reports/projects/${projectId}/weekly`, { params: { week_start } })
export const groupWeekly = (view, week_start) => request.get('/reports/group/weekly', { params: { view, week_start } })
export const exportLedger = (week_start, type = 'weekly') => request.get('/reports/group/ledger/export', { params: { week_start, type }, responseType: 'blob' })
export const getBoard = (params) => request.get('/board', { params })

// 通知
export const listNotifications = (params) => request.get('/notifications', { params })
export const markRead = (id) => request.patch(`/notifications/${id}/read`)
export const markAllRead = () => request.post('/notifications/read-all')

// 个人 / AI
export const personalSummary = (userId, params) => request.get(`/personal/${userId}/summary`, { params })
export const getAiSummary = (userId, params) => request.get(`/personal/${userId}/ai-summary`, { params })
export const genAiSummary = (userId, data) => request.post(`/personal/${userId}/ai-summary`, data)
export const editAiSummary = (id, data) => request.put(`/ai-summaries/${id}`, data)

// 附件
export const uploadAttachment = (formData) => request.post('/attachments', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
export const downloadAttachment = (id) => `/api/v1/attachments/${id}/download`

// 用户 / 配置 / 备份 / 导入
export const listUsers = () => request.get('/users')
export const listUserOptions = () => request.get('/users/options')
export const createUser = (data) => request.post('/users', data)
export const updateUser = (id, data) => request.put(`/users/${id}`, data)
export const setUserStatus = (id, status) => request.patch(`/users/${id}/status`, { status })
export const resetPassword = (id, new_password) => request.post(`/users/${id}/reset-password`, { new_password })
export const deleteUser = (id) => request.delete(`/users/${id}`)
export const listConfig = () => request.get('/config')
export const setConfig = (key, value) => request.put(`/config/${key}`, { value })
export const triggerBackup = () => request.post('/backup')
export const listBackups = () => request.get('/backups')
export const importPreview = (formData) => request.post('/import/excel/preview', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
export const importConfirm = (projects) => request.post('/import/excel/confirm', { projects })
