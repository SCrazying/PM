import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '../store/user'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/Login.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/',
    component: () => import('../layout/Index.vue'),
    redirect: '/board',
    children: [
      { path: 'board', name: 'board', component: () => import('../views/Board.vue'), meta: { title: '项目看板' } },
      { path: 'projects', name: 'projects', component: () => import('../views/ProjectList.vue'), meta: { title: '项目列表' } },
      { path: 'projects/:id', name: 'project-detail', component: () => import('../views/ProjectDetail.vue'), meta: { title: '项目详情' } },
      { path: 'weekly', name: 'weekly', component: () => import('../views/WeeklyMeeting.vue'), meta: { title: '周会视图' } },
      { path: 'workbench', name: 'workbench', component: () => import('../views/Workbench.vue'), meta: { title: '工作台' } },
      { path: 'personal', name: 'personal', component: () => import('../views/Personal.vue'), meta: { title: '个人绩效' } },
      { path: 'admin', name: 'admin', component: () => import('../views/Admin.vue'), meta: { title: '系统管理', admin: true } },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const store = useUserStore()
  if (to.meta.public) return true
  if (!store.isLogin) return { name: 'login', query: { redirect: to.fullPath } }
  if (to.meta.admin && !store.isAdmin) return { name: 'board' }
  document.title = to.meta.title ? `${to.meta.title} · 项目管理系统` : '项目管理系统'
  return true
})

export default router
