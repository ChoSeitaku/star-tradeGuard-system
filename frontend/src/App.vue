<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ROLES, ROLE_TAG_TYPE, operatorName, roleLabel,
  roleState, setOperator, setRole
} from './stores/role'

const route = useRoute()
const router = useRouter()

const menuItems = computed(() =>
  router.getRoutes()
    .filter((r) => r.meta?.title && !r.meta?.hidden)
    .map((r) => ({ path: r.path, title: r.meta.title, icon: r.meta.icon }))
)

const activeMenu = computed(() => route.meta?.activeMenu || route.path)
const pageTitle = computed(() => route.meta?.title || '风险检查')

const pageDesc = {
  '/check': '输入业务事件参数，实时返回风险评分、风险等级、命中规则与特征快照',
  '/rules': '维护 24 条风险规则：新增、编辑、启停用、删除与命中统计',
  '/cases': '查看风险案件列表，跟踪审核状态与处理进度',
  '/blacklist': '维护用户 / 地址 / IP 等黑名单，实时作用于风险检查',
  '/profile': '查看用户历史订单、退款投诉、风险事件与关联案件',
  '/dashboard': '风险事件总量、高风险占比、案件处理效率、规则命中排行与趋势'
}

const currentDesc = computed(() => pageDesc[activeMenu.value] || '案件风险结果、命中规则、特征快照与审核记录')

function onRoleChange(value) {
  setRole(value)
  const label = ROLES.find((r) => r.value === value)?.label
  ElMessage.success(`已切换为「${label}」，操作人：${operatorName.value}`)
}
</script>

<template>
  <el-container class="tg-layout">
    <el-aside width="216px" class="tg-aside">
      <div class="tg-logo">
        <div class="tg-logo-mark">TG</div>
        <div class="tg-logo-text">
          <div class="tg-logo-title">电商风险控制</div>
          <div class="tg-logo-sub">star-tradeGuard</div>
        </div>
      </div>

      <el-menu class="tg-menu" :default-active="activeMenu" router>
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>

      <div style="padding: 14px 18px; font-size: 11px; color: rgba(255,255,255,.42); line-height: 1.7;">
        <div>实时风控 · 规则引擎</div>
        <div>25 特征 / 24 规则</div>
      </div>
    </el-aside>

    <el-container>
      <el-header class="tg-header">
        <div class="tg-header-left">
          <span class="tg-page-title">{{ pageTitle }}</span>
          <span class="tg-page-desc">{{ currentDesc }}</span>
        </div>
        <div class="tg-header-right">
          <el-tag :type="ROLE_TAG_TYPE[roleState.role]" effect="light" round>
            {{ roleLabel }}
          </el-tag>
          <el-input
            v-model="roleState.operator"
            size="small"
            style="width: 168px"
            placeholder="操作人姓名"
            @change="setOperator"
          >
            <template #prefix><el-icon><UserFilled /></el-icon></template>
          </el-input>
          <el-select
            :model-value="roleState.role"
            size="small"
            style="width: 132px"
            @change="onRoleChange"
          >
            <el-option v-for="r in ROLES" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
        </div>
      </el-header>

      <el-main class="tg-content">
        <router-view v-slot="{ Component }">
          <keep-alive :max="6">
            <component :is="Component" :key="route.fullPath" />
          </keep-alive>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>
