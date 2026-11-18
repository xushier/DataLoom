<template>
  <div class="page data-page">
    <!-- 表切换 -->
    <el-tabs v-model="activeId" @tab-change="onTableChange" class="dc-tabs page-tabs">
      <el-tab-pane v-for="t in tables" :key="t.id" :name="t.id">
        <template #label>
          <span class="tab-label">
            <el-icon><Tickets /></el-icon>
            {{ t.name }}
            <span class="tab-count tabular">{{ t.count }}</span>
          </span>
        </template>
      </el-tab-pane>
    </el-tabs>

    <!-- 工具栏 -->
    <div class="card toolbar">
      <div class="toolbar-left">
        <el-button v-if="store.canAdd" type="primary" :icon="Plus" @click="openCreate">新增数据</el-button>
        <el-button v-if="store.isAdmin && selMode !== 'none' && selectedRows.length"
                   type="danger" plain :icon="Delete" @click="onBatchDelete">
          删除选中（{{ selectedRows.length }}）
        </el-button>
        <el-button v-if="store.isAdmin" :icon="Upload" @click="importVisible = true">导入</el-button>
        <el-button :icon="Download" :loading="exporting" @click="doExport">导出</el-button>
        <el-button v-if="store.authed" :icon="Delete" @click="recycleVisible = true">回收站</el-button>
      </div>
      <div class="toolbar-right">
        <el-input v-model="search" placeholder="搜索全表内容…" :prefix-icon="Search"
                  clearable class="search-input" @input="onSearchDebounced" @clear="reload" />
        <el-popover :width="340" trigger="click" persistent>
          <template #reference>
            <el-badge :value="filterCount" :hidden="!filterCount" :offset="[-2, 6]">
              <el-button :icon="Filter">筛选</el-button>
            </el-badge>
          </template>
          <FilterPanel :key="activeId" ref="filterRef" v-model="filters"
                       :fields="fields" :options="options" @update:model-value="reload" />
        </el-popover>
        <el-popover :width="290" trigger="click" persistent>
          <template #reference>
            <el-button :icon="Menu">列设置</el-button>
          </template>
          <div class="cols-pop">
            <div class="cols-head">
              <span class="muted">显示列 · 拖动排序</span>
              <span class="cols-actions">
                <el-button link type="primary" size="small" @click="allColumns(true)">全选</el-button>
                <el-button link size="small" @click="allColumns(false)">清空</el-button>
              </span>
            </div>
            <div class="cols-list">
              <div v-for="(f, i) in fields" :key="f.key"
                   class="cols-item"
                   :class="{ dragging: dragColIndex === i, 'drag-over': colDragOver === i && dragColIndex !== i }"
                   draggable="true"
                   @dragstart="onColDragStart(i, $event)"
                   @dragover.prevent="onColDragOver(i)"
                   @drop.prevent="onColDrop(i)"
                   @dragend="onColDragEnd">
                <el-icon class="drag-handle"><Rank /></el-icon>
                <el-checkbox :model-value="visibleKeys.includes(f.key)"
                             @update:model-value="v => toggleColumn(f.key, v)">
                  {{ f.label }}
                </el-checkbox>
              </div>
            </div>
            <div class="pop-sec muted">表格外观</div>
            <div class="pop-row">
              <span>选择行</span>
              <el-segmented v-model="selMode" :options="selOptions" size="small" />
            </div>
            <div class="pop-row">
              <span>列宽</span>
              <el-button size="small" :disabled="!hasSavedWidths" @click="resetColWidths">重置拖拽列宽</el-button>
            </div>
          </div>
        </el-popover>
        <el-segmented v-model="mode" :options="modeOptions" size="default"
                      @change="reload" class="mode-seg" />
        <span class="muted total-hint tabular">共 {{ total }} 条</span>
      </div>
    </div>

    <!-- 数据表 -->
    <div class="card table-card" v-loading="loading">
      <el-table ref="tableRef" :data="records" :stripe="true" size="small"
                class="dc-table" border
                height="100%" :row-key="r => r.id"
                :row-class-name="rowClassName" :row-style="rowStyle"
                :highlight-current-row="selMode === 'single'"
                :default-sort="{ prop: 'data.sn', order: 'descending' }"
                @sort-change="onSortChange" @row-click="onRowClick"
                @row-dblclick="onRowDblclick"
                @selection-change="onSelectionChange"
                @header-dragend="onHeaderDragend" v-el-scroll>
        <template #empty>
          <el-empty :description="search || filterCount ? '未找到匹配数据'
            : (store.canAdd ? '暂无数据，点击「新增数据」添加' : '暂无数据')"
                    :image-size="72" />
        </template>
        <el-table-column v-if="selMode === 'multi'" type="selection" width="42" />
        <el-table-column v-if="selMode === 'single'" label="" width="42" align="center">
          <template #default="{ row }">
            <el-radio :model-value="selSingleId" :value="row.id"
                      @update:model-value="v => (selSingleId = v)" />
          </template>
        </el-table-column>
        <el-table-column v-for="f in visibleFields" :key="f.key" :prop="'data.' + f.key"
                         :label="f.label" sortable="custom"
                         :align="f.key === 'sn' ? 'center' : 'left'"
                         :width="f.key === 'sn' ? (savedWidths.sn || 72) : savedWidths[f.key]"
                         :min-width="savedWidths[f.key] ? undefined : autoWidths[f.key]">
          <template #default="{ row }">
            <span v-if="f.key === 'sn'" class="tabular">{{ row.data.sn }}</span>
            <!-- 彩色标签：大色块徽章 -->
            <span v-else-if="f.type === 'color_tag'">
              <span v-if="row.data[f.key]" class="ct-badge"
                    :style="badgeStyle(optionColor(f, row.data[f.key]))">{{ row.data[f.key] }}</span>
            </span>
            <!-- 评分：行内直接点星，空值显示空心星 -->
            <span v-else-if="f.type === 'rating'" class="rating-cell"
                  :class="{ 'is-saving': ratingBusy[ratingKey(row, f)] }"
                  @click.stop @dblclick.stop>
              <el-rate :model-value="ratingValue(f, row)" :max="ratingMax(f)"
                       :colors="RATING_COLORS" :disabled="!canEdit(row)"
                       :clearable="canEdit(row)" size="small"
                       @change="v => onRate(f, row, v)" />
            </span>
            <!-- 日期差值：后端实时计算，命中终态后冻结 -->
            <span v-else-if="f.type === 'date_diff'" class="dd-cell"
                  :title="row.calc?.[f.key]?.text || ''">
              <span v-if="row.calc?.[f.key]?.text">{{ row.calc[f.key].text }}</span>
              <span v-if="row.calc?.[f.key]?.frozen" class="dd-frozen"
                    :title="`结束于 ${row.calc[f.key].frozen}，已停止累加`">已结束</span>
              <span v-else-if="row.calc?.[f.key]?.pending" class="dd-frozen"
                    title="尚未命中起始条件，命中后开始计算">未开始</span>
              <span v-else-if="ddArmed(f) && row.calc?.[f.key]?.started" class="dd-start"
                    :title="`自 ${row.calc[f.key].started} 起算`">起算</span>
            </span>
            <!-- 数量明细：总数 + 分项，悬停查看完整明细 -->
            <span v-else-if="f.type === 'quantity'" class="qty-cell">
              <template v-if="qtyTotal(row.data[f.key]) !== null">
                <span class="qty-total">
                  {{ fmtNum(qtyTotal(row.data[f.key])) }}<em v-if="qtyUnit(f)" class="qty-unit">{{ qtyUnit(f) }}</em>
                </span>
                <el-popover v-if="qtyItems(row.data[f.key]).length" placement="top"
                            :width="240" trigger="hover" popper-class="qty-pop">
                  <template #reference>
                    <span class="qty-chips">
                      <span v-for="(it, i) in qtyItems(row.data[f.key]).slice(0, 2)" :key="i"
                            class="qty-chip">{{ it.name }} {{ fmtNum(it.qty) }}</span>
                      <span v-if="qtyItems(row.data[f.key]).length > 2" class="qty-more">
                        +{{ qtyItems(row.data[f.key]).length - 2 }}
                      </span>
                    </span>
                  </template>
                  <div class="qty-pop-head">
                    明细 · 合计 {{ fmtNum(qtyTotal(row.data[f.key])) }}{{ qtyUnit(f) }}
                  </div>
                  <div v-for="(it, i) in qtyItems(row.data[f.key])" :key="i" class="qty-pop-row">
                    <span class="qty-pop-name">{{ it.name }}</span>
                    <span class="tabular">{{ fmtNum(it.qty) }}</span>
                  </div>
                </el-popover>
              </template>
            </span>
            <!-- 多选：按值取色的浅色胶囊，避免整表一片同色标签 -->
            <template v-else-if="Array.isArray(row.data[f.key])">
              <span v-for="(v, i) in row.data[f.key]" :key="i"
                    class="cell-pill" :style="pillStyle(f, v)">{{ v }}</span>
            </template>
            <!-- 开关：列表内直接切换，点击即保存 -->
            <span v-else-if="f.type === 'switch'" class="sw-cell"
                  :class="{ 'is-saving': switchBusy[switchKey(row, f)] }"
                  @click.stop @dblclick.stop>
              <el-switch :model-value="!!row.data[f.key]" size="small"
                         :loading="switchBusy[switchKey(row, f)]"
                         :disabled="!canEdit(row) || switchBusy[switchKey(row, f)]"
                         @change="v => onToggle(f, row, v)" />
            </span>
            <span v-else class="cell-text" :title="fmtCell(row.data[f.key])">{{ fmtCell(row.data[f.key]) }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="store.authed" label="操作" width="132" fixed="right" align="center"
                         class-name="op-cell" label-class-name="op-cell">
          <template #default="{ row }">
            <div v-if="canEdit(row)" class="op-btns" @dblclick.stop>
              <el-button size="small" type="primary" text bg @click="openEdit(row)">编辑</el-button>
              <el-button size="small" type="danger" text bg @click="onDelete(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分页模式 -->
    <div v-if="mode === 'page'" class="card pagination-card">
      <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total"
                     :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next, jumper"
                     @update:current-page="load(false)" @update:page-size="onPageSize" />
    </div>
    <!-- 懒加载模式提示 -->
    <div v-else-if="records.length" class="load-hint muted">
      {{ hasMore ? '下拉加载更多…' : `已全部加载（${records.length} 条）` }}
    </div>

    <!-- 新增 / 编辑 -->
    <RecordDialog v-model="recordVisible" :table="activeTable" :record="editing"
                  :options="options" @saved="onSaved" />

    <!-- 回收站 -->
    <RecycleDialog v-model="recycleVisible" @changed="onRecycleChanged" />

    <!-- 导入 -->
    <el-dialog v-model="importVisible" title="导入 Excel（附加模式，不覆盖现有数据）"
               width="520px" append-to-body destroy-on-close>
      <template v-if="!importResult">
        <el-upload drag :auto-upload="false" :limit="1" accept=".xlsx,.xls"
                   :on-change="f => (importFile = f.raw)" :on-remove="() => (importFile = null)"
                   class="import-upload">
          <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
          <div class="el-upload__text">拖入或 <em>点击选择</em> Excel 文件</div>
          <template #tip>
            <div class="el-upload__tip muted">
              第一行需为列标题，需与字段名一致；
              <el-link type="primary" :underline="false" style="font-size:12px;vertical-align:baseline"
                       @click="downloadTemplate">下载导入模板</el-link>
            </div>
          </template>
        </el-upload>
      </template>
      <template v-else>
        <el-result :icon="importResult.failed.length ? 'warning' : 'success'"
                   :title="`成功导入 ${importResult.added} 条${importResult.failed.length ? '，失败 ' + importResult.failed.length + ' 条' : ''}`">
          <template #extra>
            <div v-if="importResult.ignored_columns?.length" class="muted" style="margin-bottom: 6px">
              忽略的列：{{ importResult.ignored_columns.join('、') }}
            </div>
            <el-scrollbar v-if="importResult.failed.length" max-height="220px" class="import-fails">
              <div v-for="f in importResult.failed" :key="f.row" class="fail-row">
                第 {{ f.row }} 行：{{ f.reason }}
              </div>
            </el-scrollbar>
          </template>
        </el-result>
      </template>
      <template #footer>
        <template v-if="!importResult">
          <el-button @click="importVisible = false">取 消</el-button>
          <el-button type="primary" :disabled="!importFile" :loading="importing" @click="doImport">开始导入</el-button>
        </template>
        <template v-else>
          <el-button @click="importResult = null">继续导入</el-button>
          <el-button type="primary" @click="importVisible = false">完 成</el-button>
        </template>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Upload, Download, Search, Filter, Menu, Delete, Rank } from '@element-plus/icons-vue'
