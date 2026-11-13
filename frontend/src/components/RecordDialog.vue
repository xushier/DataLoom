<template>
  <el-dialog v-model="show" :title="title" width="860px" top="8vh"
             append-to-body destroy-on-close :close-on-click-modal="false" @open="onOpen">
    <div ref="bodyRef" class="rec-body">
      <div v-if="!isEdit" class="paste-bar">
        <el-button link type="primary" size="small" @click="togglePaste">
          {{ pasteOpen ? '收起粘贴' : '从 Excel 粘贴' }}
        </el-button>
        <span class="paste-tip">从 Excel 复制一片区域后粘贴，自动解析成多条</span>
      </div>
      <div v-if="pasteOpen" class="paste-panel">
        <el-input ref="pasteAreaRef" v-model="pasteText" type="textarea" :rows="6"
                  placeholder="每行一条记录，列之间用 Tab 分隔（从 Excel 直接复制即是此格式）&#10;首行可以是字段名（如：名称、分类、登记人），也可以不带头、直接按表字段顺序粘贴&#10;示例（无表头）：管接头→A 类→张三，箭头处实际为 Tab" />
        <div class="paste-ops">
          <span class="paste-tip">粘贴后点「解析为条目」，最多 {{ MAX_ENTRIES }} 条</span>
          <div>
            <el-button size="small" @click="pasteOpen = false">取 消</el-button>
            <el-button type="primary" size="small" @click="parsePaste">解析为条目</el-button>
          </div>
        </div>
      </div>
      <div v-for="(e, i) in entries" :key="e.__id" class="entry"
           :class="{ 'is-error': entryErrs[i] }">
        <div v-if="!isEdit && entries.length > 1" class="entry-head">
          <span class="entry-no">第 {{ i + 1 }} 条</span>
          <div>
            <el-button v-if="i > 0" link type="primary" size="small" @click="copyPrev(i)">
              同上一条
            </el-button>
            <el-button link type="danger" size="small" @click="removeEntry(i)">删除</el-button>
          </div>
        </div>
        <el-alert v-if="entryErrs[i]" class="entry-err" type="error"
                  :title="entryErrs[i]" :closable="false" show-icon />
        <el-form :ref="el => setFormRef(i, el)" :model="e" label-width="96px" label-position="left"
                 class="rec-form" @submit.prevent="onSubmit">
          <el-row :gutter="16">
            <el-col v-for="f in fields" :key="f.key" :xs="24" :sm="12">
              <el-form-item :label="f.label" :prop="f.key"
                            :rules="rules(f)" :required="isShowRequired(f)">
                <!-- 序号：自动 -->
                <el-input v-if="f.key === 'sn'" :model-value="snDisplay" disabled>
                  <template #suffix><span class="muted">自动</span></template>
                </el-input>
                <!-- 申请人：登录用户新增时锁定为当前用户名 -->
                <el-input v-else-if="f.key === 'applicant' && !isEdit && store.authed"
                          :model-value="store.user?.username" disabled>
                  <template #suffix><span class="muted">自动</span></template>
                </el-input>
                <!-- 申请人：非管理员编辑时锁定为原申请人，防止篡改 -->
                <el-input v-else-if="f.key === 'applicant' && isEdit && !store.isAdmin"
                          :model-value="e[f.key]" disabled>
                  <template #suffix><span class="muted">锁定</span></template>
                </el-input>
                <!-- 申请人：访客新增 / 管理员编辑 —— 可搜索选择或自行输入（选项含全部账号） -->
                <el-autocomplete v-else-if="f.key === 'applicant'"
                                 v-model="e[f.key]" :debounce="150"
                                 :fetch-suggestions="(q, cb) => fetchSuggest(f.key, q, cb)"
                                 placeholder="可搜索选择，无则直接输入" clearable />
                <!-- 单选组 -->
                <el-radio-group v-else-if="f.type === 'radio'" v-model="e[f.key]">
                  <el-radio v-for="o in optValues(f.key)" :key="o" :value="o" border size="small">{{ o }}</el-radio>
                </el-radio-group>
                <!-- 彩色标签：可清空，选中后按选项颜色显示 -->
                <div v-else-if="f.type === 'color_tag'" class="ct-picker">
                  <el-select v-model="e[f.key]" filterable allow-create default-first-option
                             :reserve-keyword="false" placeholder="选择或新建（可清空）"
                             clearable class="w-full">
                    <el-option v-for="o in colorOpts(f.key)" :key="o.value" :label="o.value"
                               :value="o.value">
                      <span class="ct-dot" :style="{ background: o.color }" />
                      <span>{{ o.value }}</span>
                    </el-option>
                  </el-select>
                  <span v-if="e[f.key]" class="ct-badge"
                        :style="badgeStyle(optionColor(f.key, e[f.key]))">{{ e[f.key] }}</span>
                </div>
                <!-- 评分：直接点星 -->
                <div v-else-if="f.type === 'rating'" class="rating-line">
                  <el-rate v-model="e[f.key]" :max="ratingMax(f)" clearable
                           :colors="['#c9ced6', '#e8a33d', '#e8a33d']" />
                  <span class="muted">{{ e[f.key] || 0 }} / {{ ratingMax(f) }}</span>
                </div>
                <!-- 日期差值：只读，由起止日期实时计算 -->
                <el-input v-else-if="f.type === 'date_diff'" :model-value="diffText(f, e)"
                          disabled>
                  <template #suffix><span class="muted">自动</span></template>
                </el-input>
                <!-- 复选组：平铺多选 -->
                <el-checkbox-group v-else-if="f.type === 'checkbox'" v-model="e[f.key]">
                  <el-checkbox v-for="o in optValues(f.key)" :key="o" :value="o" border
                               size="small">{{ o }}</el-checkbox>
                </el-checkbox-group>
                <!-- 开关 -->
                <el-switch v-else-if="f.type === 'switch'" v-model="e[f.key]" />
                <!-- 多选下拉 -->
                <el-select v-else-if="f.type === 'multi_select'"
                           v-model="e[f.key]" multiple filterable allow-create
                           default-first-option :reserve-keyword="false"
                           placeholder="可搜索，无则直接输入新建" clearable>
                  <el-option v-for="o in optValues(f.key)" :key="o" :label="o" :value="o" />
                </el-select>
                <!-- 可搜索输入：点击后原值保留可续改，输入时弹出建议 -->
                <el-autocomplete v-else-if="f.type === 'select'" v-model="e[f.key]"
                                 :debounce="150"
                                 :fetch-suggestions="(q, cb) => fetchSuggest(f.key, q, cb)"
                                 placeholder="可搜索，无则直接输入新建" clearable />
                <!-- 数字 -->
                <el-input-number v-else-if="f.type === 'number'" v-model="e[f.key]"
                                 :controls="false" class="w-full" placeholder="留空自动生成" />
                <!-- 日期 -->
                <el-date-picker v-else-if="f.type === 'date'" v-model="e[f.key]"
                                type="date" value-format="YYYY-MM-DD" placeholder="选择日期"
                                class="w-full" />
                <!-- 日期时间 -->
                <el-date-picker v-else-if="f.type === 'datetime'" v-model="e[f.key]"
                                type="datetime" value-format="YYYY-MM-DD HH:mm:ss"
                                placeholder="留空自动记录当前时间" class="w-full"
                                :default-time="defaultTime" />
                <!-- 多行文本 -->
                <el-input v-else-if="f.type === 'textarea'" v-model="e[f.key]"
                          type="textarea" :rows="2" placeholder="" />
                <!-- 文本 -->
                <el-input v-else v-model="e[f.key]" placeholder="" />
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </div>
      <el-button v-if="!isEdit" class="add-entry" :disabled="saving"
                 @click="addEntry">
        ＋ 再添加一条（{{ entries.length }}/{{ MAX_ENTRIES }}）
      </el-button>
    </div>
    <template #footer>
      <el-button @click="show = false">取 消</el-button>
      <el-button type="primary" :loading="saving" @click="onSubmit">
        {{ isEdit ? '保存修改' : entries.length > 1 ? `提交（${entries.length} 条）` : '提交' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { http } from '@/api'
import { useApp } from '@/store'

const store = useApp()

const props = defineProps({
  modelValue: Boolean,
  table: { type: Object, default: null },       // {id, name, fields, ...}
  record: { type: Object, default: null },      // 编辑时传入
  options: { type: Object, default: () => ({}) } // 各字段可选值
})
const emit = defineEmits(['update:modelValue', 'saved'])

const show = computed({
  get: () => props.modelValue,
  set: v => emit('update:modelValue', v)
})
const fields = computed(() => props.table?.fields || [])
const isEdit = computed(() => !!props.record)
const title = computed(() =>
  `${isEdit.value ? '编辑记录' : '新增数据'} · ${props.table?.name || ''}`)

const MAX_ENTRIES = 20
let uid = 0
const entries = reactive([])   // 批量条目（编辑模式仅 1 条）
const entryErrs = ref([])      // 每条的服务端/自检错误信息
const formRefs = ref([])       // 每条的 el-form 实例
const bodyRef = ref()
const saving = ref(false)

const defaultTime = new Date(2000, 0, 1, 12, 0, 0)

// 申请人候选：全部账号用户名 + 该字段已有可选值（去重）
const applicants = ref([])
async function loadApplicants() {
  try {
    const res = await http.get('/applicants', { headers: { 'X-Silent': 1 } })
    applicants.value = res.applicants || []
  } catch (e) { applicants.value = [] }
}
function applicantOptions(key) {
  const list = [...applicants.value]
  for (const o of optValues(key)) if (!list.includes(o)) list.push(o)
  return list
}

const snDisplay = computed(() => {
  if (isEdit.value) return props.record?.data?.sn ?? ''
  return '自动生成'
})

function opts(key) { return props.options[key] || [] }
function isShowRequired(f) { return f.required && f.key !== 'sn' }

// ---------------- 选项 / 颜色 / 计算字段 ----------------

const FALLBACK_COLORS = ['#5470c6', '#2f9e44', '#e8a33d', '#d94b4b',
                         '#13a8a8', '#8f5bd6', '#d969a8', '#6b7a8f']
function fallbackColor(i) { return FALLBACK_COLORS[i % FALLBACK_COLORS.length] }

// 兼容两种选项结构：普通选择类 ["A"]；彩色标签 [{value,color}]
function colorOpts(key) {
  return opts(key).map((o, i) => (o && typeof o === 'object'
    ? { value: String(o.value ?? ''), color: o.color || fallbackColor(i) }
    : { value: String(o ?? ''), color: fallbackColor(i) }))
    .filter(o => o.value !== '')
}
function optValues(key) { return colorOpts(key).map(o => o.value) }

function optionColor(key, v) {
  const hit = colorOpts(key).find(o => o.value === String(v))
  return hit ? hit.color : fallbackColor(String(v ?? '').length)
}

// 浅色底用深字、深色底用白字
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

// 与后端 human_duration 保持一致的可读时长
function humanDuration(days) {
  if (days === null || days === undefined || Number.isNaN(days)) return ''
  if (days < 0) return '—'
  if (days < 31) return `${days} 天`
  const years = Math.floor(days / 365)
  const months = Math.floor((days % 365) / 30)
  if (!years) return months ? `${months} 个月` : `${days} 天`
  return months ? `${years} 年 ${months} 个月` : `${years} 年`
}
function toDate(v) {
  const s = String(v || '').trim().slice(0, 10)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return null
  const d = new Date(`${s}T00:00:00`)
  return Number.isNaN(d.getTime()) ? null : d
}
function diffText(f, entry) {
  const cfg = f.options && typeof f.options === 'object' ? f.options : {}
  const start = toDate(entry?.[cfg.start])
  if (!start) return '选择起始日期后自动计算'
  const end = cfg.end ? (toDate(entry?.[cfg.end]) || new Date()) : new Date()
  const days = Math.round((end - start) / 86400000)
  return humanDuration(days)
}

// 单选字段建议：点击进入时原值保留可直接续改，输入时弹出过滤建议
function fetchSuggest(key, q, cb) {
  const list = key === 'applicant' ? applicantOptions(key) : optValues(key)
  const s = String(q ?? '').trim().toLowerCase()
  const hit = s ? list.filter(o => String(o).toLowerCase().includes(s)) : list
  cb(hit.slice(0, 50).map(v => ({ value: String(v) })))
}

function rules(f) {
  if (!f.required || f.key === 'sn') return []
  return [{
    validator: (rule, value, cb) => {
      const v = Array.isArray(value) ? value.length : value
      if (v === '' || v === null || v === undefined) {
        cb(new Error(`请填写${f.label}`))
      } else cb()
    },
    trigger: ['blur', 'change']
  }]
}

// ---------------- 批量条目管理 ----------------

function blankEntry() {
  const e = { __id: ++uid }
  for (const f of fields.value) {
    if (f.key === 'sn') continue
    let v = isEdit.value ? props.record.data[f.key] : (f.default_value ?? '')
    if (f.type === 'multi_select' || f.type === 'checkbox') {
      v = Array.isArray(v) ? v : (v ? [v] : [])
    }
    if (f.type === 'switch') v = v === '1' || v === 1 || v === true
    if (f.type === 'rating') v = Number(v) || 0
    if (f.type === 'date_diff') v = ''
    e[f.key] = v ?? (f.type === 'switch' ? false : null)
  }
  return e
}

function setFormRef(i, el) { if (el) formRefs.value[i] = el }

// ---------------- Excel 粘贴解析 ----------------

const pasteOpen = ref(false)
const pasteText = ref('')
const pasteAreaRef = ref()

async function togglePaste() {
  pasteOpen.value = !pasteOpen.value
  if (pasteOpen.value) {
    pasteText.value = ''
    await nextTick()
    pasteAreaRef.value?.focus()
  }
}

// 单元格文本 → 字段值（按类型转换）
function castVal(f, v) {
  if (f.type === 'multi_select' || f.type === 'checkbox') {
    return v.split(/[,，、;；]/).map(s => s.trim()).filter(Boolean)
  }
  if (f.type === 'color_tag') {
    return v.split(/[,，、;；]/).map(s => s.trim()).filter(Boolean)[0] || ''
  }
  if (f.type === 'rating') {
    const n = parseInt(v, 10)
    return Number.isNaN(n) ? 0 : Math.max(0, Math.min(ratingMax(f), n))
  }
  if (f.type === 'date_diff') return ''
  if (f.type === 'switch') return /^(是|真|1|y|yes|true|√|开)$/i.test(v)
  if (f.type === 'number') {
    const n = parseFloat(v)
    return Number.isNaN(n) ? null : n
  }
  if (f.type === 'date') {
    const m = v.match(/^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$/)
    if (m) return `${m[1]}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}`
    return v
  }
  if (f.type === 'datetime') {
    const m = v.match(/^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})(.*)$/)
    if (m) return `${m[1]}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}${m[4]}`
    return v
  }
  return v
}

