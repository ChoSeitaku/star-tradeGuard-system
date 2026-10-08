<script setup>
import { computed, onMounted, ref } from 'vue'
import { getDashboard } from '../api'
import VChart from '../components/VChart.vue'

const loading = ref(false)
const data = ref(null)

const LEVEL_COLORS = { high: '#e5484d', medium: '#f5a524', low: '#17a673' }

const overview = computed(() => data.value?.overview || {})

const trendOption = computed(() => {
  const trend = data.value?.trend || []
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['高风险', '中风险', '低风险'], right: 0, top: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10 },
    grid: { left: 42, right: 16, top: 42, bottom: 30 },
    xAxis: {
      type: 'category',
      data: trend.map((t) => t.date.slice(5)),
      axisLine: { lineStyle: { color: '#e4e9f2' } },
      axisLabel: { color: '#6b7a99', fontSize: 11 }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f0f3f9' } },
      axisLabel: { color: '#6b7a99', fontSize: 11 }
    },
    series: [
      {
        name: '高风险', type: 'line', stack: 'total', smooth: true, symbolSize: 6,
        data: trend.map((t) => t.high),
        itemStyle: { color: LEVEL_COLORS.high },
        areaStyle: { color: 'rgba(229,72,77,.18)' }
      },
      {
        name: '中风险', type: 'line', stack: 'total', smooth: true, symbolSize: 6,
        data: trend.map((t) => t.medium),
        itemStyle: { color: LEVEL_COLORS.medium },
        areaStyle: { color: 'rgba(245,165,36,.18)' }
      },
      {
        name: '低风险', type: 'line', stack: 'total', smooth: true, symbolSize: 6,
        data: trend.map((t) => t.low),
        itemStyle: { color: LEVEL_COLORS.low },
        areaStyle: { color: 'rgba(23,166,115,.16)' }
      }
    ]
  }
})

const levelPieOption = computed(() => {
  const stat = data.value?.risk_level_stat || []
  return {
    tooltip: { trigger: 'item', formatter: '{b}：{c} 次（{d}%）' },
    legend: { bottom: 0, icon: 'circle', itemWidth: 9, itemHeight: 9 },
    series: [{
      type: 'pie',
      radius: ['46%', '72%'],
      center: ['50%', '44%'],
      itemStyle: { borderColor: '#fff', borderWidth: 2 },
      label: { formatter: '{b}\n{d}%', fontSize: 11, color: '#6b7a99' },
      data: stat.map((s) => ({
        name: `${s.label}风险`,
        value: s.count,
        itemStyle: { color: LEVEL_COLORS[s.risk_level] }
      }))
    }]
  }
})

const ruleRankOption = computed(() => {
  const rank = [...(data.value?.rule_rank || [])].reverse()
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 8, right: 40, top: 12, bottom: 12, containLabel: true },
    xAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f0f3f9' } },
      axisLabel: { color: '#6b7a99', fontSize: 11 }
    },
    yAxis: {
      type: 'category',
      data: rank.map((r) => r.rule_name),
      axisLine: { lineStyle: { color: '#e4e9f2' } },
      axisLabel: { color: '#1f2b45', fontSize: 11 }
    },
    series: [{
      type: 'bar',
      data: rank.map((r) => r.hit_count),
      barWidth: 13,
      itemStyle: {
        borderRadius: [0, 6, 6, 0],
        color: {
          type: 'linear', x: 0, y: 0, x2: 1, y2: 0,
          colorStops: [{ offset: 0, color: '#7aa7ff' }, { offset: 1, color: '#2f6fed' }]
        }
      },
      label: { show: true, position: 'right', color: '#6b7a99', fontSize: 11 }
    }]
  }
})

const eventTypeOption = computed(() => {
  const stat = data.value?.event_type_stat || []
  return {
    tooltip: { trigger: 'item', formatter: '{b}：{c} 次（{d}%）' },
    legend: { bottom: 0, icon: 'circle', itemWidth: 9, itemHeight: 9 },
    color: ['#2f6fed', '#f5a524', '#e5484d', '#17a673'],
    series: [{
      type: 'pie',
      radius: ['46%', '72%'],
      center: ['50%', '44%'],
      itemStyle: { borderColor: '#fff', borderWidth: 2 },
      label: { formatter: '{b}\n{c}', fontSize: 11, color: '#6b7a99' },
      data: stat.map((s) => ({ name: s.label, value: s.count }))
    }]
  }
})

const caseStatusOption = computed(() => {
  const stat = data.value?.case_status_stat || []
  const colorMap = {
    pending: '#8d9bb5', reviewing: '#f5a524', approved: '#17a673',
    rejected: '#e5484d', resolved: '#2f6fed'
  }
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 8, right: 20, top: 16, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: stat.map((s) => s.label),
      axisLine: { lineStyle: { color: '#e4e9f2' } },
      axisLabel: { color: '#6b7a99', fontSize: 11 }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f0f3f9' } },
      axisLabel: { color: '#6b7a99', fontSize: 11 }
    },
    series: [{
      type: 'bar',
      barWidth: 26,
      data: stat.map((s) => ({ value: s.count, itemStyle: { color: colorMap[s.case_status] || '#2f6fed', borderRadius: [6, 6, 0, 0] } })),
      label: { show: true, position: 'top', color: '#6b7a99', fontSize: 11 }
    }]
  }
})