import { http, downloadBlob } from '@/api'
import { useApp } from '@/store'
import RecordDialog from '@/components/RecordDialog.vue'
import RecycleDialog from '@/components/RecycleDialog.vue'
import FilterPanel from '@/components/FilterPanel.vue'

const store = useApp()

const tables = ref([])
const activeId = ref(null)
const fields = ref([])
const records = ref([])
const total = ref(0)
const hasMore = ref(false)
const page = ref(1)
const pageSize = ref(100)
const mode = ref(localStorage.getItem('dc-view-mode') || 'lazy')
const modeOptions = [
  { label: '懒加载', value: 'lazy' },
  { label: '分页', value: 'page' }
]
const search = ref('')
const filters = ref({})
const sortKey = ref('sn')
const sortOrder = ref('desc')
const loading = ref(false)
const loadingMore = ref(false)
const exporting = ref(false)
const visibleKeys = ref([])
const options = reactive({})
const tableRef = ref()
const filterRef = ref()

/* 表格外观：选择行（无 / 单选 / 多选），本地记忆 */
const selMode = ref(localStorage.getItem('dc-selmode') || 'none')
const selOptions = [
  { label: '无', value: 'none' },
  { label: '单选', value: 'single' },
  { label: '多选', value: 'multi' }
]
const selection = ref([])
const selSingleId = ref(null)
watch(selMode, v => {
  localStorage.setItem('dc-selmode', v)
  selection.value = []
  selSingleId.value = null
})
const selectedRows = computed(() =>
  selMode.value === 'multi' ? selection.value
    : selSingleId.value ? [records.value.find(r => r.id === selSingleId.value)].filter(Boolean)
    : [])