// 已有条目里是否有已填写内容（替换前确认用）
function hasFilled() {
  return entries.some(e => Object.keys(e).some(k => {
    if (k === '__id') return false
    const v = e[k]
    if (typeof v === 'boolean') return v
    if (Array.isArray(v)) return v.length > 0
    return v !== null && v !== undefined && v !== ''
  }))
}

async function parsePaste() {
  const text = pasteText.value || ''
  const rows = text.replace(/\r\n?/g, '\n').split('\n').filter(r => r.trim() !== '')
  if (!rows.length) { ElMessage.warning('请先粘贴内容'); return }
  // 可映射字段：跳过序号；登录用户的申请人锁定不可改
  const mappable = fields.value.filter(f =>
    f.key !== 'sn' && !(f.key === 'applicant' && !isEdit.value && store.authed))
  const cells = rows.map(r => r.split('\t'))
  // 表头识别：首行至少 2 列匹配字段名（label 或 key）则视为表头行
  const head = cells[0].map(c => c.trim())
  const hits = head.filter(h => mappable.some(f => h === f.label || h === f.key))
  let map, dataRows
  if (hits.length >= 2) {
    map = head.map(h => mappable.find(f => h === f.label || h === f.key) || null)
    dataRows = cells.slice(1)
  } else {
    map = mappable.slice()
    dataRows = cells
  }
  if (entries.length > 1 || hasFilled()) {
    try {
      await ElMessageBox.confirm('解析将替换当前已填写的条目，是否继续？', '提示',
                                 { type: 'warning', confirmButtonText: '替换', cancelButtonText: '取消' })
    } catch { return }
  }
  const list = []
  for (const row of dataRows) {
    if (list.length >= MAX_ENTRIES) break
    const e = blankEntry()
    map.forEach((f, ci) => {
      if (!f) return
      const raw = (row[ci] ?? '').trim()
      if (raw === '') return
      e[f.key] = castVal(f, raw)
    })
    list.push(e)
  }
  if (!list.length) { ElMessage.warning('未解析到有效数据'); return }
  entries.length = 0
  entryErrs.value = list.map(() => '')
  entries.push(...list)
  formRefs.value = []
  pasteOpen.value = false
  pasteText.value = ''
  ElMessage.success(`已解析 ${list.length} 条` +
    (dataRows.length > list.length ? `（超出上限 ${MAX_ENTRIES} 条的部分已忽略）` : ''))
  await nextTick()
  bodyRef.value?.scrollTo({ top: bodyRef.value.scrollHeight })
}

