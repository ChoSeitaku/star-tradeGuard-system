import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({ baseURL: '/api', timeout: 20000 })

// 统一错误提示：后端返回 { detail: "..." }
http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const detail = error?.response?.data?.detail
    const message = Array.isArray(detail)
      ? detail.map((d) => d.msg || JSON.stringify(d)).join('；')
      : detail || error.message || '请求失败，请检查后端服务是否已启动'
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

// ---------------- 基础数据 ----------------
export const getMeta = () => http.get('/risk/meta')
export const getHealth = () => http.get('/health')

// ---------------- 检查模块 ----------------
export const riskCheck = (payload) => http.post('/risk/check', payload)
export const getAssessment = (id) => http.get(`/risk/assessments/${id}`)
export const listEvents = (params) => http.get('/risk/events', { params })

// ---------------- 规则模块 ----------------
export const listRules = (params) => http.get('/risk/rules', { params })
export const createRule = (payload) => http.post('/risk/rules', payload)
export const updateRule = (payload) => http.post('/risk/rules/update', payload)
export const updateRuleStatus = (payload) => http.post('/risk/rules/status', payload)
export const deleteRule = (payload) => http.post('/risk/rules/delete', payload)

// ---------------- 案件模块 ----------------
export const listCases = (params) => http.get('/risk/cases', { params })
export const getCase = (id) => http.get(`/risk/cases/${id}`)
export const reviewCase = (payload) => http.post('/risk/cases/review', payload)

// ---------------- 黑名单模块 ----------------
export const listBlacklists = (params) => http.get('/risk/blacklists', { params })
export const createBlacklist = (payload) => http.post('/risk/blacklists', payload)
export const deleteBlacklist = (payload) => http.post('/risk/blacklists/delete', payload)
export const batchImportBlacklist = (payload) => http.post('/risk/blacklists/batch', payload)

// ---------------- 画像模块 ----------------
export const getUserProfile = (userId) => http.get(`/risk/users/${userId}/profile`)

// ---------------- 统计模块 ----------------
export const getDashboard = (params) => http.get('/risk/dashboard', { params })

export default http