function onSelectionChange(rows) { selection.value = rows }
function onRowClick(row) { if (selMode.value === 'single') selSingleId.value = row.id }

const activeTable = computed(() => tables.value.find(t => t.id === activeId.value) || null)
const filterCount = computed(() => Object.keys(filters.value).length)
const visibleFields = computed(() => fields.value.filter(f => visibleKeys.value.includes(f.key)))

/* ---------------- 彩色标签 / 行色条 ---------------- */

const FALLBACK_COLORS = ['#5470c6', '#2f9e44', '#e8a33d', '#d94b4b',
                         '#13a8a8', '#8f5bd6', '#d969a8', '#6b7a8f']
function fallbackColor(i) { return FALLBACK_COLORS[i % FALLBACK_COLORS.length] }

/* 行色条依据字段（表级配置），字段不存在或非彩色标签时不启用 */
const rowColorField = computed(() => {
  const t = activeTable.value
  const key = t?.color_field
  if (!key) return ''
  return (fields.value.find(f => f.key === key && f.type === 'color_tag')) ? key : ''
})

const colorMap = computed(() => {
  const map = {}
  for (const f of fields.value) {
    if (f.type !== 'color_tag') continue
    const m = {}
    const list = options[f.key] || []
    list.forEach((o, i) => {
      if (o && typeof o === 'object') m[String(o.value)] = o.color || fallbackColor(i)
      else m[String(o)] = fallbackColor(i)
    })
    map[f.key] = m
  }
  return map
})

