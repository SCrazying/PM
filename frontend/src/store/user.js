import { defineStore } from 'pinia'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem('pm_token') || '',
    userInfo: JSON.parse(localStorage.getItem('pm_user') || 'null'),
  }),
  getters: {
    isLogin: (s) => !!s.token,
    isAdmin: (s) => s.userInfo?.role === 'admin',
  },
  actions: {
    setLogin(token, userInfo) {
      this.token = token
      this.userInfo = userInfo
      localStorage.setItem('pm_token', token)
      localStorage.setItem('pm_user', JSON.stringify(userInfo))
    },
    logout() {
      this.token = ''
      this.userInfo = null
      localStorage.removeItem('pm_token')
      localStorage.removeItem('pm_user')
    },
  },
})
