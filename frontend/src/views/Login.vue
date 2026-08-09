<template>
  <div class="login-wrap">
    <div class="login-left">
      <div class="brand">
        <div class="brand-logo">PM</div>
        <h1>项目管理系统</h1>
        <p>替代 Excel · 内置华为 TR 评审流程 · 进展自动汇总周报</p>
        <ul class="feats">
          <li><span class="pm-dot success"></span>项目 → TR节点 → 任务，阶段一目了然</li>
          <li><span class="pm-dot primary"></span>多人协作填报，周报自动生成</li>
          <li><span class="pm-dot warning"></span>项目看板 + 个人绩效 AI 总结</li>
        </ul>
      </div>
    </div>
    <div class="login-right">
      <el-card class="login-card" shadow="never">
        <div class="title">欢迎登录</div>
        <div class="subtitle">内网 · 组内项目协作平台</div>
        <el-form ref="formRef" :model="form" :rules="rules" @keyup.enter="onSubmit">
          <el-form-item prop="username">
            <el-input v-model="form.username" placeholder="用户名" size="large">
              <template #prefix><el-icon><User /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-form-item prop="password">
            <el-input v-model="form.password" type="password" placeholder="密码" size="large" show-password>
              <template #prefix><el-icon><Lock /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-button type="primary" size="large" class="btn" :loading="loading" @click="onSubmit">登 录</el-button>
        </el-form>
        <div class="tip">忘记密码请联系管理员重置</div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '../api/request'
import { useUserStore } from '../store/user'

const router = useRouter()
const route = useRoute()
const store = useUserStore()

const formRef = ref()
const loading = ref(false)
const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function onSubmit() {
  await formRef.value.validate().catch(() => Promise.reject())
  loading.value = true
  try {
    const data = await request.post('/auth/login', form)
    store.setLogin(data.access_token, data.refresh_token, data.user)
    ElMessage.success('登录成功')
    router.push(route.query.redirect || '/')
  } catch (e) { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap { display: flex; height: 100vh; }
.login-left {
  flex: 1.2;
  background: linear-gradient(135deg, #0b2237 0%, #0d2840 45%, #0ea5e9 135%);
  color: #fff;
  display: flex; align-items: center; justify-content: center;
  padding: 40px;
  position: relative;
  overflow: hidden;
}
/* 背景装饰光圈 */
.login-left::before, .login-left::after {
  content: ''; position: absolute; border-radius: 50%;
  background: radial-gradient(circle, rgba(14,165,233,.30) 0%, transparent 70%);
}
.login-left::before { width: 420px; height: 420px; top: -120px; right: -100px; }
.login-left::after { width: 340px; height: 340px; bottom: -120px; left: -90px; background: radial-gradient(circle, rgba(99,102,241,.22) 0%, transparent 70%); }
.brand { max-width: 460px; position: relative; z-index: 1; }
.brand-logo {
  width: 64px; height: 64px; border-radius: 16px;
  background: var(--pm-gradient); backdrop-filter: blur(6px);
  display: flex; align-items: center; justify-content: center;
  font-size: 26px; font-weight: 800; margin-bottom: 24px;
  box-shadow: 0 8px 24px rgba(0,0,0,.28);
}
.brand h1 { font-size: 34px; margin: 0 0 12px; font-weight: 800; letter-spacing: .5px; }
.brand p { font-size: 15px; opacity: .85; margin: 0 0 28px; }
.feats { list-style: none; padding: 0; margin: 0; }
.feats li { display: flex; align-items: center; font-size: 14px; opacity: .92; margin-bottom: 14px; }

.login-right { flex: 1; display: flex; align-items: center; justify-content: center; background: var(--pm-bg); }
.login-card { width: 380px; padding: 14px 8px; border: none; box-shadow: var(--pm-shadow-lg); border-radius: 18px; }
.title { font-size: 24px; font-weight: 800; text-align: center; }
.subtitle { text-align: center; color: var(--pm-text-3); margin: 6px 0 26px; }
.btn { width: 100%; margin-top: 6px; height: 44px; font-size: 16px; letter-spacing: 4px; }
.tip { text-align: center; color: var(--pm-text-3); font-size: 12px; margin-top: 16px; }

@media (max-width: 860px) { .login-left { display: none; } }
</style>