function optionColor(f, v) {
  const m = colorMap.value[f.key] || {}
  return m[String(v)] || fallbackColor(String(v ?? '').length)
}

function rowColor(row) {
  const key = rowColorField.value
  if (!key || !row?.data?.[key]) return ''
  return optionColor({ key }, row.data[key])
}

function rowClassName({ row }) {
  return rowColor(row) ? 'row-colored' : ''
}
function rowStyle({ row }) {
  const c = rowColor(row)
  return c ? { '--row-color': c } : {}
}

function textColor(hex) {
  const c = String(hex || '').replace('#', '')
  if (c.length !== 6) return '#fff'
  const r = parseInt(c.slice(0, 2), 16)
  const g = parseInt(c.slice(2, 4), 16)
  const b = parseInt(c.slice(4, 6), 16)
  return (r * 299 + g * 587 + b * 114) / 1000 > 160 ? '#1f2329' : '#fff'
}
function badgeStyle(color) {
  return { background: color, color: textColor(color) }
}
function ratingMax(f) {
  const m = f.options && typeof f.options === 'object' ? Number(f.options.max) : 5
  return Number.isFinite(m) && m >= 3 ? m : 5
}

/* ---------------- 行内评分 / 多选配色 ---------------- */

const RATING_COLORS = ['#e8a33d', '#e8a33d', '#e8a33d']
const ratingBusy = reactive({})

function ratingKey(row, f) { return `${row.id}:${f.key}` }

/* 开关字段：在列表内点击直接保存，失败回滚 */
const switchBusy = reactive({})
function switchKey(row, f) { return `${row.id}:${f.key}` }

async function onToggle(f, row, v) {
  if (!canEdit(row)) return
  const key = switchKey(row, f)
  if (switchBusy[key]) return
  const old = !!row.data[f.key]
  switchBusy[key] = true
  row.data[f.key] = v
  try {
    await http.put(`/records/${row.id}`, { data: { ...row.data, [f.key]: v } })
  } catch (e) {
    row.data[f.key] = old
    ElMessage.error(e?.response?.data?.message || '开关保存失败')
  } finally {
    delete switchBusy[key]
  }
}
function ratingValue(f, row) {
  const n = Number(row.data[f.key])
  return Number.isFinite(n) ? n : 0
}

/* 点击星星即保存：先本地更新，失败回滚 */
async function onRate(f, row, v) {
  if (!canEdit(row)) return
  const key = ratingKey(row, f)
  if (ratingBusy[key]) return
  const old = row.data[f.key]
  const next = Number(v) || 0
  ratingBusy[key] = true
  row.data[f.key] = next
  try {
    const data = { ...row.data, [f.key]: next }
    await http.put(`/records/${row.id}`, { data })
  } catch (e) {
    row.data[f.key] = old
    ElMessage.error(e?.response?.data?.message || '评分保存失败')
  } finally {
    delete ratingBusy[key]
  }
}

/* 多选标签：同字段不同类型也能一眼区分，按「字段 + 值」稳定取色 */
const PILL_COLORS = ['#3a7bd5', '#2f9e44', '#d98a1f', '#c9506e',
                     '#7b5fc9', '#13a8a8', '#c0563f', '#5a7d9a']
function pillStyle(f, v) {
  const s = `${f.key}:${v}`
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return { '--pill': PILL_COLORS[h % PILL_COLORS.length] }
}

/* ---------------- 数量明细 ---------------- */

function ddArmed(f) {
  const o = f.options && typeof f.options === 'object' ? f.options : {}
  return !!(o.start_field && (o.start_values || []).length)
}

function qtyUnit(f) {
  const o = f.options && typeof f.options === 'object' ? f.options : {}
  return o.unit || ''
}
function qtyTotal(v) {
  if (v === null || v === undefined || v === '') return null
  const n = typeof v === 'object' ? Number(v.total) : Number(v)
  return Number.isFinite(n) ? n : null
}
function qtyItems(v) {
  return v && typeof v === 'object' && Array.isArray(v.items)
    ? v.items.filter(it => it && String(it.name || '').trim())
    : []
}
function fmtNum(n) {
  if (n === null || n === undefined || n === '') return ''
  const num = Number(n)
  return Number.isInteger(num) ? String(num) : String(num)
}

/* ---------------- 数据加载 ---------------- */

async function loadTables() {
  const res = await http.get('/tables')
  tables.value = res.tables
  if (!tables.value.length) return
  let saved = parseInt(localStorage.getItem('dc-active-table'))
  if (!tables.value.some(t => t.id === saved)) saved = tables.value[0].id
  activeId.value = saved
  await onTableChange()
}

