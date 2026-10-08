import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/check' },
  {
    path: '/check',
    name: 'check',
    component: () => import('../views/CheckView.vue'),
    meta: { title: '风险检查', icon: 'Search' }
  },
  {
    path: '/rules',
    name: 'rules',
    component: () => import('../views/RulesView.vue'),
    meta: { title: '规则管理', icon: 'SetUp' }
  },
  {
    path: '/cases',
    name: 'cases',
    component: () => import('../views/CasesView.vue'),
    meta: { title: '案件管理', icon: 'Folder' }
  },
  {
    path: '/cases/:id',
    name: 'case-detail',
    component: () => import('../views/CaseDetailView.vue'),
    meta: { title: '案件详情', hidden: true, activeMenu: '/cases' }
  },
  {
    path: '/blacklist',
    name: 'blacklist',
    component: () => import('../views/BlacklistView.vue'),
    meta: { title: '黑名单管理', icon: 'CircleClose' }
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('../views/ProfileView.vue'),
    meta: { title: '用户画像', icon: 'User' }
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('../views/DashboardView.vue'),
    meta: { title: '运营看板', icon: 'DataLine' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.afterEach((to) => {
  document.title = to.meta?.title
    ? `${to.meta.title} · 电商风险控制系统`
    : '电商风险控制系统 · star-tradeGuard'
})

export default router
