import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'
import { useUserStore } from '../store/user'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

let refreshing = null // 防止并发刷新

// 请求拦截：携带 token
request.interceptors.request.use((config) => {
  const store = useUserStore()
  if (store.token) {
    config.headers.Authorization = `Bearer ${store.token}`
  }
  return config
})

async function doRefresh() {
  const store = useUserStore()
  if (!store.refreshToken) return null
  try {
    const resp = await axios.post('/api/v1/auth/refresh', { refresh_token: store.refreshToken })
    const data = resp.data?.data
    if (data?.access_token) {
      store.setToken(data.access_token)
      return data.access_token
    }
  } catch { /* refresh 失效 */ }
  return null
}

// 响应拦截：统一处理 { code, message, data } + 401 自动续期
request.interceptors.response.use(
  (response) => {
    const body = response.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 0) return body.data
      ElMessage.error(body.message || '请求失败')
      return Promise.reject(body)
    }
    return body
  },
  async (error) => {
    const { config, response } = error
    const status = response?.status
    // 401 且未重试过：尝试用 refresh_token 续期后重放
    if (status === 401 && config && !config._retried && !config.url.includes('/auth/')) {
      config._retried = true
      if (!refreshing) refreshing = doRefresh()
      const newToken = await refreshing
      refreshing = null
      if (newToken) {
        config.headers.Authorization = `Bearer ${newToken}`
        return request(config) // 重放原请求
      }
    }
    if (status === 401) {
      const store = useUserStore()
      store.logout()
      router.push({ name: 'login' })
      ElMessage.error('登录已过期，请重新登录')
    } else {
      // 422 为参数校验失败，展示 FastAPI detail 具体字段错误
      let msg = response?.data?.message
      const detail = response?.data?.detail
      if (Array.isArray(detail) && detail.length) {
        msg = detail.map((d) => (typeof d === 'string' ? d : d.msg || d.loc?.join('.') || JSON.stringify(d))).join('；')
      }
      ElMessage.error(msg || error.message || '网络错误')
    }
    return Promise.reject(error)
  }
)

export default request