async function onTableChange() {
  localStorage.setItem('dc-active-table', activeId.value)
  const t = activeTable.value
  fields.value = t ? t.fields : []
  initVisibleKeys()
  initColWidths()
  await loadOptions()
  reload()
}

async function loadOptions() {
  if (!activeId.value) return
  try {
    const res = await http.get(`/tables/${activeId.value}/options`)
    Object.keys(options).forEach(k => delete options[k])
    Object.assign(options, res.options)
  } catch { /* 静默 */ }
}

function initVisibleKeys() {
  const key = `dc-cols-${activeId.value}`
  const saved = localStorage.getItem(key)
  if (saved) {
    try {
      const list = JSON.parse(saved)
      const valid = fields.value.filter(f => list.includes(f.key)).map(f => f.key)
      const missing = fields.value.filter(f => !list.includes(f.key))
        .filter(f => f.is_system).map(f => f.key)
      visibleKeys.value = [...valid, ...missing]
    } catch { visibleKeys.value = fields.value.map(f => f.key) }
  } else {
    visibleKeys.value = fields.value.map(f => f.key)
  }
}

watch(visibleKeys, () => {
  if (activeId.value) localStorage.setItem(`dc-cols-${activeId.value}`, JSON.stringify(visibleKeys.value))
}, { deep: true })

function allColumns(all) {
  visibleKeys.value = all ? fields.value.map(f => f.key) : []
}

function toggleColumn(key, on) {
  if (on) {
    if (!visibleKeys.value.includes(key)) visibleKeys.value = [...visibleKeys.value, key]
  } else {
    visibleKeys.value = visibleKeys.value.filter(k => k !== key)
  }
}

/* 列设置：拖动调整列顺序，顺序写回字段排序，数据表与字段管理保持一致 */
const dragColIndex = ref(-1)
const colDragOver = ref(-1)

function onColDragStart(i, e) {
  dragColIndex.value = i
  try {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', String(i))
  } catch { /* 部分浏览器不支持 */ }
}

function onColDragOver(i) {
  if (dragColIndex.value >= 0) colDragOver.value = i
}

function onColDragEnd() {
  dragColIndex.value = -1
  colDragOver.value = -1
}

async function onColDrop(i) {
  const from = dragColIndex.value
  onColDragEnd()
  if (from < 0 || from === i) return
  const list = [...fields.value]
  const [item] = list.splice(from, 1)
  list.splice(i, 0, item)
  fields.value = list
  try {
    await http.post(`/tables/${activeId.value}/fields/reorder`, { ids: list.map(f => f.id) })
    const t = tables.value.find(x => x.id === activeId.value)
    if (t) t.fields = list
    ElMessage.success('列顺序已更新')
  } catch {
    await loadTables()
  }
}

async function load(append = false) {
  if (!activeId.value) return
  if (append) loadingMore.value = true
  else loading.value = true
  try {
    const params = {
      search: search.value,
      filters: JSON.stringify(filters.value),
      sort: sortKey.value,
      order: sortOrder.value,
      page: page.value,
      page_size: mode.value === 'page' ? pageSize.value : 50,
      mode: mode.value
    }
    const res = await http.get(`/tables/${activeId.value}/records`, { params })
    total.value = res.total
    hasMore.value = res.has_more
    if (append) records.value.push(...res.items)
    else records.value = res.items
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function reload() {
  page.value = 1
  load(false)
}

/* ---------------- 搜索 / 排序 / 懒加载 ---------------- */

let searchTimer = null
function onSearchDebounced() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(reload, 300)
}

function onSortChange({ prop, order }) {
  if (order) {
    sortKey.value = (prop || '').replace('data.', '')
    sortOrder.value = order === 'ascending' ? 'asc' : 'desc'
  } else {
    sortKey.value = 'sn'
    sortOrder.value = 'desc'
  }
  reload()
}

let scrollEl = null
let scrollTimer = null
function onBodyScroll() {
  if (mode.value !== 'lazy' || !hasMore.value || loadingMore.value || loading.value) return
  clearTimeout(scrollTimer)
  scrollTimer = setTimeout(() => {
    const el = document.querySelector('.table-card .el-scrollbar__wrap') ||
               document.querySelector('.table-card .el-table__body-wrapper')
    if (!el) return
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 60) {
      page.value++
      load(true)
    }
  }, 80)
}

const vElScroll = {
  mounted() {
    /* 在 el-table 渲染后挂载滚动监听 */
    setTimeout(() => {
      scrollEl = document.querySelector('.table-card .el-scrollbar__wrap') ||
                document.querySelector('.table-card .el-table__body-wrapper')
      scrollEl?.addEventListener('scroll', onBodyScroll, { passive: true })
    }, 500)
  },
  unmounted() {
    scrollEl?.removeEventListener('scroll', onBodyScroll)
  }
}

onMounted(loadTables)
onBeforeUnmount(() => scrollEl?.removeEventListener('scroll', onBodyScroll))

/* ---------------- 新增 / 编辑 / 删除 ---------------- */

const recordVisible = ref(false)
const editing = ref(null)

function openCreate() {
  editing.value = null
  recordVisible.value = true
}
function openEdit(row) {
  editing.value = row
  recordVisible.value = true
}

