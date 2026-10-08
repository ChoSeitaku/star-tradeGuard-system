<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getCase, getMeta, reviewCase } from '../api'
import { canReviewCase, operatorName } from '../stores/role'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const submitting = ref(false)
const detail = ref(null)
const meta = ref({ features: [], dimensions: [] })

const reviewForm = reactive({
  review_result: 'reject',
  review_remark: ''
})

const REVIEW_OPTIONS = [
  { value: 'approve', label: '审核通过（放行）', desc: '核实为正常交易，解除风险' },
  { value: 'reject', label: '审核拒绝（拦截）', desc: '确认为风险交易，拒绝处置' },
  { value: 'resolve', label: '结案归档', desc: '处置完成，关闭案件' }
]

const assessment = computed(() => detail.value?.assessment || null)

const groupedSnapshot = computed(() => {
  const snap = assessment.value?.feature_snapshot || {}
  const groups = {}
  for (const f of meta.value.features || []) {
    if (!groups[f.dimension]) groups[f.dimension] = { key: f.dimension, items: [] }
    groups[f.dimension].items.push({
      key: f.feature_key,
      label: f.feature_name,
      value: snap[f.feature_key],
      hit: snap[f.feature_key] === 1 && /blacklisted|first_order|is_new/.test(f.feature_key)
    })
  }
  const order = ['user', 'order', 'address', 'event']
  return order.filter((d) => groups[d]).map((d) => ({
    ...groups[d],
    label: (meta.value.dimensions || []).find((x) => x.value === d)?.label || d
  }))
})

const statusTagType = (status) => {
  if (status === 'resolved' || status === 'approved') return 'success'
  if (status === 'rejected') return 'danger'
  if (status === 'reviewing') return 'warning'
  return 'info'
}

const timelineType = (action) => {
  if (action === 'create') return 'primary'
  if (action === 'resolve') return 'success'
  return 'warning'
}

const canSubmit = computed(() =>
  canReviewCase.value && detail.value && detail.value.case_status !== 'resolved')

async function load() {
  loading.value = true
  try {
    detail.value = await getCase(route.params.id)
  } finally {
    loading.value = false
  }
}

async function submitReview() {
  if (!reviewForm.review_remark.trim()) {
    ElMessage.warning('请填写审核备注')
    return
  }
  submitting.value = true
  try {
    const res = await reviewCase({
      case_id: Number(route.params.id),
      review_result: reviewForm.review_result,
      review_remark: reviewForm.review_remark,
      reviewer_id: operatorName.value
    })
    ElMessage.success(res.message)
    reviewForm.review_remark = ''
    load()
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    meta.value = await getMeta()
  } catch { /* 忽略 */ }
  load()
})
</script>