function onOpen() {
  entries.length = 0
  entryErrs.value = []
  formRefs.value = []
  entries.push(blankEntry())
  pasteOpen.value = false
  pasteText.value = ''
  // 含申请人字段时加载账号用户名候选（每次打开刷新，注册新用户后立即可选）
  if (fields.value.some(f => f.key === 'applicant')) loadApplicants()
}

async function addEntry() {
  if (entries.length >= MAX_ENTRIES) {
    ElMessage.warning(`一次最多批量添加 ${MAX_ENTRIES} 条`)
    return
  }
  entries.push(blankEntry())
  entryErrs.value.push('')
  await nextTick()
  bodyRef.value?.scrollTo({ top: bodyRef.value.scrollHeight, behavior: 'smooth' })
}

function removeEntry(i) {
  entries.splice(i, 1)
  entryErrs.value.splice(i, 1)
}

function copyPrev(i) {
  const src = entries[i - 1]
  const dst = entries[i]
  for (const f of fields.value) {
    if (f.key === 'sn') continue
    // 登录用户的申请人锁定为当前用户名，无需复制
    if (f.key === 'applicant' && store.authed) continue
    const v = src[f.key]
    if (v === null || v === undefined || v === '') continue
    if (Array.isArray(v) && !v.length) continue
    dst[f.key] = Array.isArray(v) ? [...v] : v
  }
  entryErrs.value[i] = ''
}