/* 是否可编辑该行：管理员或本人创建 */
function canEdit(row) {
  return store.isAdmin || (store.authed && row.created_by === store.user?.username)
}

/* 双击行直接打开编辑；单元格内的按钮、评分、选择框不触发 */
function onRowDblclick(row, column, event) {
  if (!canEdit(row)) return
  const el = event?.target
  if (el?.closest?.('.op-btns, .rating-cell, .sw-cell, button, a, input, textarea, .el-checkbox, .el-radio')) return
  openEdit(row)
}

async function onSaved(added = 0) {
  await loadOptions()
  reload()
  const t = activeTable.value
  if (t && added > 0) t.count = (t.count || 0) + added
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除该记录吗？「${row.data.name || row.data.title || '未命名'}」将移入回收站，可恢复或彻底删除。`,
      '删除确认', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  await http.post(`/records/${row.id}`)
  ElMessage.success('已移入回收站')
  reload()
  const t = activeTable.value
  if (t) t.count = Math.max(0, (t.count || 1) - 1)
  await loadOptions()
}

async function onBatchDelete() {
  const rows = selectedRows.value
  if (!rows.length) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${rows.length} 条记录吗？删除后移入回收站，可恢复或彻底删除。`,
      '批量删除确认', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  for (const r of rows) await http.post(`/records/${r.id}`)
  ElMessage.success(`已将 ${rows.length} 条记录移入回收站`)
  selection.value = []
  selSingleId.value = null
  reload()
  const t = activeTable.value
  if (t) t.count = Math.max(0, (t.count || 0) - rows.length)
  await loadOptions()
}

/* ---------------- 回收站 ---------------- */

const recycleVisible = ref(false)

async function onRecycleChanged() {
  // 回收站恢复 / 彻底删除后刷新列表、选项与表计数
  await loadOptions()
  reload()
  await loadTablesRefreshCount()
}

/* ---------------- 导入 / 导出 ---------------- */

const importVisible = ref(false)
const importFile = ref(null)
const importing = ref(false)
const importResult = ref(null)

async function doImport() {
  if (!importFile.value) return
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', importFile.value)
    const res = await http.post(`/tables/${activeId.value}/import`, fd)
    importResult.value = res
    await loadOptions()
    await loadTablesRefreshCount()
    reload()
  } finally {
    importing.value = false
  }
}

async function loadTablesRefreshCount() {
  const res = await http.get('/tables')
  tables.value = res.tables
}

async function downloadTemplate() {
  const res = await http.get(`/tables/${activeId.value}/template`, { responseType: 'blob' })
  downloadBlob(res, `导入模板_${activeTable.value?.name || ''}.xlsx`)
}

function exportParams() {
  return {
    search: search.value,
    filters: JSON.stringify(filters.value),
    sort: sortKey.value,
    order: sortOrder.value
  }
}

async function doExport() {
  exporting.value = true
  try {
    const res = await http.get(`/tables/${activeId.value}/export`,
      { params: exportParams(), responseType: 'blob' })
    downloadBlob(res, `${activeTable.value?.name || '数据'}_导出.xlsx`)
    ElMessage.success('导出成功')
  } finally {
    exporting.value = false
  }
}

function onPageSize(size) {
  pageSize.value = size
  reload()
}

watch(mode, v => localStorage.setItem('dc-view-mode', v))

/* ---------------- 渲染辅助 ---------------- */

/* ---------------- 列宽：内容自动估宽 + 手动拖拽记忆 ---------------- */

/* 文本宽度估算：中文约 13px/字，数字字母约 7.3px/字（13px 字号） */
function textWidth(t) {
  let w = 0
  for (let i = 0; i < t.length; i++) {
    w += t.charCodeAt(i) > 255 ? 13 : 7.3
    if (w > 470) return w
  }
  return w
}
function cellWidth(f, v, row) {
  if (f.type === 'rating') return ratingMax(f) * 17 + 14
  if (f.type === 'date_diff') {
    const c = row?.calc?.[f.key]
    return textWidth(String(c?.text || '')) + (c?.frozen ? 42 : 0)
  }
  if (f.type === 'color_tag') return v ? textWidth(String(v)) + 32 : 0
  if (f.type === 'quantity') {
    const total = qtyTotal(v)
    if (total === null) return 0
    let w = textWidth(String(total)) + textWidth(qtyUnit(f)) + 34
    const items = qtyItems(v).slice(0, 2)
    for (const it of items) w += textWidth(`${it.name} ${it.qty}`) + 22
    if (qtyItems(v).length > 2) w += 26
    return w
  }
  if (v === null || v === undefined || v === '') return 0
  if (Array.isArray(v)) {
    // 多选标签：每个标签自带内边距、边框与间距
    return v.reduce((s, x) => s + textWidth(String(x)) + 24, 0) + (v.length - 1) * 4
  }
  if (f.type === 'switch') return 58
  return textWidth(String(v))
}
/* 按表头与已加载数据的实际内容估宽：窄数据列自动收窄、宽列有上限，
   多余宽度仍按比例分给各列，尽量减少横向滚动条 */
