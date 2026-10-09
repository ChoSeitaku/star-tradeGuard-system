<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getMeta, listEvents, regenerateAiExplanation, riskCheck } from '../api'
import { canSubmitCheck, operatorName } from '../stores/role'
import VChart from '../components/VChart.vue'

const router = useRouter()

const form = reactive({
  event_type: 'order_create',
  source_id: 'web_console',
  user_id: 'U1001',
  order_id: 'SO202400101'
})

const meta = ref({ event_types: [], features: [], dimensions: [], score_model: {} })
const loading = ref(false)
const result = ref(null)
const aiLoading = ref(false)
const recent = ref([])

// 演示场景快捷入口，覆盖 4 类业务事件与高中低三档风险
const PRESETS = [
  { label: '正常下单（低风险放行）', type: 'success', data: { event_type: 'order_create', user_id: 'U1009', order_id: 'SO202400901' } },
  { label: '黑名单用户大额下单（高风险）', type: 'danger', data: { event_type: 'order_create', user_id: 'U1001', order_id: 'SO202400101' } },
  { label: '深夜大额支付（高风险）', type: 'danger', data: { event_type: 'order_pay', user_id: 'U1003', order_id: 'SO202400301' } },
  { label: '售后退款异常（中风险）', type: 'warning', data: { event_type: 'after_sale_apply', user_id: 'U1005', order_id: 'SO202400501' } },
  { label: '物流投诉惯犯（中风险）', type: 'warning', data: { event_type: 'logistics_complaint', user_id: 'U1007', order_id: 'SO202400701' } }
]

const featureLabel = computed(() => {
  const map = {}
  for (const f of meta.value.features || []) map[f.feature_key] = f
  return map
})

const groupedSnapshot = computed(() => {
  if (!result.value) return []
  const snap = result.value.feature_snapshot || {}
  const groups = {}
  for (const f of meta.value.features || []) {
    const dim = f.dimension
    if (!groups[dim]) groups[dim] = { key: dim, items: [] }
    groups[dim].items.push({
      key: f.feature_key,
      label: f.feature_name,
      value: snap[f.feature_key],
      // 布尔/命中类特征高亮显示
      hit: snap[f.feature_key] === 1 && /blacklisted|first_order|is_new/.test(f.feature_key)
    })
  }
  const order = ['user', 'order', 'address', 'event']
  return order.filter((d) => groups[d]).map((d) => ({
    ...groups[d],
    label: (meta.value.dimensions || []).find((x) => x.value === d)?.label || d
  }))
})

const gaugeOption = computed(() => {
  const score = result.value?.risk_score ?? 0
  const level = result.value?.risk_level || 'low'
  const color = level === 'high' ? '#e5484d' : level === 'medium' ? '#f5a524' : '#17a673'
  return {
    series: [{
      type: 'gauge',
      startAngle: 210,
      endAngle: -30,
      min: 0,
      max: 100,
      radius: '96%',
      center: ['50%', '58%'],
      progress: { show: true, width: 14, itemStyle: { color } },
      axisLine: { lineStyle: { width: 14, color: [[0.3, '#e6f7f1'], [0.7, '#fdf3e2'], [1, '#fdeaea']] } },
      pointer: { width: 4, length: '62%', itemStyle: { color } },
      axisTick: { show: false },
      splitLine: { length: 10, lineStyle: { color: '#c9d3e3', width: 1 } },
      axisLabel: { distance: 14, fontSize: 10, color: '#8d9bb5' },
      anchor: { show: true, size: 8, itemStyle: { color } },
      title: { show: true, offsetCenter: [0, '32%'], fontSize: 12, color: '#6b7a99' },
      detail: {
        valueAnimation: true,
        offsetCenter: [0, '4%'],
        fontSize: 40,
        fontWeight: 'bold',
        color,
        formatter: '{value}'
      },
      data: [{ value: score, name: '风险评分' }]
    }]
  }
})

const levelTagType = (lv) => (lv === 'high' ? 'danger' : lv === 'medium' ? 'warning' : 'success')

function fill(preset) {
  Object.assign(form, preset.data)
  result.value = null
}

async function submit() {
  if (!form.user_id && !form.order_id) {
    ElMessage.warning('用户编号与订单编号至少填写一个')
    return
  }
  loading.value = true
  try {
    result.value = await riskCheck({ ...form })
    ElMessage.success(result.value.message || '风险检查完成')
    loadRecent()
  } finally {
    loading.value = false
  }
}

