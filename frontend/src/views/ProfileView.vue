<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getUserProfile } from '../api'
import VChart from '../components/VChart.vue'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const userId = ref('U1001')
const profile = ref(null)

// 演示用户快捷入口：覆盖正常用户与各类风险画像
const DEMO_USERS = [
  { id: 'U1009', label: '正常用户', type: 'success' },
  { id: 'U1001', label: '黑名单用户', type: 'danger' },
  { id: 'U1006', label: '顽固退款', type: 'danger' },
  { id: 'U1005', label: '退款狂魔', type: 'warning' },
  { id: 'U1008', label: '投诉惯犯', type: 'warning' },
  { id: 'U1010', label: '多地址用户', type: 'warning' },
  { id: 'U1012', label: '地址共用', type: 'warning' }
]

const statusTagType = (level) => (level === 'high' ? 'danger' : level === 'medium' ? 'warning' : 'success')

const radarOption = computed(() => {
  const metrics = profile.value?.profile_metrics || []
  const max = 100
  return {
    tooltip: {},
    radar: {
      indicator: metrics.map((m) => ({ name: m.label, max })),
      radius: '66%',
      splitLine: { lineStyle: { color: '#e4e9f2' } },
      splitArea: { areaStyle: { color: ['#fbfcfe', '#f5f8fd'] } },
      axisName: { color: '#6b7a99', fontSize: 12 }
    },
    series: [{
      type: 'radar',
      symbolSize: 5,
      lineStyle: { width: 2, color: '#2f6fed' },
      itemStyle: { color: '#2f6fed' },
      areaStyle: { color: 'rgba(47,111,237,.22)' },
      data: [{
        // 归一化到 0-100，便于不同量级指标同图对比
        value: metrics.map((m) => (m.max ? Math.round((m.value / m.max) * max) : 0)),
        name: '风险画像'
      }]
    }]
  }
})

async function load(target) {
  const uid = (target || userId.value || '').trim()
  if (!uid) {
    ElMessage.warning('请输入用户编号')
    return
  }
  userId.value = uid
  loading.value = true
  try {
    profile.value = await getUserProfile(uid)
  } catch {
    profile.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (route.query.user_id) userId.value = String(route.query.user_id)
  load()
})
</script>

