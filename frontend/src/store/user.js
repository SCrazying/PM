import { defineStore } from 'pinia'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem('pm_token') || '',
    refreshToken: localStorage.getItem('pm_refresh') || '',
    userInfo: JSON.parse(localStorage.getItem('pm_user') || 'null'),
  }),
  getters: {
    isLogin: (s) => !!s.token,
    isAdmin: (s) => s.userInfo?.role === 'admin',
  },
  actions: {
    setLogin(token, refreshToken, userInfo) {
      this.token = token
      this.refreshToken = refreshToken || ''
      this.userInfo = userInfo
      localStorage.setItem('pm_token', token)
      if (refreshToken) localStorage.setItem('pm_refresh', refreshToken)
      localStorage.setItem('pm_user', JSON.stringify(userInfo))
    },
    setToken(token) {
      this.token = token
      localStorage.setItem('pm_token', token)
    },
    logout() {
      this.token = ''
      this.refreshToken = ''
      this.userInfo = null
      localStorage.removeItem('pm_token')
      localStorage.removeItem('pm_refresh')
      localStorage.removeItem('pm_user')
    },
  },
})