// 重新调用大模型生成风险解读（GET 默认复用首次落库结果）
async function regenerateAi() {
  if (!result.value?.assessment_id) return
  aiLoading.value = true
  try {
    result.value = await regenerateAiExplanation(result.value.assessment_id)
    ElMessage.success('AI 风险解读已更新')
  } finally {
    aiLoading.value = false
  }
}

async function loadRecent() {
  try {
    const data = await listEvents({ page: 1, page_size: 8 })
    recent.value = data.list || []
  } catch { /* 忽略列表加载失败 */ }
}

onMounted(async () => {
  try {
    meta.value = await getMeta()
  } catch { /* 忽略 */ }
  loadRecent()
})
</script>

<template>
  <div>
    <!-- 检查表单 -->
    <div class="tg-card">
      <div class="tg-card-title">
        <div class="title-left"><span class="tg-title-bar"></span>风险检查入参</div>
        <span class="tg-muted" style="font-size:12px;">
          评分规则：命中规则分值累加，≥70 高风险，≥30 中风险，其余低风险
        </span>
      </div>

      <el-form :model="form" label-width="86px" inline>
        <el-form-item label="事件类型">
          <el-select v-model="form.event_type" style="width: 168px">
            <el-option v-for="t in meta.event_types" :key="t.value" :label="`${t.label}（${t.value}）`" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源标识">
          <el-input v-model="form.source_id" style="width: 168px" placeholder="source_id" />
        </el-form-item>
        <el-form-item label="用户编号">
          <el-input v-model="form.user_id" style="width: 150px" placeholder="如 U1001" />
        </el-form-item>
        <el-form-item label="订单编号">
          <el-input v-model="form.order_id" style="width: 176px" placeholder="如 SO202400101" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" :disabled="!canSubmitCheck" @click="submit">
            <el-icon style="margin-right:4px"><Search /></el-icon>发起风险检查
          </el-button>
        </el-form-item>
      </el-form>

      <div class="tg-muted" style="font-size:12px;margin-bottom:8px;">演示场景快捷填充：</div>
      <div style="display:flex;flex-wrap:wrap;gap:8px;">
        <el-button v-for="p in PRESETS" :key="p.label" :type="p.type" plain size="small" @click="fill(p)">
          {{ p.label }}
        </el-button>
      </div>
      <el-alert
        v-if="!canSubmitCheck"
        style="margin-top:12px;"
        type="info" :closable="false" show-icon
        title="当前角色为「数据查看人」，仅可查看结果，无法发起风险检查"
      />
    </div>

    <!-- 检查结果 -->
    <div v-if="result" class="tg-card">
      <div class="tg-card-title">
        <div class="title-left"><span class="tg-title-bar"></span>风险检查结果</div>
        <span class="tg-muted tg-mono" style="font-size:12px;">
          评估编号 #{{ result.assessment_id }} · 事件编号 #{{ result.event_id }} · {{ result.created_at }}
        </span>
      </div>

      <div class="tg-result-head">
        <div class="tg-score-panel">
          <VChart :option="gaugeOption" height="200px" />
        </div>
        <div>
          <div class="tg-decision-row">
            <div class="tg-decision-item">
              <div class="k">风险等级</div>
              <div class="v">
                <span class="tg-level" :class="result.risk_level">
                  <i class="tg-dot"></i>{{ result.risk_level_label }}风险
                </span>
              </div>
            </div>
            <div class="tg-decision-item">
              <div class="k">处理建议</div>
              <div class="v">
                <el-tag :type="levelTagType(result.risk_level)" effect="dark" size="large">
                  {{ result.decision_label }}
                </el-tag>
              </div>
            </div>
            <div class="tg-decision-item">
              <div class="k">命中规则数</div>
              <div class="v">{{ result.hit_count }} 条</div>
            </div>
            <div class="tg-decision-item">
              <div class="k">自动建案</div>
              <div class="v">
                <span v-if="result.case_id" class="tg-case-link" @click="router.push(`/cases/${result.case_id}`)">
                  案件 #{{ result.case_id }}（{{ result.case_status_label }}）
                </span>
                <span v-else class="tg-muted">未触发建案</span>
              </div>
            </div>
          </div>

          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="事件类型">{{ result.event_type_label }}</el-descriptions-item>
            <el-descriptions-item label="来源标识">{{ result.source_id }}</el-descriptions-item>
            <el-descriptions-item label="用户编号">{{ result.user_id || '—' }}</el-descriptions-item>
            <el-descriptions-item label="订单编号">{{ result.order_id || '—' }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>

      <!-- AI 风险解读（大模型基于规则引擎结论生成，仅辅助解读，不改变评分与决策） -->
      <div class="tg-dim-title">
        AI 风险解读
        <span class="tg-muted" style="font-weight:400;margin-left:8px;">
          <template v-if="result.ai_provider === 'deepseek'">
            来源：大模型 {{ result.ai_model }} · 生成于 {{ result.ai_generated_at }}
          </template>
          <template v-else-if="result.ai_provider">来源：规则模板（未启用大模型）</template>
        </span>
        <el-button
          v-if="result.ai_provider"
          size="small" text type="primary"
          style="float:right;margin-top:-4px;"
          :loading="aiLoading" @click="regenerateAi"
        >重新生成解读</el-button>
      </div>
      <div v-if="result.ai_explanation" class="tg-ai-panel">
        <div class="tg-ai-summary">
          <el-icon style="margin-right:6px;vertical-align:-2px;"><MagicStick /></el-icon>
          {{ result.ai_explanation.summary }}
        </div>
        <div v-if="(result.ai_explanation.key_factors || []).length" class="tg-ai-block">
          <div class="tg-ai-label">关键风险点</div>
          <ul class="tg-ai-list">
            <li v-for="(factor, i) in result.ai_explanation.key_factors" :key="i">{{ factor }}</li>
          </ul>
        </div>
        <div v-if="(result.ai_explanation.handling_steps || []).length" class="tg-ai-block">
          <div class="tg-ai-label">处置建议</div>
          <ol class="tg-ai-list">
            <li v-for="(step, i) in result.ai_explanation.handling_steps" :key="i">{{ step }}</li>
          </ol>
        </div>
        <div v-if="result.ai_explanation.risk_note" class="tg-ai-note">
          {{ result.ai_explanation.risk_note }}
        </div>
      </div>
      <div v-else class="tg-empty">暂无 AI 解读（历史评估数据，可点击上方按钮重新生成）</div>

      <!-- 命中规则 -->
      <div class="tg-dim-title">命中规则（{{ result.hit_count }} 条）</div>
      <el-table v-if="result.rule_hits.length" :data="result.rule_hits" size="small" border>
        <el-table-column prop="rule_code" label="规则编码" width="210" />
        <el-table-column prop="rule_name" label="规则名称" width="180" />
        <el-table-column prop="hit_score" label="命中分值" width="90" align="center">
          <template #default="{ row }">
            <el-tag type="danger" effect="plain" size="small">+{{ row.hit_score }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="hit_message" label="命中原因" min-width="320" show-overflow-tooltip />
      </el-table>
      <div v-else class="tg-empty">未命中任何风险规则，风险评分为 0</div>

      <!-- 特征快照 -->
      <div class="tg-dim-title">特征快照（共 {{ Object.keys(result.feature_snapshot || {}).length }} 项）</div>
      <div v-for="group in groupedSnapshot" :key="group.key">
        <div class="tg-muted" style="font-size:12px;margin:10px 0 6px;">{{ group.label }}</div>
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

    <!-- 最近风险事件 -->
    <div class="tg-card">
      <div class="tg-card-title">
        <div class="title-left"><span class="tg-title-bar"></span>最近风险事件</div>
        <el-button size="small" text type="primary" @click="loadRecent">刷新</el-button>
      </div>
      <el-table :data="recent" size="small" border>
        <el-table-column prop="id" label="事件编号" width="90" />
        <el-table-column prop="event_type_label" label="事件类型" width="110" />
        <el-table-column prop="user_id" label="用户" width="100" />
        <el-table-column prop="order_id" label="订单" width="140" />
        <el-table-column label="风险评分" width="100" align="center">
          <template #default="{ row }">
            <span v-if="row.risk_score !== null">{{ row.risk_score }}</span>
            <span v-else class="tg-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="风险等级" width="110">
          <template #default="{ row }">
            <span v-if="row.risk_level" class="tg-level" :class="row.risk_level">
              <i class="tg-dot"></i>{{ row.risk_level_label }}
            </span>
            <span v-else class="tg-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="decision_label" label="处理建议" width="110" />
        <el-table-column prop="source_id" label="来源" min-width="130" />
        <el-table-column prop="created_at" label="创建时间" width="170" />
      </el-table>
      <div v-if="!recent.length" class="tg-empty">暂无风险事件记录</div>
    </div>
  </div>
</template>
