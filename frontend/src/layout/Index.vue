<template>
  <el-container class="layout">
    <!-- 侧边栏 -->
    <el-aside :width="asideW" class="aside">
      <div class="logo">
        <div class="logo-icon">PM</div>
        <span class="logo-text">项目管理系统</span>
      </div>
      <el-menu :default-active="activeMenu" router class="menu" :collapse="false">
        <el-menu-item index="/board">
          <el-icon><Grid /></el-icon><span>项目看板</span>
        </el-menu-item>
        <el-menu-item index="/projects">
          <el-icon><Folder /></el-icon><span>项目列表</span>
        </el-menu-item>
        <el-menu-item index="/weekly">
          <el-icon><DataAnalysis /></el-icon><span>周会视图</span>
        </el-menu-item>
        <el-menu-item index="/workbench">
          <el-icon><Monitor /></el-icon><span>工作台</span>
        </el-menu-item>
        <el-menu-item index="/personal">
          <el-icon><User /></el-icon><span>个人绩效</span>
        </el-menu-item>
        <el-menu-item v-if="store.isAdmin" index="/admin">
          <el-icon><Setting /></el-icon><span>系统管理</span>
        </el-menu-item>
      </el-menu>
      <div class="aside-footer">v0.3 · 内网版</div>
    </el-aside>

    <el-container class="right">
      <!-- 顶栏 -->
      <el-header class="header">
        <div class="crumb">
          <span class="crumb-title">{{ route.meta.title || '工作台' }}</span>
        </div>
        <div class="header-right">
          <el-tooltip content="通知" placement="bottom">
            <el-badge :value="unread" :hidden="!unread" class="bell" @click="goNotifications">
              <el-icon :size="18"><Bell /></el-icon>
            </el-badge>
          </el-tooltip>
          <el-dropdown @command="onCommand">
            <span class="user">
              <span class="avatar">{{ avatarText }}</span>
              <span class="uname">{{ store.userInfo?.display_name || '用户' }}</span>
              <el-icon class="caret"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>{{ store.userInfo?.username }}</el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 主内容 -->
      <el-main class="main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../store/user'
import request from '../api/request'

const route = useRoute()
const router = useRouter()
const store = useUserStore()
const asideW = '232px'
const unread = ref(0)

const activeMenu = computed(() => {
  if (route.path.startsWith('/projects')) return '/projects'
  return route.path
})
const avatarText = computed(() => (store.userInfo?.display_name || 'U').slice(0, 1))

function onCommand(cmd) {
  if (cmd === 'logout') {
    store.logout()
    router.push({ name: 'login' })
  }
}
function goNotifications() { router.push({ name: 'workbench' }) }

async function loadUnread() {
  try {
    const list = await request.get('/notifications', { params: { is_read: false } })
    unread.value = Array.isArray(list) ? list.length : 0
  } catch { unread.value = 0 }
}
onMounted(loadUnread)
</script>

<style scoped>
.layout { height: 100vh; }

/* 侧边栏：深青墨绿渐变，与青绿主色呼应 */
.aside {
  background: linear-gradient(180deg, #10312f 0%, #0c2422 100%);
  display: flex;
  flex-direction: column;
  transition: width .2s;
}
.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 60px;
  padding: 0 18px;
  border-bottom: 1px solid rgba(255,255,255,.07);
}
.logo-icon {
  width: 34px; height: 34px; border-radius: 9px;
  background: var(--pm-gradient);
  color: #fff; font-weight: 800; font-size: 14px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 12px rgba(20,184,166,.4);
}
.logo-text { color: #fff; font-size: 17px; font-weight: 700; letter-spacing: .5px; }

.menu {
  border-right: none;
  background: transparent;
  padding: 12px 10px;
  flex: 1;
}
.menu :deep(.el-menu-item) {
  color: #9db8b5;
  border-radius: 8px;
  margin-bottom: 4px;
  height: 46px;
  line-height: 46px;
}
.menu :deep(.el-menu-item:hover) {
  background: rgba(255,255,255,.07);
  color: #fff;
}
.menu :deep(.el-menu-item.is-active) {
  background: var(--pm-gradient);
  color: #fff;
  box-shadow: 0 4px 12px rgba(20,184,166,.35);
}
.aside-footer {
  padding: 14px 18px;
  color: rgba(255,255,255,.35);
  font-size: 12px;
  border-top: 1px solid rgba(255,255,255,.07);
}

/* 顶栏 */
.right { background: var(--pm-bg); }
.header {
  height: var(--pm-header-h);
  background: rgba(255,255,255,.8);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--pm-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}
.crumb-title { font-size: 17px; font-weight: 700; color: var(--pm-text); }
.header-right { display: flex; align-items: center; gap: 20px; }
.bell { cursor: pointer; color: var(--pm-text-2); display: flex; }
.user { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.avatar {
  width: 32px; height: 32px; border-radius: 50%;
  background: var(--pm-gradient); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 700;
}
.uname { font-size: 14px; color: var(--pm-text); font-weight: 600; }
.caret { color: var(--pm-text-3); font-size: 12px; }

.main { padding: 18px 20px; overflow-y: auto; }

/* 过渡 */
.fade-enter-active, .fade-leave-active { transition: opacity .15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
