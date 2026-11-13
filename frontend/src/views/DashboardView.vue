<template>
  <div class="page dash">
    <!-- 自定义汇总统计卡 -->
    <el-row v-if="statCards.length" :gutter="12" class="stat-row">
      <el-col v-for="(c, i) in statCards" :key="c.id" :xs="12" :sm="12" :md="6">
        <div class="card stat-card">
          <div class="stat-icon" :style="iconStyle(i)">
            <el-icon :size="22"><component :is="statIcons[i % statIcons.length]" /></el-icon>
          </div>
          <div class="stat-body">
            <div class="stat-num tabular">
              {{ formatNum(c.value) }}<span v-if="c.suffix" class="stat-suffix">{{ c.suffix }}</span>
            </div>
            <div class="muted stat-label">{{ c.title }}</div>
            <div class="muted stat-hint">{{ c.hint }}</div>
          </div>
        </div>
      </el-col>
    </el-row>
    <div v-else class="card empty-cards">
      <el-empty description="尚未配置汇总卡片，可在「系统设置 - 仪表盘」中添加" :image-size="60" />
    </div>

    <!-- 增长曲线（全部数据表合计） -->
    <div class="card chart-card growth-card">
      <div class="card-title">近 30 天增长曲线<span class="card-hint muted">全部数据表合计</span></div>
      <div ref="growthEl" class="chart" />
    </div>

    <!-- 自定义图表卡片：分布（饼图） / 排行（条形） -->
    <div v-if="chartCards.length" class="card-grid">
      <div v-for="c in chartCards" :key="c.id" class="card chart-card">
        <div class="card-title">{{ c.title }}<span class="card-hint muted">{{ c.hint }}</span></div>
        <el-empty v-if="!c.items || !c.items.length" description="暂无数据" :image-size="56" />
        <template v-else>
          <div v-if="c.type === 'pie'" class="chart pie-chart" :ref="el => setPieRef(c.id, el)" />
          <div v-else class="rank-list">
            <div v-for="(r, i) in c.items" :key="r.name" class="rank-item">
              <span class="rank-no tabular" :class="`rank-${i + 1}`">{{ i + 1 }}</span>
              <span class="rank-name">{{ r.name }}</span>
              <div class="rank-bar-wrap">
                <div class="rank-bar" :style="{ width: barPct(r.value, c) }" />
              </div>
              <span class="rank-count tabular">{{ formatNum(r.value) }}</span>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- 日历热力图 + 最近数据 -->
    <el-row :gutter="12" class="bottom-row">
      <el-col :xs="24" :lg="10">
        <CalendarCard />
      </el-col>
      <el-col :xs="24" :lg="14">
        <div class="card recent-card">
          <div class="card-title">最近添加的数据</div>
          <el-empty v-if="!recent.length" description="暂无数据" :image-size="60" />
          <el-scrollbar v-else max-height="300px">
            <div class="recent-list">
              <div v-for="r in recent" :key="r.id" class="recent-item">
                <el-tag size="small" effect="plain" class="recent-table">{{ r.table_name }}</el-tag>
                <span class="recent-primary">{{ r.primary || '—' }}</span>
                <span class="recent-secondary">{{ r.secondary }}</span>
                <span class="muted recent-meta">
                  {{ r.operator || '未知' }} · {{ r.created_at }}
                </span>
              </div>
            </div>
          </el-scrollbar>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { http } from '@/api'
import { useApp } from '@/store'
import CalendarCard from '@/components/CalendarCard.vue'

const store = useApp()

const cards = ref([])
const growth = ref([])
const recent = ref([])

const statCards = computed(() => cards.value.filter(c => c.type === 'stat'))
const chartCards = computed(() => cards.value.filter(c => c.type !== 'stat'))