// ---------------- 提交 ----------------

function entryPayload(e) {
  const data = {}
  for (const f of fields.value) {
    if (f.key === 'sn' || f.type === 'date_diff') continue
    data[f.key] = e[f.key]
  }
  return data
}

async function onSubmit() {
  // 逐条表单校验
  const forms = formRefs.value.slice(0, entries.length).filter(Boolean)
  let invalid = false
  for (const f of forms) {
    try { await f.validate() } catch { invalid = true }
  }
  if (invalid) {
    ElMessage.warning(isEdit.value ? '请填写必填项' : '仍有条目未通过校验，请检查标红字段')
    return
  }
  saving.value = true
  try {
    if (isEdit.value) {
      const data = { ...props.record.data, ...entryPayload(entries[0]) }
      delete data.sn
      await http.put(`/records/${props.record.id}`, { data })
      ElMessage.success('记录已更新')
      emit('saved', 0)
      show.value = false
      return
    }
    entryErrs.value = entries.map(() => '')
    const items = entries.map(e => ({ data: entryPayload(e) }))
    const res = await http.post(`/tables/${props.table.id}/records/batch`, { items })
    const results = res.results || []
    if (res.partial) {
      // 成功的移除，失败的保留标红，改完可单独重交
      results.forEach(r => { if (!r.ok) entryErrs.value[r.index] = r.message })
      for (let i = results.length - 1; i >= 0; i--) {
        if (results[i].ok) { entries.splice(i, 1); entryErrs.value.splice(i, 1) }
      }
      ElMessage.warning(`已成功 ${res.added} 条，失败 ${items.length - res.added} 条，请修改后重新提交`)
      emit('saved', res.added)
    } else {
      ElMessage.success(`${res.added} 条数据添加成功`)
      emit('saved', res.added)
      show.value = false
    }
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.rec-body { max-height: 60vh; overflow-y: auto; padding-right: 2px; }
.paste-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.paste-tip { font-size: 12px; color: var(--el-text-color-secondary); }
.paste-panel { background: var(--el-fill-color-lighter); border-radius: 10px;
               padding: 12px; margin-bottom: 12px; }
.paste-ops { display: flex; justify-content: space-between; align-items: center;
             margin-top: 8px; }
.entry { background: var(--el-fill-color-lighter); border: 1px solid transparent;
         border-radius: 10px; padding: 14px 14px 0; margin-bottom: 12px; }
.entry.is-error { border-color: var(--el-color-danger-light-5);
                  background: var(--el-color-danger-light-9); }
.entry-head { display: flex; align-items: center; justify-content: space-between;
              margin-bottom: 10px; }
.entry-no { font-size: 13px; font-weight: 600; color: var(--el-text-color-primary); }
.entry-err { margin-bottom: 10px; }
.add-entry { width: 100%; border-style: dashed; border-radius: 8px;
             margin-bottom: 0; height: 36px; }
.rec-form :deep(.el-form-item) { margin-bottom: 14px; }
.rec-form :deep(.el-form-item__label) { font-size: 13px; }
.w-full { width: 100%; }

/* 彩色标签 */
.ct-picker { display: flex; align-items: center; gap: 8px; width: 100%; }
.ct-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%;
          margin-right: 8px; vertical-align: middle; }
.ct-badge { display: inline-block; padding: 3px 12px; border-radius: 6px;
            font-size: 13px; font-weight: 600; white-space: nowrap; }
.rating-line { display: flex; align-items: center; gap: 10px; }
</style>
