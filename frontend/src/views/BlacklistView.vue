<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { batchImportBlacklist, createBlacklist, deleteBlacklist, listBlacklists } from '../api'
import { canEditBlacklist } from '../stores/role'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const types = ref([])
const typeStat = ref({})

const query = reactive({ blacklist_type: '', keyword: '', page: 1, page_size: 10 })

const addVisible = ref(false)
const importVisible = ref(false)
const saving = ref(false)

const addForm = reactive({ blacklist_type: 'user', blacklist_value: '', remark: '', status: 'active' })
const importText = ref('')
const importSummary = ref(null)

const typeCards = computed(() =>
  (types.value || []).map((t) => ({ ...t, count: typeStat.value[t.value] || 0 }))
)

const typeTagType = (type) => {
  if (type === 'user') return 'danger'
  if (type === 'ip') return 'warning'
  if (type === 'address') return 'primary'
  return 'info'
}

const IMPORT_SAMPLE = `user,U2001,恶意刷单账号
ip,10.20.30.40,高风险设备IP
address,某某市某某区某某路1号,虚假收货地址
phone,13900001111,骚扰客服手机号`

async function load() {
  loading.value = true
  try {
    const data = await listBlacklists({
      page: query.page,
      page_size: query.page_size,
      blacklist_type: query.blacklist_type || undefined,
      keyword: query.keyword || undefined
    })
    rows.value = data.list || []
    total.value = data.total || 0
    types.value = data.types || []
    typeStat.value = data.type_stat || {}
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  query.blacklist_type = ''
  query.keyword = ''
  query.page = 1
  load()
}

function filterByType(value) {
  query.blacklist_type = query.blacklist_type === value ? '' : value
  query.page = 1
  load()
}

function openAdd() {
  Object.assign(addForm, { blacklist_type: 'user', blacklist_value: '', remark: '', status: 'active' })
  addVisible.value = true
}

async function submitAdd() {
  if (!addForm.blacklist_value.trim()) {
    ElMessage.warning('请填写黑名单命中值')
    return
  }
  saving.value = true
  try {
    const res = await createBlacklist({ ...addForm })
    ElMessage.success(res.message)
    addVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

function openImport() {
  importText.value = ''
  importSummary.value = null
  importVisible.value = true
}

async function submitImport() {
  if (!importText.value.trim()) {
    ElMessage.warning('请粘贴待导入的数据')
    return
  }
  saving.value = true
  try {
    const res = await batchImportBlacklist({ text: importText.value })
    importSummary.value = res
    ElMessage.success(res.message)
    load()
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(
    `确认删除黑名单「${row.blacklist_value}」？删除后风险检查将不再命中该条目。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
  )
  const res = await deleteBlacklist({ id: row.id })
  ElMessage.success(res.message)
  load()
}

onMounted(load)
</script>

<template>
  <div>
    <div class="tg-stat-grid">
      <div
        v-for="card in typeCards"
        :key="card.value"
        class="tg-stat"
        :class="{ 'is-high': card.value === 'user', 'is-medium': card.value === 'ip' }"
        style="cursor:pointer;"
        @click="filterByType(card.value)"
      >
        <div class="tg-stat-label">{{ card.label }}黑名单</div>
        <div class="tg-stat-value">{{ card.count }}<small>条生效</small></div>
        <div class="tg-stat-foot">点击按类型筛选</div>
      </div>
    </div>

    <div class="tg-card">
      <div class="tg-toolbar">
        <el-select v-model="query.blacklist_type" placeholder="全部类型" style="width: 150px" clearable>
          <el-option v-for="t in types" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
        <el-input
          v-model="query.keyword"
          placeholder="搜索命中值 / 备注"
          style="width: 230px"
          clearable
          @keyup.enter="query.page = 1; load()"
        />
        <el-button type="primary" @click="query.page = 1; load()">查询</el-button>
        <el-button @click="resetQuery">重置</el-button>
        <div class="spacer"></div>
        <el-button :disabled="!canEditBlacklist" @click="openImport">
          <el-icon style="margin-right:4px"><Upload /></el-icon>批量导入
        </el-button>
        <el-button type="primary" :disabled="!canEditBlacklist" @click="openAdd">
          <el-icon style="margin-right:4px"><Plus /></el-icon>新增黑名单
        </el-button>
      </div>

      <el-alert
        v-if="!canEditBlacklist"
        style="margin-bottom:12px;"
        type="info" :closable="false" show-icon
        title="当前角色无黑名单维护权限（仅「风控管理员」可新增、删除、批量导入黑名单）"
      />

      <el-table v-loading="loading" :data="rows" size="small" border>
        <el-table-column prop="id" label="编号" width="76" />
        <el-table-column label="黑名单类型" width="120">
          <template #default="{ row }">
            <el-tag :type="typeTagType(row.blacklist_type)" effect="light" size="small">
              {{ row.blacklist_type_label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="blacklist_value" label="命中值" min-width="220">
          <template #default="{ row }">
            <span class="tg-mono">{{ row.blacklist_value }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="250" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" effect="plain" size="small">
              {{ row.status_label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="165" />
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="danger" :disabled="!canEditBlacklist" @click="remove(row)">
              删除
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

    <!-- 新增黑名单 -->
    <el-dialog v-model="addVisible" title="新增黑名单" width="520px">
      <el-form :model="addForm" label-width="96px">
        <el-form-item label="黑名单类型" required>
          <el-select v-model="addForm.blacklist_type" style="width:100%">
            <el-option v-for="t in types" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="命中值" required>
          <el-input v-model="addForm.blacklist_value" placeholder="用户编号 / 收货地址 / 设备IP / 手机号" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="addForm.remark" type="textarea" :rows="2" placeholder="拉黑原因，便于后续排查" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="addForm.status">
            <el-radio value="active">生效中</el-radio>
            <el-radio value="disabled">已停用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <el-alert
        type="warning" :closable="false" show-icon
        title="新增后立即作用于风险检查：用户/地址/IP 三类会直接参与特征计算"
      />
      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitAdd">确认新增</el-button>
      </template>
    </el-dialog>

    <!-- 批量导入 -->
    <el-dialog v-model="importVisible" title="批量导入黑名单" width="620px">
      <el-alert
        type="info" :closable="false" show-icon
        style="margin-bottom:12px;"
        title="每行一条，格式：类型,命中值,备注。类型支持 user / address / ip / phone / order"
      />
      <el-input
        v-model="importText"
        type="textarea"
        :rows="9"
        :placeholder="IMPORT_SAMPLE"
      />
      <div style="margin-top:10px;">
        <el-button size="small" text type="primary" @click="importText = IMPORT_SAMPLE">填入示例数据</el-button>
      </div>

      <el-alert
        v-if="importSummary"
        style="margin-top:12px;"
        :type="importSummary.skipped_count ? 'warning' : 'success'"
        :closable="false" show-icon
        :title="importSummary.message"
      >
        <div v-if="importSummary.skipped?.length" style="font-size:12px;line-height:1.7;">
          <div v-for="(s, i) in importSummary.skipped" :key="i">· {{ s }}</div>
        </div>
      </el-alert>

      <template #footer>
        <el-button @click="importVisible = false">关闭</el-button>
        <el-button type="primary" :loading="saving" @click="submitImport">开始导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>