const statIcons = ['DataAnalysis', 'CirclePlus', 'TrendCharts', 'Tickets', 'Histogram', 'PieChart', 'Collection']
const statColors = [
  { background: 'var(--dc-primary-soft)', color: 'var(--dc-primary)' },
  { background: '#e8f7ef', color: '#2f9e6e' },
  { background: '#fff6e5', color: '#d07e2d' },
  { background: '#eef0fd', color: '#7b5fc9' },
  { background: '#e9f4fb', color: '#3a7bd5' },
  { background: '#fdeef1', color: '#c9506e' }
]
function iconStyle(i) { return statColors[i % statColors.length] }

function formatNum(v) {
  const n = Number(v)
  if (!isFinite(n)) return v ?? 0
  return Number.isInteger(n) ? n : n.toFixed(2)
}

const growthEl = ref()
let growthChart = null
const pieRefs = {}
const pieCharts = {}

function setPieRef(id, el) {
  if (el) pieRefs[id] = el
}

const palette = computed(() => {
  const p = getComputedStyle(document.documentElement).getPropertyValue('--dc-primary').trim()
  return [p || '#3e8e68', '#50c2a0', '#f2b544', '#e8735a', '#7b5fc9', '#4c7e93', '#8fb339', '#c9506e']
})

function axisStyle() {
  const dark = store.dark
  return {
    axisLabel: { color: dark ? '#8b95a1' : '#5a6470' },
    axisLine: { lineStyle: { color: dark ? '#2a2f36' : '#dfe4e9' } },
    splitLine: { lineStyle: { color: dark ? '#22272e' : '#edf0f3' } }
  }
}

function renderGrowth() {
  if (!growthEl.value) return
  growthChart = growthChart || echarts.init(growthEl.value)
  const axis = axisStyle()
  growthChart.setOption({
    grid: { left: 36, right: 14, top: 20, bottom: 24 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: growth.value.map(g => g.date.slice(5)), ...axis },
    yAxis: { type: 'value', minInterval: 1, ...axis },
    series: [{
      type: 'line', smooth: true, symbolSize: 5,
      data: growth.value.map(g => g.count),
      lineStyle: { width: 2.5, color: palette.value[0] },
      itemStyle: { color: palette.value[0] },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: palette.value[0] + '55' },
          { offset: 1, color: palette.value[0] + '05' }
        ])
      }
    }]
  }, true)
}

function renderPies() {
  const alive = new Set()
  const axis = axisStyle()
  for (const c of chartCards.value) {
    if (c.type !== 'pie') continue
    const el = pieRefs[c.id]
    if (!el) continue
    alive.add(c.id)
    if (pieCharts[c.id] && pieCharts[c.id].getDom() !== el) {
      pieCharts[c.id].dispose()
      delete pieCharts[c.id]
    }
    const chart = pieCharts[c.id] || echarts.init(el)
    pieCharts[c.id] = chart
    chart.setOption({
      tooltip: { trigger: 'item' },
      legend: {
        bottom: 0, icon: 'circle', type: 'scroll',
        textStyle: { color: axis.axisLabel.color, fontSize: 12 }
      },
      series: [{
        type: 'pie', radius: ['40%', '66%'], center: ['50%', '44%'],
        itemStyle: { borderRadius: 6, borderWidth: 2, borderColor: store.dark ? '#13161a' : '#fff' },
        label: { show: false },
        data: (c.items || []).map(it => {
          const manual = c.colors && c.colors[it.name]
          return manual ? { name: it.name, value: it.value, itemStyle: { color: manual } }
            : { name: it.name, value: it.value }
        })
      }],
      color: palette.value
    }, true)
  }
  for (const id of Object.keys(pieCharts)) {
    if (!alive.has(id)) {
      pieCharts[id].dispose()
      delete pieCharts[id]
    }
  }
}

function renderAll() {
  renderGrowth()
  renderPies()
}

function onResize() {
  growthChart?.resize()
  Object.values(pieCharts).forEach(c => c.resize())
}

function barPct(value, card) {
  const max = card.items?.[0]?.value || 1
  return Math.max(6, Math.round((value / max) * 100)) + '%'
}

async function load() {
  const [dash, cardRes] = await Promise.all([
    http.get('/dashboard'),
    http.get('/dashboard/cards')
  ])
  growth.value = dash.growth
  recent.value = dash.recent
  cards.value = cardRes.cards || []
  await nextTick()
  renderAll()
}