async function load() {
  loading.value = true
  try {
    data.value = await getDashboard()
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <div class="tg-stat-grid">
      <div class="tg-stat">
        <div class="tg-stat-label">风险事件总数</div>
        <div class="tg-stat-value">{{ overview.total_events }}<small>次</small></div>
        <div class="tg-stat-foot">累计风险检查 {{ overview.total_assessments }} 次</div>
      </div>
      <div class="tg-stat" :class="overview.high_risk_ratio >= 30 ? 'is-high' : 'is-medium'">
        <div class="tg-stat-label">高风险占比</div>
        <div class="tg-stat-value">{{ overview.high_risk_ratio }}<small>%</small></div>
        <div class="tg-stat-foot">高风险 {{ overview.high_risk_count }} 次 · 平均评分 {{ overview.avg_risk_score }}</div>
      </div>
      <div class="tg-stat is-low">
        <div class="tg-stat-label">案件处理效率</div>
        <div class="tg-stat-value">{{ overview.handled_ratio }}<small>%</small></div>
        <div class="tg-stat-foot">
          已处理 {{ overview.handled_cases }} / {{ overview.total_cases }} 件 · 平均 {{ overview.avg_handle_hours }} 小时
        </div>
      </div>
      <div class="tg-stat is-high">
        <div class="tg-stat-label">黑名单命中次数</div>
        <div class="tg-stat-value">{{ overview.blacklist_hit_count }}<small>次</small></div>
        <div class="tg-stat-foot">生效黑名单 {{ overview.active_blacklist_count }} 条</div>
      </div>
      <div class="tg-stat">
        <div class="tg-stat-label">人工审核动作</div>
        <div class="tg-stat-value">{{ overview.review_action_count }}<small>次</small></div>
        <div class="tg-stat-foot">审核与结案留痕累计</div>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="24">
        <div class="tg-card">
          <div class="tg-card-title">
            <div class="title-left"><span class="tg-title-bar"></span>近 7 天风险趋势</div>
            <el-button size="small" text type="primary" @click="load">刷新</el-button>
          </div>
          <VChart :option="trendOption" height="290px" />
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="8">
        <div class="tg-card">
          <div class="tg-card-title">
            <div class="title-left"><span class="tg-title-bar"></span>风险等级分布</div>
          </div>
          <VChart :option="levelPieOption" height="280px" />
        </div>
      </el-col>
      <el-col :xs="24" :lg="8">
        <div class="tg-card">
          <div class="tg-card-title">
            <div class="title-left"><span class="tg-title-bar"></span>业务事件分布</div>
          </div>
          <VChart :option="eventTypeOption" height="280px" />
        </div>
      </el-col>
      <el-col :xs="24" :lg="8">
        <div class="tg-card">
          <div class="tg-card-title">
            <div class="title-left"><span class="tg-title-bar"></span>案件状态分布</div>
          </div>
          <VChart :option="caseStatusOption" height="280px" />
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :xs="24" :lg="14">
        <div class="tg-card">
          <div class="tg-card-title">
            <div class="title-left"><span class="tg-title-bar"></span>规则命中排行 TOP 10</div>
          </div>
          <VChart :option="ruleRankOption" height="340px" />
        </div>
      </el-col>
      <el-col :xs="24" :lg="10">
        <div class="tg-card">
          <div class="tg-card-title">
            <div class="title-left"><span class="tg-title-bar"></span>黑名单命中明细</div>
            <span class="tg-muted" style="font-size:12px;">
              生效 {{ data?.blacklist_stat?.active_count || 0 }} 条
            </span>
          </div>
          <el-table :data="data?.blacklist_stat?.by_rule || []" size="small" border max-height="300">
            <el-table-column prop="rule_name" label="黑名单规则" min-width="150" />
            <el-table-column prop="hit_count" label="命中次数" width="100" align="center">
              <template #default="{ row }">
                <el-tag type="danger" effect="plain" size="small">{{ row.hit_count }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="!(data?.blacklist_stat?.by_rule || []).length" class="tg-empty">
            暂无黑名单命中记录
          </div>

          <div class="tg-dim-title">命中详情排行</div>
          <el-table :data="data?.rule_rank || []" size="small" border max-height="240">
            <el-table-column prop="rule_name" label="规则名称" min-width="140" />
            <el-table-column prop="hit_count" label="命中" width="72" align="center" />
            <el-table-column prop="total_score" label="累计分值" width="90" align="center" />
          </el-table>
        </div>
      </el-col>
    </el-row>

    <div class="tg-muted" style="text-align:right;font-size:12px;">
      统计生成时间：{{ data?.generated_at }}
    </div>
  </div>
</template>
