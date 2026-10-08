<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getMeta, listCases } from '../api'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const statusStat = ref({})
const meta = ref({ case_statuses: [], risk_levels: [] })

const query = reactive({
  case_status: '',
  risk_level: '',
  keyword: '',
  page: 1,
  page_size: 10
})

const statusCards = computed(() =>
  (meta.value.case_statuses || []).map((s) => ({
    ...s,
    count: statusStat.value[s.value] || 0,
    type: s.value === 'resolved' ? 'low' : s.value === 'rejected' ? 'high' : s.value === 'approved' ? 'low' : 'medium'
  }))
)

const statusTagType = (status) => {
  if (status === 'resolved') return 'success'
  if (status === 'approved') return 'success'
  if (status === 'rejected') return 'danger'
  if (status === 'reviewing') return 'warning'
  return 'info'
}

async function load() {
  loading.value = true
  try {
    const data = await listCases({
      page: query.page,
      page_size: query.page_size,
      case_status: query.case_status || undefined,
      risk_level: query.risk_level || undefined,
      keyword: query.keyword || undefined
    })
    rows.value = data.list || []
    total.value = data.total || 0
    statusStat.value = data.status_stat || {}
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  query.case_status = ''
  query.risk_level = ''
  query.keyword = ''
  query.page = 1
  load()
}

function filterByStatus(value) {
  query.case_status = query.case_status === value ? '' : value
  query.page = 1
  load()
}

onMounted(async () => {
  try {
    meta.value = await getMeta()
  } catch { /* 忽略 */ }
  // 支持从其它页面带 order_id 跳转过来
  if (route.query.order_id) query.keyword = String(route.query.order_id)
  load()
})
</script>

<template>
  <div>
    <div class="tg-stat-grid">
      <div
        v-for="card in statusCards"
        :key="card.value"
        class="tg-stat"
        :class="[`is-${card.type}`, { 'is-active': query.case_status === card.value }]"
        style="cursor:pointer;"
        @click="filterByStatus(card.value)"
      >
        <div class="tg-stat-label">{{ card.label }}案件</div>
        <div class="tg-stat-value">{{ card.count }}<small>件</small></div>
        <div class="tg-stat-foot">点击按该状态筛选</div>
      </div>
    </div>

    <div class="tg-card">
      <div class="tg-toolbar">
        <el-select v-model="query.case_status" placeholder="全部案件状态" style="width: 160px" clearable>
          <el-option v-for="s in meta.case_statuses" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-select v-model="query.risk_level" placeholder="全部风险等级" style="width: 150px" clearable>
          <el-option v-for="l in meta.risk_levels" :key="l.value" :label="l.label" :value="l.value" />
        </el-select>
        <el-input
          v-model="query.keyword"
          placeholder="搜索用户 / 订单 / 审核人"
          style="width: 230px"
          clearable
          @keyup.enter="query.page = 1; load()"
        />
        <el-button type="primary" @click="query.page = 1; load()">查询</el-button>
        <el-button @click="resetQuery">重置</el-button>
      </div>

      <el-table v-loading="loading" :data="rows" size="small" border>
        <el-table-column prop="id" label="案件编号" width="92" fixed>
          <template #default="{ row }">
            <span class="tg-mono">#{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="案件状态" width="105">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.case_status)" effect="light" size="small">
              {{ row.case_status_label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="风险等级" width="100">
          <template #default="{ row }">
            <span class="tg-level" :class="row.risk_level">
              <i class="tg-dot"></i>{{ row.risk_level_label }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="risk_score" label="评分" width="72" align="center" />
        <el-table-column prop="event_type_label" label="事件类型" width="105" />
        <el-table-column prop="user_id" label="关联用户" width="100" />
        <el-table-column prop="order_id" label="关联订单" width="140" />
        <el-table-column label="审核人" width="150">
          <template #default="{ row }">
            <span v-if="row.reviewer_id">{{ row.reviewer_id }}</span>
            <span v-else class="tg-muted">待分配</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="165" />
        <el-table-column label="操作" width="92" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click="router.push(`/cases/${row.id}`)">
              查看详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="tg-pagination">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @current-change="load"
          @size-change="query.page = 1; load()"
        />
      </div>
    </div>
  </div>
</template>