let ro = null

onMounted(async () => {
  await load()
  window.addEventListener('resize', onResize)
  ro = new ResizeObserver(onResize)
  if (growthEl.value) ro.observe(growthEl.value)
})

watch(() => [store.theme, store.dark], async () => {
  await new Promise(r => setTimeout(r, 60))
  growthChart?.dispose(); growthChart = null
  Object.keys(pieCharts).forEach(id => { pieCharts[id].dispose(); delete pieCharts[id] })
  await nextTick()
  renderAll()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  ro?.disconnect()
  growthChart?.dispose()
  Object.values(pieCharts).forEach(c => c.dispose())
})
</script>

<style scoped>
.dash { overflow-y: auto; }
.stat-row { row-gap: 12px; }
.stat-card {
  display: flex; align-items: center; gap: 12px; padding: 16px;
  height: 100%;
}
.stat-icon {
  width: 46px; height: 46px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center; flex: none;
}
.stat-body { min-width: 0; }
.stat-num { font-size: 26px; font-weight: 700; line-height: 1.1; color: var(--dc-text); }
.stat-suffix { font-size: 13px; font-weight: 500; margin-left: 3px; color: var(--dc-text-soft); }
.stat-label { margin-top: 4px; }
.stat-hint {
  font-size: 12px; margin-top: 2px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.empty-cards { padding: 10px; }

.growth-card { margin-top: 12px; }
.chart-card { padding: 14px 16px; }
.card-title { font-size: 14px; font-weight: 600; margin-bottom: 8px; }
.card-hint { font-size: 12px; font-weight: 400; margin-left: 8px; }
.chart { height: 260px; width: 100%; }

.card-grid {
  display: grid; gap: 12px; margin-top: 12px;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
}
.pie-chart { height: 260px; }

.rank-list { display: flex; flex-direction: column; gap: 4px; }
.rank-item { display: flex; align-items: center; gap: 8px; padding: 5px 0; }
.rank-no {
  width: 22px; height: 22px; border-radius: 7px; flex: none;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700;
  background: var(--dc-bg-soft); color: var(--dc-text-soft);
}
.rank-1 { background: #f2b544; color: #fff; }
.rank-2 { background: #9aa8b5; color: #fff; }
.rank-3 { background: #c98a5b; color: #fff; }
.rank-name { width: 110px; flex: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rank-bar-wrap { flex: 1; height: 8px; background: var(--dc-bg-soft); border-radius: 4px; overflow: hidden; }
.rank-bar { height: 100%; background: var(--dc-primary); border-radius: 4px; transition: width .4s; }
.rank-count { min-width: 36px; text-align: right; color: var(--dc-text-soft); font-size: 12px; }

.bottom-row { margin-top: 12px; }
.recent-card { padding: 14px 16px; height: 100%; }
.recent-list { display: flex; flex-direction: column; }
.recent-item {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 6px; border-bottom: 1px solid var(--dc-border);
  font-size: 13px;
}
.recent-item:last-child { border-bottom: none; }
.recent-table { flex: none; max-width: 150px; overflow: hidden; }
.recent-primary { font-weight: 600; color: var(--dc-primary); flex: none; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.recent-secondary { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--dc-text-soft); }
.recent-meta { margin-left: auto; flex: none; font-size: 12px; }

/* <1200px：同行多卡在窄屏改为全宽堆叠，列间留间距防粘连 */
@media (max-width: 1199px) {
  .bottom-row :deep(.el-col) { margin-bottom: 12px; }
  .bottom-row :deep(.el-col:last-child) { margin-bottom: 0; }
  .stat-row { row-gap: 0; }
  .stat-row :deep(.el-col) { margin-bottom: 12px; }
}

@media (max-width: 768px) {
  .recent-meta { display: none; }
  .chart, .pie-chart { height: 220px; }
  .card-grid { grid-template-columns: 1fr; }
}
</style>
