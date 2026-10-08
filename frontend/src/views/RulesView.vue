<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createRule, deleteRule, listRules, updateRule, updateRuleStatus } from '../api'
import { canEditRule } from '../stores/role'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const operators = ref([])
const features = ref([])

const query = reactive({ keyword: '', rule_status: '', page: 1, page_size: 20 })

const dialogVisible = ref(false)
const dialogMode = ref('create')
const saving = ref(false)

const blankLeaf = () => ({ op: 'gte', feature: 'order_amount', value: '' })
const blankForm = () => ({
  id: null,
  rule_code: '',
  rule_name: '',
  rule_status: 'enabled',
  priority: 100,
  score: 10,
  description: '',
  allLeaves: [blankLeaf()],
  anyLeaves: []
})

const form = reactive(blankForm())

const featureOptions = computed(() =>
  features.value.map((f) => ({ value: f.feature_key, label: `${f.feature_name}（${f.feature_key}）` }))
)

async function load() {
  loading.value = true
  try {
    const data = await listRules({
      keyword: query.keyword || undefined,
      rule_status: query.rule_status || undefined
    })
    rows.value = data.list || []
    total.value = data.total || 0
    operators.value = data.operators || []
    features.value = data.features || []
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  query.keyword = ''
  query.rule_status = ''
  load()
}

/** 把 condition_json 渲染成可读文本 */
function formatCondition(condition) {
  if (!condition) return '—'
  const render = (node) => {
    if (Array.isArray(node)) return node.map(render).join(' 且 ')
    if (!node || typeof node !== 'object') return ''
    if (node.feature) {
      const opLabel = operators.value.find((o) => o.op === node.op)?.label || node.op
      const value = Array.isArray(node.value) ? `[${node.value.join('、')}]` : node.value
      return `${node.feature} ${opLabel} ${value}`
    }
    const parts = []
    if (node.all) parts.push(render(node.all))
    if (node.any) {
      const g = node.any
      parts.push(`（${(Array.isArray(g) ? g : [g]).map(render).join(' 或 ')}）`)
    }
    return parts.filter(Boolean).join(' 且 ')
  }
  return render(condition) || '—'
}

function coerceValue(op, raw) {
  if (op === 'contains') {
    return String(raw)
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean)
  }
  const text = String(raw).trim()
  if (text !== '' && !Number.isNaN(Number(text))) return Number(text)
  return text
}

function buildCondition() {
  const build = (leaves) =>
    leaves
      .filter((l) => l.feature && String(l.value).trim() !== '')
      .map((l) => ({ op: l.op, feature: l.feature, value: coerceValue(l.op, l.value) }))

  const all = build(form.allLeaves)
  const any = build(form.anyLeaves)
  if (!all.length && !any.length) {
    ElMessage.warning('请至少配置一个有效的规则条件')
    return null
  }
  const condition = {}
  if (all.length) condition.all = all
  if (any.length) condition.any = any
  return condition
}

function openCreate() {
  Object.assign(form, blankForm())
  dialogMode.value = 'create'
  dialogVisible.value = true
}

function openEdit(row) {
  const condition = row.condition || {}
  const toLeaves = (group) =>
    (Array.isArray(group) ? group : []).map((l) => ({
      op: l.op,
      feature: l.feature,
      value: Array.isArray(l.value) ? l.value.join(',') : String(l.value ?? '')
    }))

  Object.assign(form, {
    id: row.id,
    rule_code: row.rule_code,
    rule_name: row.rule_name,
    rule_status: row.rule_status,
    priority: row.priority,
    score: row.score,
    description: row.description || '',
    allLeaves: toLeaves(condition.all).length ? toLeaves(condition.all) : [blankLeaf()],
    anyLeaves: toLeaves(condition.any)
  })
  dialogMode.value = 'edit'
  dialogVisible.value = true
}

