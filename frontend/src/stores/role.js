import { computed, reactive } from 'vue'

/**
 * 角色与操作人（演示环境无真实登录鉴权，通过顶部角色切换器模拟三种角色）。
 * 三种角色的职责见需求 1.2.2：
 *   风控审核员 reviewer —— 查看风险结果、审核案件、填写处理结论
 *   风控管理员 admin    —— 维护规则、维护黑名单、查看统计看板
 *   数据查看人 viewer   —— 查看用户画像、历史风险记录、命中统计
 */
export const ROLES = [
  { value: 'reviewer', label: '风控审核员', desc: '查看风险结果、审核案件、填写处理结论' },
  { value: 'admin', label: '风控管理员', desc: '维护规则、维护黑名单、查看统计看板' },
  { value: 'viewer', label: '数据查看人', desc: '查看用户画像、历史风险记录、命中统计' }
]

const DEFAULT_OPERATOR = {
  reviewer: '风控审核员-王明',
  admin: '风控管理员-系统管理员',
  viewer: '数据查看人-访客'
}

const savedRole = localStorage.getItem('tg_role')
const state = reactive({
  role: ROLES.some((r) => r.value === savedRole) ? savedRole : 'admin',
  operator: localStorage.getItem('tg_operator') || ''
})

export const roleState = state

export const roleLabel = computed(
  () => ROLES.find((r) => r.value === state.role)?.label || '未知角色'
)

export const operatorName = computed(
  () => state.operator || DEFAULT_OPERATOR[state.role] || '未署名'
)

export function setRole(role) {
  if (!ROLES.some((r) => r.value === role)) return
  state.role = role
  state.operator = DEFAULT_OPERATOR[role] || ''
  localStorage.setItem('tg_role', role)
  localStorage.setItem('tg_operator', state.operator)
}

export function setOperator(name) {
  state.operator = name || ''
  localStorage.setItem('tg_operator', state.operator)
}

// 权限判定
export const canSubmitCheck = computed(() => state.role === 'reviewer' || state.role === 'admin')
export const canReviewCase = computed(() => state.role === 'reviewer' || state.role === 'admin')
export const canEditRule = computed(() => state.role === 'admin')
export const canEditBlacklist = computed(() => state.role === 'admin')

export const ROLE_TAG_TYPE = { reviewer: 'warning', admin: 'danger', viewer: 'info' }