<template>
  <div v-loading="loading">
    <div class="tg-toolbar">
      <el-button text @click="router.push('/cases')">
        <el-icon style="margin-right:4px"><ArrowLeft /></el-icon>返回案件列表
      </el-button>
      <div class="spacer"></div>
      <el-button
        v-if="detail"
        text
        type="primary"
        @click="router.push({ path: '/profile', query: { user_id: detail.user_id } })"
      >
        查看用户画像
      </el-button>
    </div>

    <template v-if="detail">
      <!-- 案件概要 -->
      <div class="tg-card">
        <div class="tg-card-title">
          <div class="title-left"><span class="tg-title-bar"></span>案件概要</div>
          <el-tag :type="statusTagType(detail.case_status)" effect="dark">
            {{ detail.case_status_label }}
          </el-tag>
        </div>

        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="案件编号">
            <span class="tg-mono">#{{ detail.case_id }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="关联用户">{{ detail.user_id }}</el-descriptions-item>
          <el-descriptions-item label="关联订单">{{ detail.order_id }}</el-descriptions-item>
          <el-descriptions-item label="用户名称">
            {{ detail.user_info?.username || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="风险评分">{{ assessment?.risk_score }}</el-descriptions-item>
          <el-descriptions-item label="风险等级">
            <span class="tg-level" :class="assessment?.risk_level">
              <i class="tg-dot"></i>{{ assessment?.risk_level_label }}风险
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="处理建议">{{ assessment?.decision_label }}</el-descriptions-item>
          <el-descriptions-item label="审核人">{{ detail.reviewer_id || '待分配' }}</el-descriptions-item>
          <el-descriptions-item label="审核结论">{{ detail.review_result_label || '—' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ detail.created_at }}</el-descriptions-item>
          <el-descriptions-item label="更新时间" :span="2">{{ detail.updated_at }}</el-descriptions-item>
        </el-descriptions>
      </div>

      <el-row :gutter="16">
        <!-- 左：风险结果 -->
        <el-col :xs="24" :lg="15">
          <div class="tg-card">
            <div class="tg-card-title">
              <div class="title-left"><span class="tg-title-bar"></span>风险结果与命中规则</div>
              <span class="tg-muted tg-mono" style="font-size:12px;">
                评估编号 #{{ assessment?.assessment_id }} · {{ assessment?.created_at }}
              </span>
            </div>

            <el-table :data="assessment?.rule_hits || []" size="small" border>
              <el-table-column prop="rule_code" label="规则编码" width="205" />
              <el-table-column prop="rule_name" label="规则名称" width="165" />
              <el-table-column prop="hit_score" label="分值" width="76" align="center">
                <template #default="{ row }">
                  <el-tag type="danger" effect="plain" size="small">+{{ row.hit_score }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="hit_message" label="命中原因" min-width="280" show-overflow-tooltip />
            </el-table>
            <div v-if="!(assessment?.rule_hits || []).length" class="tg-empty">未命中任何风险规则</div>
          </div>

          <!-- 特征快照 -->
          <div class="tg-card">
            <div class="tg-card-title">
              <div class="title-left"><span class="tg-title-bar"></span>特征快照</div>
              <span class="tg-muted" style="font-size:12px;">
                共 {{ Object.keys(assessment?.feature_snapshot || {}).length }} 项
              </span>
            </div>
            <div v-for="group in groupedSnapshot" :key="group.key">
              <div class="tg-muted" style="font-size:12px;margin:8px 0 6px;">{{ group.label }}</div>
              <div class="tg-kv-grid">
                <div v-for="item in group.items" :key="item.key" class="tg-kv">
                  <span class="k">{{ item.label }}</span>
                  <span class="v" :class="{ hit: item.hit }">
                    {{ item.value === null || item.value === undefined ? '—' : item.value }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </el-col>

        <!-- 右：审核操作与日志 -->
        <el-col :xs="24" :lg="9">
          <div class="tg-card">
            <div class="tg-card-title">
              <div class="title-left"><span class="tg-title-bar"></span>人工审核</div>
            </div>

            <el-alert
              v-if="!canReviewCase"
              style="margin-bottom:12px;"
              type="info" :closable="false" show-icon
              title="当前角色无审核权限（仅「风控审核员」「风控管理员」可提交审核结论）"
            />
            <el-alert
              v-else-if="detail.case_status === 'resolved'"
              style="margin-bottom:12px;"
              type="success" :closable="false" show-icon
              title="该案件已结案，不可重复处理"
            />

            <el-form :model="reviewForm" label-position="top">
              <el-form-item label="审核结论">
                <el-radio-group v-model="reviewForm.review_result" :disabled="!canSubmit">
                  <el-radio v-for="opt in REVIEW_OPTIONS" :key="opt.value" :value="opt.value" border>
                    {{ opt.label }}
                  </el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item label="审核备注">
                <el-input
                  v-model="reviewForm.review_remark"
                  type="textarea"
                  :rows="3"
                  :disabled="!canSubmit"
                  placeholder="请填写处理结论与依据，例如：确认为黑名单用户，拒绝交易"
                />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="submitting" :disabled="!canSubmit" @click="submitReview">
                  提交审核结论
                </el-button>
              </el-form-item>
            </el-form>
          </div>

          <div class="tg-card">
            <div class="tg-card-title">
              <div class="title-left"><span class="tg-title-bar"></span>审核记录</div>
              <span class="tg-muted" style="font-size:12px;">{{ detail.review_logs.length }} 条</span>
            </div>
            <el-timeline>
              <el-timeline-item
                v-for="log in [...detail.review_logs].reverse()"
                :key="log.id"
                :type="timelineType(log.action_type)"
                :timestamp="log.created_at"
                placement="top"
              >
                <div style="font-weight:600;font-size:13px;">
                  {{ log.action_type_label }}
                  <span class="tg-muted" style="font-weight:400;">· {{ log.operator_id }}</span>
                </div>
                <div class="tg-muted" style="font-size:12px;margin-top:4px;line-height:1.6;">
                  {{ log.action_remark }}
                </div>
              </el-timeline-item>
            </el-timeline>
          </div>
        </el-col>
      </el-row>
    </template>
  </div>
</template>