const autoWidths = computed(() => {
  const map = {}
  /* 只按前 60 行估宽：懒加载不断追加数据时避免重复全量计算造成卡顿 */
  const sample = records.value.slice(0, 60)
  for (const f of visibleFields.value) {
    let w = 0
    for (const r of sample) {
      const cw = cellWidth(f, r.data[f.key], r)
      if (cw > w) { w = cw; if (w > 470) break }
    }
    // 表头文字 + 排序箭头 + 单元格左右内边距与少量余量
    const head = textWidth(f.label) + 24 + 26
    map[f.key] = Math.round(Math.min(Math.max(w, head, 64), 470))
  }
  return map
})

/* 用户拖拽过的列宽按表记忆，未拖拽的列保持自动估宽 */
const savedWidths = ref({})
const hasSavedWidths = computed(() => Object.keys(savedWidths.value).length > 0)
const colwKey = computed(() => `dc-colw-${activeId.value}`)
function initColWidths() {
  try { savedWidths.value = JSON.parse(localStorage.getItem(colwKey.value)) || {} }
  catch { savedWidths.value = {} }
}
function onHeaderDragend(newWidth, oldWidth, column) {
  const key = (column?.property || '').replace('data.', '')
  if (!key) return
  savedWidths.value[key] = Math.round(newWidth)
  localStorage.setItem(colwKey.value, JSON.stringify(savedWidths.value))
}
function resetColWidths() {
  savedWidths.value = {}
  localStorage.removeItem(colwKey.value)
}

function fmtCell(v) {
  if (v === null || v === undefined) return ''
  if (Array.isArray(v)) return v.join('、')
  return String(v)
}
</script>

<style scoped>
.data-page { height: 100%; overflow: hidden; }

/* tabs 不再嵌卡片，样式走全局 .dc-tabs（style.css） */
.page-tabs { flex: none; }
.page-tabs :deep(.el-tabs__header) { margin: 0; }
.tab-label { display: inline-flex; align-items: center; gap: 5px; max-width: 240px; }
.tab-count {
  background: color-mix(in srgb, var(--dc-primary) 16%, transparent);
  color: var(--dc-primary);
  border-radius: 999px; padding: 0 8px; font-size: 11px; line-height: 17px;
}

.toolbar {
  display: flex; justify-content: space-between; align-items: center;
  gap: 10px; padding: 10px 12px; flex-wrap: wrap; flex: none;
}
.toolbar-left, .toolbar-right { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.search-input { width: 230px; }
.total-hint { white-space: nowrap; }

.table-card { flex: 1; min-height: 200px; overflow: hidden; padding: 0; }

.pagination-card { padding: 8px 12px; flex: none; display: flex; justify-content: flex-end; }
.load-hint { text-align: center; font-size: 12px; padding: 6px 0 2px; flex: none; }

.cols-pop .cols-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 6px;
}
.cols-actions { display: flex; align-items: center; gap: 2px; }
.cols-list {
  display: flex; flex-direction: column; gap: 1px;
  max-height: 300px; overflow-y: auto; overscroll-behavior: contain;
  margin: 0 -4px; padding: 0 4px 2px;
}
.cols-item {
  display: flex; align-items: center; gap: 6px;
  padding: 1px 6px; border-radius: 6px; cursor: grab;
  transition: background-color .15s, box-shadow .15s;
}
.cols-item:hover { background: var(--dc-bg-soft); }
.cols-item.dragging { opacity: .45; }
.cols-item.drag-over { box-shadow: inset 0 2px 0 var(--dc-primary); }
.cols-item .drag-handle { font-size: 14px; color: var(--dc-text-soft); flex: none; }
.cols-item :deep(.el-checkbox) { flex: 1; min-width: 0; height: 28px; margin-right: 0; }
.cols-item :deep(.el-checkbox__label) {
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.cols-item:has(.el-checkbox.is-checked) :deep(.el-checkbox__label) { color: var(--dc-text); }
.cols-item:not(:has(.el-checkbox.is-checked)) :deep(.el-checkbox__label) { color: var(--dc-text-soft); }
.pop-sec { margin: 10px 0 4px; font-size: 12px; }
.pop-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 5px 0; font-size: 13px; color: var(--dc-text);
}

.import-upload { width: 100%; }
.import-fails .fail-row {
  font-size: 13px; color: var(--dc-text);
  padding: 5px 8px; border-radius: 6px; margin-bottom: 4px;
  background: var(--dc-bg-soft); text-align: left;
}

/* 斑马纹：偶数行用极浅主题色，能看出交替但不抢表头 */
.dc-table :deep(.el-table__body tr.el-table__row--striped > td.el-table__cell) {
  background: color-mix(in srgb, var(--dc-primary) 6%, var(--dc-card));
}
.dc-table :deep(.el-table__body tr:hover > td.el-table__cell) {
  background: color-mix(in srgb, var(--dc-primary) 10%, var(--dc-card));
}
html.dark .dc-table :deep(.el-table__body tr.el-table__row--striped > td.el-table__cell) {
  background: color-mix(in srgb, var(--dc-primary) 6%, var(--dc-card));
}
html.dark .dc-table :deep(.el-table__body tr:hover > td.el-table__cell) {
  background: color-mix(in srgb, var(--dc-primary) 16%, var(--dc-card));
}