<template>
  <div v-loading="loading">
    <div class="tg-card">
      <div class="tg-toolbar" style="margin-bottom:0;">
        <span class="tg-muted" style="font-size:13px;">用户编号：</span>
        <el-input
          v-model="userId"
          placeholder="如 U1001"
          style="width: 200px"
          @keyup.enter="load()"
        />
        <el-button type="primary" @click="load()">查询画像</el-button>
        <div class="spacer"></div>
        <span class="tg-muted" style="font-size:12px;">演示用户：</span>
        <el-button
          v-for="u in DEMO_USERS"
          :key="u.id"
          :type="u.type"
          plain
          size="small"
          @click="load(u.id)"
        >
          {{ u.label }}
        </el-button>
      </div>
    </div>

    <template v-if="profile">
      <!-- 用户基本信息 -->
      <div class="tg-card">
        <div class="tg-card-title">
          <div class="title-left">
            <span class="tg-title-bar"></span>
            {{ profile.username }}（{{ profile.user_id }}）
          </div>
          <el-tag effect="light" size="small">{{ profile.level }}</el-tag>
        </div>
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="用户编号">{{ profile.user_id }}</el-descriptions-item>
          <el-descriptions-item label="手机号">{{ profile.phone || '—' }}</el-descriptions-item>
          <el-descriptions-item label="邮箱">{{ profile.email || '—' }}</el-descriptions-item>
          <el-descriptions-item label="账号等级">{{ profile.level }}</el-descriptions-item>
          <el-descriptions-item label="账号状态">{{ profile.status }}</el-descriptions-item>
          <el-descriptions-item label="注册日期">{{ profile.registered_at }}</el-descriptions-item>
        </el-descriptions>
      </div>

      <div class="tg-stat-grid">
        <div class="tg-stat">
          <div class="tg-stat-label">历史订单数</div>
          <div class="tg-stat-value">{{ profile.summary.total_orders }}<small>单</small></div>
          <div class="tg-stat-foot">累计实付 ¥{{ profile.summary.paid_amount_total }}</div>
        </div>
        <div class="tg-stat" :class="profile.summary.refund_count >= 3 ? 'is-high' : ''">
          <div class="tg-stat-label">退款次数</div>
          <div class="tg-stat-value">{{ profile.summary.refund_count }}<small>次</small></div>
          <div class="tg-stat-foot">退款占比 {{ (profile.summary.refund_ratio * 100).toFixed(1) }}%</div>
        </div>
        <div class="tg-stat" :class="profile.summary.complaint_count >= 3 ? 'is-medium' : ''">
          <div class="tg-stat-label">投诉次数</div>
          <div class="tg-stat-value">{{ profile.summary.complaint_count }}<small>次</small></div>
          <div class="tg-stat-foot">含物流与退款纠纷</div>
        </div>
        <div class="tg-stat">
          <div class="tg-stat-label">收货地址数</div>
          <div class="tg-stat-value">{{ profile.summary.address_count }}<small>个</small></div>
          <div class="tg-stat-foot">近30天登录IP {{ profile.summary.login_ip_count_30d }} 个</div>
        </div>
        <div class="tg-stat" :class="profile.summary.rejected_count > 0 ? 'is-high' : 'is-low'">
          <div class="tg-stat-label">历史拒绝次数</div>
          <div class="tg-stat-value">{{ profile.summary.rejected_count }}<small>次</small></div>
          <div class="tg-stat-foot">风控拒绝处置累计</div>
        </div>
      </div>

      <el-row :gutter="16">
        <el-col :xs="24" :lg="9">
          <div class="tg-card">
            <div class="tg-card-title">
              <div class="title-left"><span class="tg-title-bar"></span>风险画像雷达</div>
            </div>
            <VChart :option="radarOption" height="320px" />
            <div class="tg-muted" style="font-size:12px;text-align:center;">
              各维度按当前用户量级归一化展示，面积越大风险特征越集中
            </div>
          </div>
        </el-col>

        <el-col :xs="24" :lg="15">
          <div class="tg-card">
            <div class="tg-card-title">
              <div class="title-left"><span class="tg-title-bar"></span>最近风险事件</div>
              <span class="tg-muted" style="font-size:12px;">{{ profile.recent_risk_events.length }} 条</span>
            </div>
            <el-table :data="profile.recent_risk_events" size="small" border max-height="320">
              <el-table-column prop="event_id" label="事件" width="70" />
              <el-table-column prop="event_type_label" label="事件类型" width="105" />
              <el-table-column prop="order_id" label="订单" width="138" />
              <el-table-column prop="risk_score" label="评分" width="70" align="center" />
              <el-table-column label="等级" width="86">
                <template #default="{ row }">
                  <span v-if="row.risk_level" class="tg-level" :class="row.risk_level">
                    <i class="tg-dot"></i>{{ row.risk_level_label }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="hit_count" label="命中" width="66" align="center" />
              <el-table-column prop="created_at" label="时间" width="160" />
            </el-table>
            <div v-if="!profile.recent_risk_events.length" class="tg-empty">暂无风险事件</div>
          </div>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :xs="24" :lg="12">
          <div class="tg-card">
            <div class="tg-card-title">
              <div class="title-left"><span class="tg-title-bar"></span>历史订单</div>
              <span class="tg-muted" style="font-size:12px;">最近 {{ profile.recent_orders.length }} 笔</span>
            </div>
            <el-table :data="profile.recent_orders" size="small" border max-height="330">
              <el-table-column prop="order_no" label="订单编号" width="140" />
              <el-table-column prop="category" label="类目" width="90" />
              <el-table-column prop="amount" label="金额" width="90" align="right">
                <template #default="{ row }">¥{{ row.amount }}</template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="86" />
              <el-table-column prop="address_detail" label="收货地址" min-width="180" show-overflow-tooltip />
              <el-table-column prop="created_at" label="下单时间" width="160" />
            </el-table>
          </div>
        </el-col>

        <el-col :xs="24" :lg="12">
          <div class="tg-card">
            <div class="tg-card-title">
              <div class="title-left"><span class="tg-title-bar"></span>关联案件</div>
              <span class="tg-muted" style="font-size:12px;">{{ profile.related_cases.length }} 件</span>
            </div>
            <el-table :data="profile.related_cases" size="small" border max-height="330">
              <el-table-column prop="case_id" label="案件" width="70">
                <template #default="{ row }">
                  <span class="tg-case-link" @click="router.push(`/cases/${row.case_id}`)">#{{ row.case_id }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="order_id" label="关联订单" width="138" />
              <el-table-column label="等级" width="80">
                <template #default="{ row }">
                  <el-tag :type="statusTagType(row.risk_level)" size="small" effect="light">
                    {{ row.risk_level_label }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="case_status_label" label="状态" width="90" />
              <el-table-column prop="reviewer_id" label="审核人" min-width="130">
                <template #default="{ row }">
                  {{ row.reviewer_id || '待分配' }}
                </template>
              </el-table-column>
              <el-table-column prop="created_at" label="创建时间" width="160" />
            </el-table>
            <div v-if="!profile.related_cases.length" class="tg-empty">暂无关联案件</div>
          </div>
        </el-col>
      </el-row>
    </template>
  </div>
</template>