async function save() {
  if (!form.rule_code || !form.rule_name) {
    ElMessage.warning('规则编码与规则名称为必填项')
    return
  }
  const condition = buildCondition()
  if (!condition) return

  const payload = {
    rule_code: form.rule_code,
    rule_name: form.rule_name,
    rule_status: form.rule_status,
    priority: Number(form.priority),
    score: Number(form.score),
    condition_json: condition,
    description: form.description
  }
  saving.value = true
  try {
    if (dialogMode.value === 'create') {
      await createRule(payload)
      ElMessage.success('规则创建成功')
    } else {
      await updateRule({ ...payload, id: form.id })
      ElMessage.success('规则更新成功')
    }
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function toggleStatus(row) {
  const next = row.rule_status === 'enabled' ? 'disabled' : 'enabled'
  try {
    const res = await updateRuleStatus({ id: row.id, rule_status: next })
    row.rule_status = next
    ElMessage.success(res.message)
  } catch {
    load()
  }
}

async function remove(row) {
  await ElMessageBox.confirm(
    `确认删除规则「${row.rule_name}」？删除后历史命中记录会保留作为留痕。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
  )
  const res = await deleteRule({ id: row.id })
  ElMessage.success(res.message)
  load()
}

onMounted(load)
</script>

<template>
  <div>
    <div class="tg-card">
      <div class="tg-toolbar">
        <el-input v-model="query.keyword" placeholder="搜索规则名称 / 编码" style="width: 240px" clearable @keyup.enter="load" />
        <el-select v-model="query.rule_status" placeholder="全部状态" style="width: 130px" clearable>
          <el-option label="启用" value="enabled" />
          <el-option label="停用" value="disabled" />
        </el-select>
        <el-button type="primary" @click="load">查询</el-button>
        <el-button @click="resetQuery">重置</el-button>
        <div class="spacer"></div>
        <el-button type="primary" :disabled="!canEditRule" @click="openCreate">
          <el-icon style="margin-right:4px"><Plus /></el-icon>新增规则
        </el-button>
      </div>

      <el-alert
        v-if="!canEditRule"
        style="margin-bottom:12px;"
        type="info" :closable="false" show-icon
        title="当前角色无规则维护权限（仅「风控管理员」可新增、编辑、启停用、删除规则）"
      />

      <el-table v-loading="loading" :data="rows" size="small" border>
        <el-table-column prop="rule_name" label="规则名称" width="180" fixed />
        <el-table-column prop="rule_code" label="规则编码" width="215" />
        <el-table-column label="规则状态" width="100" align="center">
          <template #default="{ row }">
            <el-switch
              :model-value="row.rule_status === 'enabled'"
              :disabled="!canEditRule"
              @change="toggleStatus(row)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="80" align="center" sortable />
        <el-table-column prop="score" label="命中分值" width="90" align="center">
          <template #default="{ row }">
            <el-tag type="danger" effect="plain" size="small">+{{ row.score }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="hit_count" label="命中次数" width="90" align="center" sortable>
          <template #default="{ row }">
            <el-tag :type="row.hit_count > 0 ? 'primary' : 'info'" effect="plain" size="small">
              {{ row.hit_count }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="触发条件" min-width="280">
          <template #default="{ row }">
            <span class="tg-mono tg-muted" style="font-size:12px;">{{ formatCondition(row.condition) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="规则描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="updated_at" label="更新时间" width="160" />
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" :disabled="!canEditRule" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" text type="danger" :disabled="!canEditRule" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="tg-pagination">
        <span class="tg-muted" style="margin-right:auto;font-size:12px;">
          共 {{ total }} 条规则（优先级数字越小越先匹配）
        </span>
      </div>
    </div>

    <!-- 新增 / 编辑规则 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新增风险规则' : `编辑风险规则 #${form.id}`"
      width="820px"
      top="6vh"
    >
      <el-form :model="form" label-width="92px">
        <el-row :gutter="14">
          <el-col :span="12">
            <el-form-item label="规则编码" required>
              <el-input v-model="form.rule_code" placeholder="如 R_CUSTOM_RULE" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="规则名称" required>
              <el-input v-model="form.rule_name" placeholder="如 自定义风险规则" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="优先级">
              <el-input-number v-model="form.priority" :min="1" :max="999" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="命中分值">
              <el-input-number v-model="form.score" :min="1" :max="100" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="规则状态">
              <el-select v-model="form.rule_status" style="width:100%">
                <el-option label="启用" value="enabled" />
                <el-option label="停用" value="disabled" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="规则描述">
              <el-input v-model="form.description" placeholder="描述该规则的风险含义" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="触发条件">
          <div style="width:100%">
            <!-- 与条件组 -->
            <div class="cond-group">
              <div class="cond-group-head">
                <span>【与】条件组 —— 需全部满足</span>
                <el-button size="small" text type="primary" @click="form.allLeaves.push(blankLeaf())">添加条件</el-button>
              </div>
              <div v-for="(leaf, idx) in form.allLeaves" :key="`all-${idx}`" class="cond-leaf">
                <el-select v-model="leaf.op" style="width: 118px">
                  <el-option v-for="o in operators" :key="o.op" :label="o.label" :value="o.op" />
                </el-select>
                <el-select v-model="leaf.feature" filterable style="flex:1">
                  <el-option v-for="f in featureOptions" :key="f.value" :label="f.label" :value="f.value" />
                </el-select>
                <el-input v-model="leaf.value" style="width: 190px" placeholder="比较值" />
                <el-button text type="danger" @click="form.allLeaves.splice(idx, 1)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
              <div v-if="!form.allLeaves.length" class="tg-muted" style="font-size:12px;">暂无「与」条件</div>
            </div>

            <!-- 或条件组 -->
            <div class="cond-group">
              <div class="cond-group-head">
                <span>【或】条件组 —— 满足任一即可</span>
                <el-button size="small" text type="primary" @click="form.anyLeaves.push(blankLeaf())">添加条件</el-button>
              </div>
              <div v-for="(leaf, idx) in form.anyLeaves" :key="`any-${idx}`" class="cond-leaf">
                <el-select v-model="leaf.op" style="width: 118px">
                  <el-option v-for="o in operators" :key="o.op" :label="o.label" :value="o.op" />
                </el-select>
                <el-select v-model="leaf.feature" filterable style="flex:1">
                  <el-option v-for="f in featureOptions" :key="f.value" :label="f.label" :value="f.value" />
                </el-select>
                <el-input v-model="leaf.value" style="width: 190px" placeholder="比较值" />
                <el-button text type="danger" @click="form.anyLeaves.splice(idx, 1)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
              <div v-if="!form.anyLeaves.length" class="tg-muted" style="font-size:12px;">暂无「或」条件</div>
            </div>

            <el-alert
              type="info" :closable="false" show-icon
              title="提示：包含(contains) 运算符的比较值请用英文逗号分隔，例如：虚拟卡券,数码3C"
            />
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存规则</el-button>
      </template>
    </el-dialog>
  </div>
</template>