/* 多选值胶囊：按值取色，替代清一色的标签 */
.cell-pill {
  display: inline-block; margin: 1px 4px 1px 0; padding: 0 7px;
  border-radius: 5px; font-size: 12px; line-height: 18px; white-space: nowrap;
  background: color-mix(in srgb, var(--pill) 13%, transparent);
  color: color-mix(in srgb, var(--pill) 82%, var(--dc-text));
}
html.dark .cell-pill {
  background: color-mix(in srgb, var(--pill) 24%, transparent);
  color: color-mix(in srgb, var(--pill) 62%, white);
}

/* 开关：列表内直接切换 */
.sw-cell { display: inline-flex; align-items: center; line-height: 1; }
.sw-cell.is-saving { opacity: .6; }
.sw-cell :deep(.el-switch) {
  --el-switch-on-color: #2f9e44;
  --el-switch-off-color: color-mix(in srgb, var(--dc-text-soft) 28%, transparent);
  vertical-align: middle;
}

/* 操作列：半透明毛玻璃，横向滚动时不遮挡下方内容 */
.table-card :deep(.el-table__body .el-table__cell.op-cell) {
  background: color-mix(in srgb, var(--dc-card) 72%, transparent) !important;
  backdrop-filter: blur(10px) saturate(1.12);
  -webkit-backdrop-filter: blur(10px) saturate(1.12);
  box-shadow: -10px 0 12px -10px rgba(20, 30, 40, .22);
}
.table-card :deep(.el-table__header .el-table__cell.op-cell) {
  background: color-mix(in srgb, var(--dc-bg-soft) 84%, transparent) !important;
  backdrop-filter: blur(10px) saturate(1.12);
  -webkit-backdrop-filter: blur(10px) saturate(1.12);
  box-shadow: -10px 0 12px -10px rgba(20, 30, 40, .22);
}

/* 彩色标签：醒目大色块徽章 */
.ct-badge {
  display: inline-block; padding: 2px 12px; border-radius: 7px;
  font-size: 12px; font-weight: 600; line-height: 20px;
  min-width: 56px; text-align: center; white-space: nowrap;
}
.rating-cell { display: inline-flex; align-items: center; height: 20px; }
.rating-cell :deep(.el-rate) {
  height: 18px; display: inline-flex;
  --el-rate-void-color: color-mix(in srgb, var(--dc-text-soft) 36%, transparent);
}
.rating-cell :deep(.el-rate__icon) { font-size: 15px; margin-right: 1px; }
.rating-cell :deep(.el-rate__item) { cursor: pointer; }
.rating-cell :deep(.el-rate.is-disabled .el-rate__item) { cursor: default; }
.rating-cell.is-saving { opacity: .5; }

/* 日期差值：终态后带「已结束」标记 */
.dd-cell { display: inline-flex; align-items: center; gap: 5px; }
.dd-frozen { font-size: 11px; line-height: 15px; padding: 0 5px; border-radius: 3px;
             background: var(--el-fill-color); color: var(--el-text-color-secondary);
             cursor: default; }
.dd-start { font-size: 11px; line-height: 15px; padding: 0 5px; border-radius: 3px;
            background: color-mix(in srgb, var(--dc-primary) 12%, transparent);
            color: var(--dc-primary); cursor: default; }

/* 数量明细：总数 + 分项小签 */
.qty-cell { display: inline-flex; align-items: center; gap: 6px; max-width: 100%; }
.qty-total { font-weight: 700; font-variant-numeric: tabular-nums; white-space: nowrap; }
.qty-unit { font-style: normal; font-size: 12px; font-weight: 400; margin-left: 2px;
            color: var(--el-text-color-secondary); }
.qty-chips { display: inline-flex; align-items: center; gap: 4px; cursor: default; }
.qty-chip { font-size: 11px; line-height: 16px; padding: 0 6px; border-radius: 4px;
            background: var(--el-fill-color); color: var(--el-text-color-regular);
            white-space: nowrap; }
.qty-more { font-size: 11px; color: var(--el-text-color-secondary); }
:global(.qty-pop) { padding: 10px 12px; }
:global(.qty-pop .qty-pop-head) { font-size: 12px; color: var(--el-text-color-secondary);
                                  padding-bottom: 6px; margin-bottom: 4px;
                                  border-bottom: 1px solid var(--el-border-color-lighter); }
:global(.qty-pop .qty-pop-row) { display: flex; justify-content: space-between; gap: 16px;
                                 font-size: 13px; line-height: 22px; }
:global(.qty-pop .qty-pop-name) { overflow: hidden; text-overflow: ellipsis;
                                  white-space: nowrap; }

/* 行色条：左侧 4px 竖条跟随表级配置的彩色标签字段 */
.dc-table :deep(.el-table__body tr.row-colored td.el-table__cell:first-child) {
  box-shadow: inset 4px 0 0 var(--row-color);
}
.dc-table :deep(.el-table__body tr.row-colored:hover td.el-table__cell:first-child) {
  box-shadow: inset 4px 0 0 var(--row-color);
}

@media (max-width: 768px) {
  .data-page { overflow-y: auto; }
  .table-card { min-height: 55vh; }
  .search-input { width: 100%; }
  .toolbar-left, .toolbar-right { width: 100%; }
  .tab-label { max-width: 160px; }
}
</style>
