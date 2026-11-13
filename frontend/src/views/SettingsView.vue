<template>
  <div class="page settings-page">
    <el-tabs v-model="tab" class="settings-tabs dc-tabs">
      <!-- 基本设置 -->
      <el-tab-pane label="基本设置" name="basic" v-if="store.isAdmin">
        <div class="pane">
          <div class="pane-center">
            <div class="pane-title">基本设置</div>
            <el-form label-width="120px" class="set-form">
              <el-form-item label="系统名称">
                <el-input v-model="form.site_name" placeholder="如：数织" maxlength="20" style="max-width: 320px" />
                <div class="field-hint muted">显示在侧边栏、登录页与浏览器标题，可随时修改</div>
              </el-form-item>
              <el-form-item label="系统副标题">
                <el-input v-model="form.site_subtitle" placeholder="留空自动生成：机构 · 数据登记与台账"
                          maxlength="40" style="max-width: 320px" />
              </el-form-item>
              <el-form-item label="机构名称">
                <el-input v-model="form.site_org" placeholder="选填，用于生成副标题" style="max-width: 320px" />
                <div class="field-hint muted">
                  副标题预览：{{ (form.site_subtitle || '').trim() || ((form.site_org || '').trim() ? (form.site_org || '').trim() + ' · 数据登记与台账' : '通用数据登记与台账') }}
                </div>
              </el-form-item>
              <el-form-item label="系统 Logo">
                <div class="inline-row">
                  <Logo :size="36" />
                  <el-upload :show-file-list="false" :auto-upload="false"
                             accept="image/png,image/jpeg,image/svg+xml,image/webp"
                             :on-change="onLogoChange">
                    <el-button size="small" :loading="logoUploading">上传 Logo</el-button>
                  </el-upload>
                  <el-button v-if="store.site.logo" size="small" type="danger" text bg @click="removeLogo">
                    恢复默认
                  </el-button>
                </div>
                <div class="field-hint muted">支持 PNG / JPG / SVG / WebP，建议正方形；不上传则使用内置图标</div>
              </el-form-item>
              <el-form-item label="访客模式">
                <el-segmented v-model="form.guest_mode" :options="guestOptions" />
                <div class="field-hint muted">
                  未登录访客的权限：关闭则必须登录；只读浏览可查看、筛选、导出；可添加还能新增数据（不能修改删除）
                </div>
              </el-form-item>
              <el-form-item label="允许注册">
                <div class="inline-row">
                  <el-switch v-model="registerBool" />
                  <span class="muted" v-if="registerBool">已开放：登录页将显示「立即注册」入口</span>
                  <span class="muted" v-else>已关闭：新用户需由管理员在用户管理中创建</span>
                </div>
                <div class="field-hint muted">
                  开启后用户可在登录页自助注册（默认普通用户），用户名建议真实姓名、密码至少 8 位
                </div>
              </el-form-item>
              <el-form-item label="日志自动清理">
                <div class="inline-row">
                  <el-switch v-model="logAutoBool" />
                  <el-input-number v-model="form.log_retention_days" :min="1" :max="365"
                                   :disabled="!logAutoBool" controls-position="right" style="width: 120px" />
                  <span class="muted">天</span>
                </div>
                <div class="field-hint muted">系统日志将定期自动清理，保留最近指定天数的记录</div>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="saving" @click="saveBasic">保存设置</el-button>
              </el-form-item>
            </el-form>
          </div>
        </div>
      </el-tab-pane>

      <!-- 用户管理 -->
      <el-tab-pane label="用户管理" name="users" v-if="store.isAdmin">
        <div class="pane pane-table">
          <div class="pane-head">
            <div class="pane-title">用户管理</div>
            <el-button type="primary" :icon="Plus" @click="openUserCreate">新建用户</el-button>
          </div>
          <el-table :data="users" stripe size="small" class="dc-table">
            <el-table-column prop="username" label="用户名" min-width="150" show-overflow-tooltip />
            <el-table-column label="角色" width="100" align="center">
              <template #default="{ row }">
                <el-tag size="small" effect="plain"
                        :type="row.role === 'admin' ? 'danger' : 'info'">
                  {{ row.role === 'admin' ? '管理员' : '普通用户' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="160" align="center" />
            <el-table-column label="操作" width="240" align="center">
              <template #default="{ row }">
                <div class="op-btns">
                  <el-button size="small" type="primary" text bg @click="openUserEdit(row)">编辑</el-button>
                  <el-button size="small" text bg @click="resetUserPwd(row)">重置密码</el-button>
                  <el-button v-if="row.id !== store.user?.id" size="small" type="danger"
                             text bg @click="deleteUser(row)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
          <div class="muted backup-tip">
            普通用户登录后可新增数据，仅能修改、删除自己创建的数据；管理员拥有全部权限。可在「新建用户」中创建账号并分配角色。
          </div>
        </div>
      </el-tab-pane>

      <!-- 表管理 -->
      <el-tab-pane label="表管理" name="tables" v-if="store.isAdmin">
        <div class="pane pane-table">
          <div class="pane-head">
            <div class="pane-title">数据表管理</div>
            <el-button type="primary" :icon="Plus" @click="newTableOpen = true">新建表</el-button>
          </div>
          <el-table :data="tables" stripe size="small" class="dc-table">
            <el-table-column prop="name" label="表名" min-width="180" />
            <el-table-column prop="count" label="数据量" width="90" align="center" />
            <el-table-column label="字段数" width="90" align="center">
              <template #default="{ row }">{{ row.fields?.length || 0 }}</template>
            </el-table-column>
            <el-table-column label="行首色条" width="170" align="center">
              <template #default="{ row }">
                <el-select :model-value="row.color_field || ''" size="small" class="color-field-sel"
                           :disabled="!colorTagFields(row).length"
                           placeholder="不显示"
                           @update:model-value="v => setColorField(row, v)">
                  <el-option label="不显示" value="" />
                  <el-option v-for="f in colorTagFields(row)" :key="f.key"
                             :label="f.label" :value="f.key" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="232" align="center">
              <template #default="{ row }">
                <div class="op-btns">
                  <el-button size="small" type="primary" text bg @click="openFields(row)">字段管理</el-button>
                  <el-button size="small" text bg @click="renameTable(row)">重命名</el-button>
                  <el-button size="small" type="danger" text bg @click="deleteTable(row)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- 仪表盘 -->
      <el-tab-pane label="仪表盘" name="dashboard" v-if="store.isAdmin">
        <div class="pane pane-table">
          <div class="pane-head">
            <div class="pane-title">仪表盘汇总卡片</div>
            <div class="inline-row">
              <el-button :loading="cardsSaving" @click="resetCards">恢复默认</el-button>
              <el-button type="primary" :icon="Plus" @click="openCardEdit(null)">添加卡片</el-button>
            </div>
          </div>
          <div class="muted backup-tip" style="margin-bottom: 10px">
            卡片按下方顺序展示在仪表盘顶部与图表区。统计范围选「全部数据表」时按条数跨表合计；
            选择具体表并指定分组字段，即可得到该字段的分布或排行。
          </div>
          <el-table :data="cards" stripe size="small" class="dc-table">
            <el-table-column prop="title" label="卡片标题" min-width="140" />
            <el-table-column label="类型" width="96" align="center">
              <template #default="{ row }">
                <el-tag size="small" effect="plain">{{ CARD_TYPES[row.type] || row.type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="统计范围" min-width="150">
              <template #default="{ row }">{{ cardScopeName(row) }}</template>
            </el-table-column>
            <el-table-column label="统计内容" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">{{ cardSummary(row) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="248" align="center">
              <template #default="{ row, $index }">
                <div class="op-btns">
                  <el-button size="small" text bg :disabled="$index === 0"
                             @click="moveCard($index, -1)">上移</el-button>
                  <el-button size="small" text bg :disabled="$index === cards.length - 1"
                             @click="moveCard($index, 1)">下移</el-button>
                  <el-button size="small" type="primary" text bg @click="openCardEdit(row)">编辑</el-button>
                  <el-button size="small" type="danger" text bg @click="deleteCard($index)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- 通知 -->
      <el-tab-pane label="微信通知" name="notify" v-if="store.isAdmin">
        <div class="pane">
          <div class="pane-center">
            <div class="pane-title">微信通知</div>
            <el-form label-width="130px" class="set-form">
            <el-form-item label="启用通知">
              <el-switch v-model="notifyOn" />
            </el-form-item>
            <el-form-item label="通知渠道">
              <el-radio-group v-model="form.notify_type" :disabled="!notifyOn">
                <el-radio value="robot">企业微信群机器人</el-radio>
                <el-radio value="wecom_app">企业微信应用通知</el-radio>
              </el-radio-group>
            </el-form-item>
            <template v-if="form.notify_type === 'robot'">
              <el-form-item label="Webhook 地址">
                <el-input v-model="form.notify_webhook" :disabled="!notifyOn"
                          placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=…"
                          style="max-width: 520px" />
              </el-form-item>
            </template>
            <template v-else>
              <el-form-item label="企业 ID">
                <el-input v-model="form.notify_corpid" :disabled="!notifyOn"
                          placeholder="企业微信管理后台 - 我的企业 - 企业信息" style="max-width: 320px" />
              </el-form-item>
              <el-form-item label="应用密钥">
                <el-input v-model="form.notify_secret" :disabled="!notifyOn" show-password
                          placeholder="自建应用的 Secret" style="max-width: 320px" />
              </el-form-item>
              <el-form-item label="应用 AgentId">
                <el-input v-model="form.notify_agentid" :disabled="!notifyOn"
                          placeholder="自建应用的 AgentId" style="max-width: 320px" />
              </el-form-item>
              <el-form-item label="指定接收人">
                <el-input v-model="form.notify_touser" :disabled="!notifyOn"
                          placeholder="成员账号，多人用 | 分隔，默认 @all" style="max-width: 320px" />
              </el-form-item>
            </template>
            <el-form-item label="消息类型">
              <el-radio-group v-model="form.notify_style" :disabled="!notifyOn">
                <el-radio value="text">文字消息</el-radio>
                <el-radio value="image_text">图文消息</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="通知字体">
              <div class="font-manage">
                <div class="font-row">
                  <el-select v-model="form.notify_font" :disabled="!notifyOn" style="width: 240px">
                    <el-option label="系统默认字体" value="" />
                    <el-option v-for="f in fonts" :key="f.name" :label="f.name" :value="f.name" />
                  </el-select>
                  <el-upload :show-file-list="false" :auto-upload="false" accept=".ttf,.otf,.ttc"
                             :disabled="!notifyOn" :on-change="onFontUpload">
                    <el-button :disabled="!notifyOn" :loading="fontUploading">上传字体</el-button>
                  </el-upload>
                </div>
                <div v-if="fonts.length" class="font-list">
                  <div v-for="f in fonts" :key="f.name" class="font-item">
                    <span class="font-name" :title="f.name">{{ f.name }}</span>
                    <span class="muted font-size">{{ fmtSize(f.size) }}</span>
                    <el-button size="small" type="danger" text bg @click="delFont(f)">删除</el-button>
                  </div>
                </div>
                <div class="field-hint muted">封面图使用的字体，可上传中文 TTF / OTF 字体，选择后点击「保存设置」生效</div>
              </div>
            </el-form-item>
            <el-form-item label="触发事件">
              <div class="inline-row">
                <el-checkbox v-model="notifyAdd" :disabled="!notifyOn">新增数据时通知</el-checkbox>
                <el-checkbox v-model="notifyDel" :disabled="!notifyOn">删除数据时通知</el-checkbox>
              </div>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="saving" @click="saveNotify">保存设置</el-button>
              <el-button :disabled="!notifyOn" :loading="testing" @click="testNotify">发送测试通知</el-button>
            </el-form-item>
          </el-form>
          </div>
        </div>
      </el-tab-pane>

      <!-- 个性化 -->
      <el-tab-pane label="个性化" name="theme">
        <div class="pane">
          <div class="pane-center pane-theme">
            <div class="pane-title">主题与外观</div>
            <div class="theme-grid">
              <div v-for="t in THEMES" :key="t.id" class="theme-card"
                   :class="{ active: store.theme === t.id }" @click="store.setTheme(t.id)">
                <div class="theme-colors">
                  <span :style="{ background: t.color }" />
                  <span :style="{ background: mix(t.color) }" />
                </div>
                <div class="theme-name">{{ t.name }}</div>
                <el-icon v-if="store.theme === t.id" class="theme-check"><Check /></el-icon>
              </div>
            </div>
            <div class="dark-row">
              <div>
                <div>暗色模式</div>
                <div class="muted" style="font-size: 12px">深色背景下同色系低亮度配色</div>
              </div>
              <el-switch :model-value="store.dark" @update:model-value="store.setDark" />
            </div>
            <div class="dark-row" v-if="store.isAdmin">
              <div>
                <div>表格边框</div>
                <div class="muted" style="font-size: 12px">开启后所有表格显示列分隔线，全局生效</div>
              </div>
              <el-switch :model-value="store.vborder" @update:model-value="store.setVborder" />
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- 账户安全 -->
      <el-tab-pane label="账户安全" name="security">
        <div class="pane">
          <div class="pane-center">
            <div class="pane-title">账户安全</div>
            <el-form label-width="90px" class="set-form" ref="pwdFormRef" :model="pwd">
              <el-form-item label="原密码">
                <el-input v-model="pwd.old" type="password" show-password />
              </el-form-item>
              <el-form-item label="新密码">
                <el-input v-model="pwd.new" type="password" show-password placeholder="至少 4 位" />
              </el-form-item>
              <el-form-item label="确认新密码">
                <el-input v-model="pwd.confirm" type="password" show-password />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="pwdSaving" @click="changePwd">修改密码</el-button>
              </el-form-item>
            </el-form>
            <div class="avatar-row">
              <el-avatar :size="56" :src="avatarUrl"
                         style="background: var(--dc-primary); font-size: 22px; flex: none">A</el-avatar>
              <div class="avatar-info">
                <div class="avatar-name">{{ store.user?.username }}</div>
                <div class="muted" style="font-size: 12px">支持 PNG / JPG / GIF / WebP，上传后自动替换旧头像</div>
              </div>
              <el-upload :show-file-list="false" :auto-upload="false" accept="image/*"
                         :on-change="onAvatarChange">
                <el-button>更换头像</el-button>
              </el-upload>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- 备份恢复 -->
      <el-tab-pane label="备份恢复" name="backup" v-if="store.isAdmin">
        <div class="pane pane-backup">
          <div class="pane-head">
            <div class="pane-title">备份与恢复</div>
            <div class="backup-actions">
              <el-switch v-model="autoBackup" active-text="每日自动备份" @change="onAutoBackup" />
              <el-button type="primary" :icon="FolderAdd" :loading="backing" @click="doBackup">立即备份</el-button>
            </div>
          </div>
          <el-table :data="backups" stripe size="small" class="dc-table" v-loading="backupsLoading">
            <template #empty>
              <el-empty description="暂无备份，点击「立即备份」创建" :image-size="64" />
            </template>
            <el-table-column prop="name" label="文件名" min-width="230" show-overflow-tooltip />
            <el-table-column label="大小" width="90" align="center">
              <template #default="{ row }">{{ fmtSize(row.size) }}</template>
            </el-table-column>
            <el-table-column prop="created_at" label="备份时间" width="165" align="center" />
            <el-table-column label="操作" width="196" align="center">
              <template #default="{ row }">
                <div class="op-btns">
                  <el-button size="small" type="primary" text bg @click="downloadBk(row)">下载</el-button>
                  <el-button size="small" text bg @click="restoreBk(row)">恢复</el-button>
                  <el-button size="small" type="danger" text bg @click="deleteBk(row)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
          <div class="muted backup-tip">
            备份包含全部数据表与系统数据，保存在服务器数据目录 backups 下，最多保留 10 个。
            恢复将用备份文件覆盖当前全部数据，请谨慎操作。
          </div>
        </div>
      </el-tab-pane>

      <!-- 关于 -->
      <el-tab-pane label="关于" name="about">
        <div class="pane">
          <div class="pane-center">
            <div class="pane-title">关于系统</div>
          <div class="about-hero">
            <Logo :size="56" />
            <div>
              <div class="about-full">{{ store.site.name }}</div>
              <div class="muted">{{ store.site.app || 'DataLoom' }} · {{ store.site.subtitle }}</div>
            </div>
          </div>
          <div class="about-items">
            <div class="about-li"><span class="muted">版本</span><b>v{{ store.site.version }}</b></div>
            <div class="about-li"><span class="muted">作者</span><b>{{ store.site.author }}</b></div>
            <div class="about-li">
              <span class="muted">GitHub</span>
              <el-link type="primary" :href="store.site.github" target="_blank">{{ store.site.github }}</el-link>
            </div>
          </div>
          <div class="muted about-log-title">更新内容</div>
          <div v-for="log in store.site.changelog" :key="log.version" class="changelog">
            <b>v{{ log.version }}（{{ log.date }}）</b>
            <ul>
              <li v-for="i in log.items" :key="i">{{ i }}</li>
            </ul>
          </div>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 新建表 -->
    <el-dialog v-model="newTableOpen" title="新建数据表" width="460px" append-to-body destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="表名" required>
          <el-input v-model="newTableName" placeholder="请输入新表名称" maxlength="40" />
        </el-form-item>
        <el-form-item label="字段模板">
          <el-radio-group v-model="newTableTemplate" class="tpl-group">
            <el-radio value="blank" border size="small">空白自定义</el-radio>
            <el-radio v-for="t in tables" :key="t.id" :value="`table:${t.id}`" border size="small">
              {{ t.name }}
            </el-radio>
          </el-radio-group>
          <div class="field-hint muted">选择已有表将复制其字段结构（不含数据）</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="newTableOpen = false">取 消</el-button>
        <el-button type="primary" :loading="creatingTable" @click="createTable">创 建</el-button>
      </template>
    </el-dialog>

    <!-- 仪表盘卡片 -->
    <el-dialog v-model="cardOpen" :title="cardForm.index === null ? '添加汇总卡片' : '编辑汇总卡片'"
               width="520px" append-to-body destroy-on-close>
      <el-form label-width="100px">
        <el-form-item label="卡片标题" required>
          <el-input v-model="cardForm.title" maxlength="20" placeholder="如：数据总量 / 按分类统计" />
        </el-form-item>
        <el-form-item label="展示类型">
          <el-radio-group v-model="cardForm.type">
            <el-radio value="stat">数值卡</el-radio>
            <el-radio value="pie">分布饼图</el-radio>
            <el-radio value="rank">排行榜</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="统计范围">
          <el-select v-model="cardForm.scope" class="w-full">
            <el-option label="全部数据表（跨表合计）" value="all" />
            <el-option v-for="t in tables" :key="t.id" :label="t.name" :value="`table:${t.id}`" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="cardForm.type === 'stat'" label="统计周期">
          <el-radio-group v-model="cardForm.period">
            <el-radio value="all">全部</el-radio>
            <el-radio value="today">今日</el-radio>
            <el-radio value="week">近 7 天</el-radio>
            <el-radio value="month">近 30 天</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-else label="分组字段">
          <el-select v-model="cardForm.dimension" class="w-full" filterable allow-create
                     default-first-option placeholder="选择字段，或输入 __table__ 按表分组">
            <el-option label="按数据表分组" value="__table__" />
            <el-option v-for="f in cardFields" :key="f.key" :label="f.label" :value="f.key" />
          </el-select>
          <div class="field-hint muted" v-if="cardForm.scope === 'all'">
            统计全部表时，仅汇总各表中存在该字段的记录
          </div>
        </el-form-item>
        <el-form-item label="聚合方式">
          <el-select v-model="cardForm.agg" class="w-full">
            <el-option label="计数（条数）" value="count" />
            <el-option label="求和" value="sum" />
            <el-option label="平均值" value="avg" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="cardForm.agg !== 'count'" label="数值字段">
          <el-select v-model="cardForm.metric" class="w-full" filterable placeholder="选择用于计算的数字字段">
            <el-option v-for="f in numberFields" :key="f.key" :label="f.label" :value="f.key" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="cardForm.type !== 'stat'" label="显示条数">
          <el-input-number v-model="cardForm.limit" :min="3" :max="50" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cardOpen = false">取 消</el-button>
        <el-button type="primary" :loading="cardsSaving" @click="saveCard">保 存</el-button>
      </template>
    </el-dialog>

    <!-- 字段管理 -->
    <el-dialog v-model="fieldsOpen" :title="`字段管理 · ${fieldsTable?.name || ''}`"
               width="720px" append-to-body destroy-on-close>
      <div class="fields-head">
        <span class="muted">所有字段均可重命名、改类型或删除；下拉类字段的新值将自动加入可选值</span>
        <el-button type="primary" size="small" :icon="Plus" @click="openFieldEdit(null)">添加字段</el-button>
      </div>
      <el-table :data="editFields" stripe size="small" class="dc-table">
        <el-table-column prop="label" label="字段名" min-width="110" />
        <el-table-column label="类型" width="108" align="center">
          <template #default="{ row }">
            <el-tooltip :content="FIELD_TIPS[row.type] || typeLabel(row.type)" placement="top">
              <el-tag size="small" effect="plain" class="type-tag">{{ typeLabel(row.type) }}</el-tag>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="必填" width="60" align="center">
          <template #default="{ row }">{{ row.required ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column prop="default_value" label="默认值" width="90" show-overflow-tooltip>
          <template #default="{ row }">{{ row.default_value || '—' }}</template>
        </el-table-column>
        <el-table-column label="可选值" min-width="150">
          <template #default="{ row }">
            <el-tooltip v-if="isSelType(row.type) || row.type === 'color_tag'"
                        :content="optionSummary(row)" placement="top">
              <div class="opt-cell">
                <template v-if="row.type === 'color_tag'">
                  <span v-for="o in colorOptions(row).slice(0, 2)" :key="o.value" class="opt-badge"
                        :style="{ background: o.color, color: textColor(o.color) }">{{ o.value }}</span>
                  <span v-if="colorOptions(row).length > 2" class="muted">+{{ colorOptions(row).length - 2 }}</span>
                  <span v-if="!colorOptions(row).length" class="muted">暂无</span>
                </template>
                <template v-else>
                  <el-tag v-for="o in (row.options || []).slice(0, 3)" :key="o" size="small"
                          style="margin-right: 4px" effect="plain">{{ o }}</el-tag>
                  <span v-if="(row.options || []).length > 3" class="muted">+{{ row.options.length - 3 }}</span>
                  <span v-if="!(row.options || []).length" class="muted">暂无</span>
                </template>
              </div>
            </el-tooltip>
            <el-tooltip v-else-if="row.type === 'rating'" content="星级评分" placement="top">
              <span class="muted">最多 {{ ratingMax(row) }} 星</span>
            </el-tooltip>
            <el-tooltip v-else-if="row.type === 'number'" :content="numSummary(row)" placement="top">
              <span class="muted">{{ numSummary(row) }}</span>
            </el-tooltip>
            <el-tooltip v-else-if="row.type === 'date_diff'"
                        :content="diffSummary(row) || '未指定起止字段'" placement="top">
              <span class="muted">{{ diffSummary(row) || '未配置' }}</span>
            </el-tooltip>
            <el-tooltip v-else-if="row.type === 'quantity'" :content="qtySummary(row)" placement="top">
              <span class="muted">{{ qtySummary(row) }}</span>
            </el-tooltip>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="排序" width="96" align="center">
          <template #default="{ $index }">
            <div class="op-btns">
              <el-button size="small" text bg :icon="ArrowUp" :disabled="$index === 0"
                         title="上移" @click="moveField($index, -1)" />
              <el-button size="small" text bg :icon="ArrowDown"
                         :disabled="$index === editFields.length - 1"
                         title="下移" @click="moveField($index, 1)" />
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="132" align="center">
          <template #default="{ row }">
            <div class="op-btns">
              <el-button size="small" type="primary" text bg @click="openFieldEdit(row)">编辑</el-button>
              <el-button size="small" type="danger" text bg @click="deleteField(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 字段编辑 -->
    <el-dialog v-model="fieldOpen" :title="fieldForm.id ? '编辑字段' : '添加字段'"
               width="480px" append-to-body destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="字段名称" required>
          <el-input v-model="fieldForm.label" maxlength="20"
                    placeholder="如：设计负责人" />
        </el-form-item>
        <el-form-item label="字段类型">
          <el-select v-model="fieldForm.type" class="w-full" @change="onFieldTypeChange">
            <el-option v-for="(label, t) in FIELD_TYPES" :key="t" :label="label" :value="t" />
          </el-select>
          <div class="field-tip muted">{{ FIELD_TIPS[fieldForm.type] || '' }}</div>
        </el-form-item>
        <el-form-item label="是否必填">
          <el-switch v-model="fieldForm.required" />
        </el-form-item>
        <el-form-item v-if="!isSelType(fieldForm.type) && !isSpecialType(fieldForm.type)" label="默认值">
          <el-date-picker v-if="fieldForm.type === 'date'" v-model="fieldForm.default_value"
                          type="date" value-format="YYYY-MM-DD" class="w-full" />
          <el-date-picker v-else-if="fieldForm.type === 'datetime'" v-model="fieldForm.default_value"
                          type="datetime" value-format="YYYY-MM-DD HH:mm:ss" class="w-full" />
          <el-switch v-else-if="fieldForm.type === 'switch'" v-model="fieldForm.default_value" />
          <el-input v-else v-model="fieldForm.default_value" placeholder="留空则无默认值" />
        </el-form-item>
        <el-form-item v-if="fieldForm.type === 'number'" label="小数位">
          <el-select v-model="fieldForm.numPrecision" class="w-full">
            <el-option label="不限制" value="" />
            <el-option v-for="n in [0, 1, 2, 3, 4, 5, 6]" :key="n"
                       :label="`保留 ${n} 位小数`" :value="n" />
          </el-select>
          <div class="field-tip muted">存入与导入时按该精度自动取整，留空表示不处理</div>
        </el-form-item>
        <el-form-item v-if="isSelType(fieldForm.type)" label="可选值">
          <el-select v-model="fieldForm.options" multiple filterable allow-create
                     default-first-option placeholder="输入后回车添加，可预先配置" class="w-full">
            <el-option v-for="o in fieldForm.options" :key="o" :label="o" :value="o" />
          </el-select>
        </el-form-item>
        <!-- 彩色标签：逐项配置文字与颜色 -->
        <el-form-item v-if="fieldForm.type === 'color_tag'" label="可选值">
          <div class="ct-editor">
            <div v-for="(o, i) in fieldForm.colorList" :key="i" class="ct-row">
              <el-color-picker v-model="o.color" size="small" :predefine="PRESET_COLORS" />
              <el-input v-model="o.value" placeholder="选项文字" maxlength="20" />
              <el-button link type="danger" :icon="Delete" @click="fieldForm.colorList.splice(i, 1)" />
            </div>
            <el-button size="small" :icon="Plus" @click="addColorOption">添加选项</el-button>
            <div class="field-tip muted">颜色可留空，保存时自动分配；值可以为空，数据留空时显示无颜色</div>
          </div>
        </el-form-item>
        <!-- 评分：满分星数 -->
        <el-form-item v-if="fieldForm.type === 'rating'" label="满分星数">
          <el-input-number v-model="fieldForm.ratingMax" :min="3" :max="10" :step="1" />
        </el-form-item>
        <!-- 日期差值：起始条件 + 起止日期字段 -->
        <el-form-item v-if="fieldForm.type === 'date_diff'" label="起始条件">
          <el-select v-model="fieldForm.ddStartField" clearable
                     placeholder="不启用（按起始日期计算）" class="w-full"
                     @change="onDdStartFieldChange">
            <el-option v-for="f in statusFields" :key="f.key" :label="f.label" :value="f.key" />
          </el-select>
          <div class="field-tip muted">
            启用后，字段命中起始取值时才开始计算；切走后清零，再次命中重新起算
          </div>
        </el-form-item>
        <el-form-item v-if="fieldForm.type === 'date_diff' && fieldForm.ddStartField" label="起始取值">
          <el-select v-model="fieldForm.ddStartValues" multiple clearable
                     placeholder="选择触发开始的取值" class="w-full">
            <el-option v-for="v in ddStartValueOptions" :key="v" :label="v" :value="v" />
          </el-select>
          <div class="field-tip muted">
            命中任一取值即从变更当天起算；未命中时显示 0 天
          </div>
        </el-form-item>
        <el-form-item v-if="fieldForm.type === 'date_diff'" label="起始日期">
          <el-select v-model="fieldForm.ddStart" placeholder="选择日期字段" class="w-full">
            <el-option v-for="f in dateFields" :key="f.key" :label="f.label" :value="f.key" />
          </el-select>
          <div class="field-tip muted">未配置起始条件时按该日期字段计算</div>
        </el-form-item>
        <el-form-item v-if="fieldForm.type === 'date_diff'" label="结束日期">
          <el-select v-model="fieldForm.ddEnd" placeholder="留空表示按今天计算" clearable class="w-full">
            <el-option v-for="f in dateFields" :key="f.key" :label="f.label" :value="f.key" />
          </el-select>
          <div class="field-tip muted">留空则持续计算到今天（适合「进行中」的项目）</div>
        </el-form-item>
        <el-form-item v-if="fieldForm.type === 'date_diff'" label="终态条件">
          <el-select v-model="fieldForm.ddStatus" clearable
                     placeholder="不启用（一直计算到今天）" class="w-full"
                     @change="onDdStatusChange">
            <el-option v-for="f in statusFields" :key="f.key" :label="f.label" :value="f.key" />
          </el-select>
          <div class="field-tip muted">
            结束日期留空时，命中终态即停止累加；需选择状态类字段
          </div>
        </el-form-item>
        <el-form-item v-if="fieldForm.type === 'date_diff' && fieldForm.ddStatus" label="终态取值">
          <el-select v-model="fieldForm.ddValues" multiple clearable
                     placeholder="选择视为结束的取值" class="w-full">
            <el-option v-for="v in ddValueOptions" :key="v" :label="v" :value="v" />
          </el-select>
          <div class="field-tip muted">
            命中任一取值即视为结束，日期差值冻结在状态变更为终态的那一天
          </div>
        </el-form-item>
        <el-form-item v-if="fieldForm.type === 'quantity'" label="合计方式">
          <el-radio-group v-model="fieldForm.qtyMode">
            <el-radio value="auto" border size="small">按分项自动合计</el-radio>
            <el-radio value="manual" border size="small">手动填总数</el-radio>
          </el-radio-group>
          <div class="field-tip muted">
            自动合计时总数恒等于分项之和；手动填写时总数可大于分项之和（余额视为未分配）
          </div>
        </el-form-item>
        <el-form-item v-if="fieldForm.type === 'quantity'" label="单位">
          <el-input v-model="fieldForm.qtyUnit" maxlength="8" placeholder="如：套、面、个，可留空" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="fieldOpen = false">取 消</el-button>
        <el-button type="primary" :loading="savingField" @click="saveField">保 存</el-button>
      </template>
    </el-dialog>

    <!-- 新建用户 -->
    <el-dialog v-model="userOpen" title="新建用户" width="440px" append-to-body destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="用户名" required>
          <el-input v-model="userForm.username" placeholder="登录账号，40 字以内" maxlength="40" />
        </el-form-item>
        <el-form-item label="初始密码" required>
          <el-input v-model="userForm.password" placeholder="至少 4 位" show-password />
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="userForm.role">
            <el-radio value="user">普通用户</el-radio>
            <el-radio value="admin">管理员</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userOpen = false">取 消</el-button>
        <el-button type="primary" :loading="userSaving" @click="createUser">创 建</el-button>
      </template>
    </el-dialog>

    <!-- 编辑用户 -->
    <el-dialog v-model="userEditOpen" title="编辑用户" width="440px" append-to-body destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="用户名" required>
          <el-input v-model="userEdit.username" placeholder="登录账号，40 字以内" maxlength="40" />
          <div class="field-hint muted">用户名不是真实姓名时可在此修改，其历史数据的创建人将同步更新</div>
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="userEdit.role" :disabled="userEdit.id === store.user?.id">
            <el-radio value="user">普通用户</el-radio>
            <el-radio value="admin">管理员</el-radio>
          </el-radio-group>
          <div class="field-hint muted" v-if="userEdit.id === store.user?.id">不能修改自己的角色</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userEditOpen = false">取 消</el-button>
        <el-button type="primary" :loading="userEditSaving" @click="saveUserEdit">保 存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, FolderAdd, Delete, ArrowUp, ArrowDown } from '@element-plus/icons-vue'
import { http, downloadBlob } from '@/api'
import { useApp, THEMES } from '@/store'
import Logo from '@/components/Logo.vue'

const store = useApp()
const route = useRoute()
const router = useRouter()

const tab = ref('basic')
watch(tab, () => router.replace({ query: { ...route.query, tab: tab.value } }))

const FIELD_TYPES = {
  text: '文本', textarea: '多行文本', number: '数字', select: '可搜索下拉',
  multi_select: '多选下拉', radio: '单选组', checkbox: '复选组', switch: '开关',
  date: '日期', datetime: '日期时间',
  color_tag: '彩色标签', rating: '评分', date_diff: '日期差值',
  quantity: '数量明细', contact: '联系方式'
}
const FIELD_TIPS = {
  select: '可搜索，输入新值会自动加入可选值',
  multi_select: '可搜索多选，输入新值会自动加入可选值',
  radio: '平铺单选，只能从已配置的可选值中选择',
  checkbox: '平铺多选，可勾选多个可选值',
  color_tag: '单选 + 每个选项自定义颜色，可为空；可指定用于行首色条',
  rating: '点击星星打分，存数字，可排序与求平均',
  date_diff: '自动计算两个日期间的天数，并以「天 / 个月 / 年」显示',
  quantity: '总数 + 一层分项明细，可统计总数；明细仅展开查看，不参与拆分统计',
  contact: '手机 / 座机 / 400 / 邮箱，多个用、分隔，保存时校验格式',
  switch: '开关，存 1 / 0',
  date: '日期',
  datetime: '日期时间',
  number: '数字，可配置小数位精度',
  text: '单行文本',
  textarea: '多行文本'
}
const typeLabel = t => FIELD_TYPES[t] || t
const isSelType = t => ['select', 'multi_select', 'radio', 'checkbox'].includes(t)
const mix = c => `color-mix(in srgb, ${c} 40%, #e8edf2)`

/* ---------------- 基本设置 ---------------- */
const form = reactive({})
const saving = ref(false)
const guestOptions = [
  { label: '关闭', value: 'off' },
  { label: '只读浏览', value: 'readonly' },
  { label: '可添加', value: 'add' }
]
const logAutoBool = ref(false)
const notifyOn = ref(false)
const notifyAdd = ref(true)
const notifyDel = ref(true)
const testing = ref(false)
const registerBool = ref(false)

watch(logAutoBool, v => { form.log_auto_clear = v ? '1' : '0' })
watch(registerBool, v => { form.allow_register = v ? '1' : '0' })
watch(notifyOn, v => { form.notify_enabled = v ? '1' : '0' })
watch(notifyAdd, v => { form.notify_on_add = v ? '1' : '0' })
watch(notifyDel, v => { form.notify_on_delete = v ? '1' : '0' })

async function loadSettings() {
  const res = await http.get('/settings')
  Object.assign(form, res.settings)
  if (!guestOptions.some(o => o.value === form.guest_mode)) form.guest_mode = 'off'
  logAutoBool.value = form.log_auto_clear === '1'
  registerBool.value = form.allow_register === '1'
  notifyOn.value = form.notify_enabled === '1'
  notifyAdd.value = form.notify_on_add === '1'
  notifyDel.value = form.notify_on_delete === '1'
}

async function saveBasic() {
  if (!form.site_name?.trim()) return ElMessage.warning('系统名称不能为空')
  saving.value = true
  try {
    await http.put('/settings', {
      site_name: form.site_name.trim(),
      site_org: (form.site_org || '').trim(),
      site_subtitle: (form.site_subtitle || '').trim(),
      guest_mode: form.guest_mode,
      allow_register: form.allow_register,
      log_auto_clear: form.log_auto_clear, log_retention_days: String(form.log_retention_days)
    })
    await store.init(true)
    ElMessage.success('设置已保存')
  } finally { saving.value = false }
}

/* ---------------- 品牌 Logo ---------------- */
const logoUploading = ref(false)

async function onLogoChange(file) {
  if (!file?.raw) return
  const fd = new FormData()
  fd.append('file', file.raw)
  logoUploading.value = true
  try {
    const res = await http.post('/site/logo', fd)
    store.site.logo = res.logo
    ElMessage.success('Logo 已更新')
  } finally { logoUploading.value = false }
}

async function removeLogo() {
  await http.post('/site/logo/delete')
  store.site.logo = ''
  ElMessage.success('已恢复默认 Logo')
}

async function saveNotify() {
  saving.value = true
  try {
    await http.put('/settings', {
      notify_enabled: form.notify_enabled, notify_type: form.notify_type,
      notify_webhook: form.notify_webhook, notify_corpid: form.notify_corpid,
      notify_secret: form.notify_secret, notify_agentid: form.notify_agentid,
      notify_touser: form.notify_touser, notify_style: form.notify_style,
      notify_font: form.notify_font || '',
      notify_on_add: form.notify_on_add, notify_on_delete: form.notify_on_delete
    })
    ElMessage.success('通知设置已保存')
  } finally { saving.value = false }
}

/* ---------------- 通知字体 ---------------- */
const fonts = ref([])
const fontUploading = ref(false)

async function loadFonts() {
  const res = await http.get('/notify/fonts')
  fonts.value = res.fonts || []
}

async function onFontUpload(file) {
  const fd = new FormData()
  fd.append('file', file.raw)
  fontUploading.value = true
  try {
    const res = await http.post('/notify/fonts', fd)
    ElMessage.success(`字体「${res.name}」已上传，已自动选中`)
    form.notify_font = res.name
    await loadFonts()
  } finally { fontUploading.value = false }
}

async function delFont(f) {
  try {
    await ElMessageBox.confirm(`确定删除字体「${f.name}」吗？`, '删除字体',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  await http.post(`/notify/fonts/${encodeURIComponent(f.name)}`)
  if (form.notify_font === f.name) form.notify_font = ''
  ElMessage.success('已删除')
  await loadFonts()
}

async function testNotify() {
  testing.value = true
  try {
    await saveNotify()
    const res = await http.post('/notify/test')
    if (res.ok) ElMessage.success(res.message || '测试通知已发送')
    else ElMessage.error(res.message || '发送失败')
  } finally { testing.value = false }
}

/* ---------------- 备份与恢复 ---------------- */
const backups = ref([])
const backupsLoading = ref(false)
const backing = ref(false)
const autoBackup = ref(true)

async function loadBackups() {
  backupsLoading.value = true
  try {
    const res = await http.get('/backups')
    backups.value = res.items || []
    autoBackup.value = !!res.enabled
  } finally { backupsLoading.value = false }
}

async function onAutoBackup(v) {
  await http.put('/settings', { backup_enabled: v ? '1' : '0' })
  ElMessage.success(v ? '已开启每日自动备份' : '已关闭自动备份')
}

async function doBackup() {
  backing.value = true
  try {
    await http.post('/backups')
    ElMessage.success('备份完成')
    await loadBackups()
  } finally { backing.value = false }
}

function fmtSize(n) {
  if (n >= 1048576) return (n / 1048576).toFixed(1) + ' MB'
  if (n >= 1024) return (n / 1024).toFixed(1) + ' KB'
  return n + ' B'
}

async function downloadBk(row) {
  const res = await http.get(`/backups/${row.name}/download`, { responseType: 'blob' })
  downloadBlob(res, row.name)
}

async function restoreBk(row) {
  try {
    await ElMessageBox.confirm(
      `确定用备份「${row.name}」覆盖当前全部数据吗？此操作不可撤销。`,
      '恢复备份', { type: 'warning', confirmButtonText: '恢复', cancelButtonText: '取消' })
  } catch { return }
  const res = await http.post('/backups/restore', { name: row.name })
  ElMessage.success(res.message || '恢复完成，即将刷新页面')
  setTimeout(() => location.reload(), 900)
}

async function deleteBk(row) {
  try {
    await ElMessageBox.confirm(`确定删除备份「${row.name}」吗？`, '删除备份',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  await http.post(`/backups/${row.name}`)
  ElMessage.success('已删除')
  await loadBackups()
}

/* ---------------- 表管理 ---------------- */
const tables = ref([])
const newTableOpen = ref(false)
const newTableName = ref('')
const newTableTemplate = ref('blank')
const creatingTable = ref(false)

const fieldsOpen = ref(false)
const fieldsTable = ref(null)
const editFields = ref([])
const fieldOpen = ref(false)
const savingField = ref(false)
const fieldForm = reactive({
  id: null, table_id: null, label: '', type: 'text', required: false,
  default_value: '', options: [], is_system: false,
  colorList: [], ratingMax: 5, ddStart: '', ddEnd: '', ddStatus: '', ddValues: [],
  ddStartField: '', ddStartValues: [], numPrecision: '',
  qtyMode: 'auto', qtyUnit: ''
})

const PRESET_COLORS = ['#2f9e44', '#e8a33d', '#d94b4b', '#5470c6',
                       '#13a8a8', '#8f5bd6', '#d969a8', '#6b7a8f']
const FALLBACK_COLORS = PRESET_COLORS

function isSpecialType(t) {
  return ['color_tag', 'rating', 'date_diff', 'quantity'].includes(t)
}

function colorOptions(f) {
  return (f.options || []).map((o, i) => (o && typeof o === 'object'
    ? { value: String(o.value ?? ''), color: o.color || FALLBACK_COLORS[i % 8] }
    : { value: String(o ?? ''), color: FALLBACK_COLORS[i % 8] }))
    .filter(o => o.value !== '')
}
function ratingMaxOf(f) {
  const m = f.options && typeof f.options === 'object' ? Number(f.options.max) : 5
  return Number.isFinite(m) && m >= 3 ? m : 5
}
function ratingMax(f) { return ratingMaxOf(f) }
function textColor(hex) {
  const c = String(hex || '').replace('#', '')
  if (c.length !== 6) return '#fff'
  const r = parseInt(c.slice(0, 2), 16)
  const g = parseInt(c.slice(2, 4), 16)
  const b = parseInt(c.slice(4, 6), 16)
  return (r * 299 + g * 587 + b * 114) / 1000 > 160 ? '#1f2329' : '#fff'
}
function optionSummary(row) {
  const list = row.type === 'color_tag' ? colorOptions(row).map(o => o.value)
    : (row.options || []).map(o => String(o))
  return list.length ? list.join('、') : '暂无可选值'
}
function diffSummary(row) {
  const cfg = row.options && typeof row.options === 'object' ? row.options : {}
  const label = k => (fieldsTable.value?.fields || []).find(f => f.key === k)?.label || k
  if (!cfg.start) return ''
  const s = `${label(cfg.start)} → ${cfg.end ? label(cfg.end) : '今天'}`
  const bits = []
  if (cfg.start_field && (cfg.start_values || []).length) {
    bits.push(`命中 ${label(cfg.start_field)} 后起算`)
  }
  if (cfg.end_field && (cfg.end_values || []).length) bits.push('终态冻结')
  return bits.length ? `${s}；${bits.join('，')}` : s
}
function numSummary(row) {
  const cfg = row.options && typeof row.options === 'object' ? row.options : {}
  return Number.isFinite(Number(cfg.precision)) && cfg.precision !== null
    ? `精确到 ${cfg.precision} 位小数` : '不限小数位'
}
function qtySummary(row) {
  const cfg = row.options && typeof row.options === 'object' ? row.options : {}
  const mode = cfg.mode === 'manual' ? '手动总数' : '自动合计'
  return cfg.unit ? `${mode} · 单位 ${cfg.unit}` : `${mode} · 无单位`
}
const dateFields = computed(() =>
  (fieldsTable.value?.fields || []).filter(f =>
    (f.type === 'date' || f.type === 'datetime') && f.id !== fieldForm.id))
const STATUS_FIELD_TYPES = ['select', 'multi_select', 'radio', 'checkbox', 'color_tag']
const statusFields = computed(() =>
  (fieldsTable.value?.fields || []).filter(f =>
    STATUS_FIELD_TYPES.includes(f.type) && f.id !== fieldForm.id))
const ddValueOptions = computed(() => {
  const f = (fieldsTable.value?.fields || []).find(x => x.key === fieldForm.ddStatus)
  return f ? colorOptions(f).map(o => o.value) : []
})
const ddStartValueOptions = computed(() => {
  const f = (fieldsTable.value?.fields || []).find(x => x.key === fieldForm.ddStartField)
  return f ? colorOptions(f).map(o => o.value) : []
})
function onDdStatusChange() { fieldForm.ddValues = [] }
function onDdStartFieldChange() { fieldForm.ddStartValues = [] }
function colorTagFields(row) {
  return (row.fields || []).filter(f => f.type === 'color_tag')
}
function addColorOption() {
  fieldForm.colorList.push({ value: '', color: FALLBACK_COLORS[fieldForm.colorList.length % 8] })
}
function onFieldTypeChange() {
  if (fieldForm.type === 'color_tag' && !fieldForm.colorList.length) {
    fieldForm.colorList = [{ value: '', color: FALLBACK_COLORS[0] }]
  }
}

async function setColorField(row, key) {
  try {
    await http.put(`/tables/${row.id}`, { color_field: key || '' })
    row.color_field = key || ''
    ElMessage.success(key ? '已启用行首色条' : '已关闭行首色条')
  } catch (e) {
    ElMessage.error(e?.message || '保存失败')
  }
}

async function loadTables() {
  const res = await http.get('/tables')
  tables.value = res.tables
}

async function createTable() {
  if (!newTableName.value.trim()) return ElMessage.warning('请输入表名')
  creatingTable.value = true
  try {
    await http.post('/tables', { name: newTableName.value.trim(), template: newTableTemplate.value })
    ElMessage.success('数据表已创建')
    newTableOpen.value = false
    newTableName.value = ''
    newTableTemplate.value = 'blank'
    loadTables()
  } finally { creatingTable.value = false }
}

async function renameTable(row) {
  try {
    const { value } = await ElMessageBox.prompt('请输入新的表名', '重命名数据表', {
      inputValue: row.name, inputPattern: /\S+/, inputErrorMessage: '表名不能为空',
      confirmButtonText: '保存', cancelButtonText: '取消'
    })
    await http.put(`/tables/${row.id}`, { name: value.trim() })
    ElMessage.success('已重命名')
    loadTables()
    store.init()
  } catch { /* 取消 */ }
}

async function deleteTable(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除「${row.name}」吗？该表 ${row.count} 条数据将一并删除，不可恢复。`,
      '删除数据表', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  await http.post(`/tables/${row.id}`)
  ElMessage.success('数据表已删除')
  loadTables()
}

function openFields(row) {
  fieldsTable.value = row
  editFields.value = row.fields || []
  fieldsOpen.value = true
}

async function moveField(index, dir) {
  const target = index + dir
  if (target < 0 || target >= editFields.value.length) return
  const list = editFields.value
  const [item] = list.splice(index, 1)
  list.splice(target, 0, item)
  try {
    await http.post(`/tables/${fieldsTable.value.id}/fields/reorder`,
      { ids: list.map(f => f.id) })
    ElMessage.success('字段顺序已更新，数据表列顺序同步调整')
  } catch (e) {
    ElMessage.error(e?.message || '排序保存失败')
    await loadTables()
    const t = tables.value.find(x => x.id === fieldsTable.value?.id)
    if (t) {
      fieldsTable.value = t
      editFields.value = t.fields || []
    }
  }
}

function openFieldEdit(f) {
  if (f) {
    const raw = f.options
    const isColor = f.type === 'color_tag'
    const isRating = f.type === 'rating'
    const isDiff = f.type === 'date_diff'
    const isQty = f.type === 'quantity'
    const isNum = f.type === 'number'
    const isContact = f.type === 'contact'
    Object.assign(fieldForm, {
      id: f.id, table_id: fieldsTable.value.id, label: f.label, type: f.type,
      required: !!f.required, default_value: f.default_value || '',
      options: (isColor || isRating || isDiff || isQty || isNum || isContact) ? [] : [...(raw || [])],
      colorList: isColor ? colorOptions(f).map(o => ({ ...o })) : [],
      ratingMax: isRating ? ratingMaxOf(f) : 5,
      ddStart: isDiff ? (raw?.start || '') : '',
      ddEnd: isDiff ? (raw?.end || '') : '',
      ddStatus: isDiff ? (raw?.end_field || '') : '',
      ddValues: isDiff && Array.isArray(raw?.end_values) ? [...raw.end_values] : [],
      ddStartField: isDiff ? (raw?.start_field || '') : '',
      ddStartValues: isDiff && Array.isArray(raw?.start_values) ? [...raw.start_values] : [],
      numPrecision: isNum && raw?.precision !== undefined && raw?.precision !== null
        ? Number(raw.precision) : '',
      qtyMode: isQty && raw?.mode === 'manual' ? 'manual' : 'auto',
      qtyUnit: isQty ? (raw?.unit || '') : '',
      is_system: !!f.is_system
    })
  } else {
    Object.assign(fieldForm, {
      id: null, table_id: fieldsTable.value.id, label: '', type: 'text',
      required: false, default_value: '', options: [], is_system: false,
      colorList: [], ratingMax: 5, ddStart: '', ddEnd: '', ddStatus: '', ddValues: [],
      ddStartField: '', ddStartValues: [], numPrecision: '',
      qtyMode: 'auto', qtyUnit: ''
    })
  }
  fieldOpen.value = true
}

async function saveField() {
  if (!fieldForm.label.trim()) return ElMessage.warning('请填写字段名称')
  const t = fieldForm.type
  let options = fieldForm.options
  if (t === 'color_tag') {
    options = fieldForm.colorList
      .map(o => ({ value: String(o.value || '').trim(), color: o.color || '' }))
      .filter(o => o.value)
  } else if (t === 'rating') {
    options = { max: fieldForm.ratingMax }
  } else if (t === 'date_diff') {
    if (!fieldForm.ddStart) return ElMessage.warning('请选择起始日期字段')
    options = { start: fieldForm.ddStart, end: fieldForm.ddEnd || '',
                end_field: fieldForm.ddStatus || '',
                end_values: fieldForm.ddStatus ? [...fieldForm.ddValues] : [],
                start_field: fieldForm.ddStartField || '',
                start_values: fieldForm.ddStartField ? [...fieldForm.ddStartValues] : [] }
  } else if (t === 'quantity') {
    options = { mode: fieldForm.qtyMode === 'manual' ? 'manual' : 'auto',
                unit: String(fieldForm.qtyUnit || '').trim() }
  } else if (t === 'number') {
    options = fieldForm.numPrecision === '' || fieldForm.numPrecision === null
      ? {} : { precision: Number(fieldForm.numPrecision) }
  }
  savingField.value = true
  try {
    const payload = {
      label: fieldForm.label.trim(), type: t,
      required: fieldForm.required ? 1 : 0,
      default_value: String(fieldForm.default_value ?? ''),
      options
    }
    if (fieldForm.id) await http.put(`/fields/${fieldForm.id}`, payload)
    else await http.post(`/tables/${fieldForm.table_id}/fields`, payload)
    ElMessage.success('字段已保存')
    fieldOpen.value = false
    await loadTables()
    const t = tables.value.find(x => x.id === fieldForm.table_id)
    if (t) {
      fieldsTable.value = t
      editFields.value = t.fields || []
    }
  } finally { savingField.value = false }
}

async function deleteField(f) {
  try {
    await ElMessageBox.confirm(
      `确定删除字段「${f.label}」吗？记录中的该字段数据将一并清除。`,
      '删除字段', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  await http.post(`/fields/${f.id}`)
  ElMessage.success('字段已删除')
  await loadTables()
  const t = tables.value.find(x => x.id === fieldsTable.value.id)
  if (t) {
    fieldsTable.value = t
    editFields.value = t.fields || []
  }
}

/* ---------------- 用户管理 ---------------- */
const users = ref([])
const userOpen = ref(false)
const userSaving = ref(false)
const userForm = reactive({ username: '', password: '', role: 'user' })

async function loadUsers() {
  const res = await http.get('/users')
  users.value = res.users || []
}

function openUserCreate() {
  Object.assign(userForm, { username: '', password: '', role: 'user' })
  userOpen.value = true
}

async function createUser() {
  if (!userForm.username.trim()) return ElMessage.warning('请输入用户名')
  if (!userForm.password || userForm.password.length < 4) return ElMessage.warning('初始密码至少 4 位')
  userSaving.value = true
  try {
    await http.post('/users', {
      username: userForm.username.trim(), password: userForm.password, role: userForm.role
    })
    ElMessage.success('用户已创建')
    userOpen.value = false
    loadUsers()
  } finally { userSaving.value = false }
}

/* ---------------- 编辑用户 ---------------- */
const userEditOpen = ref(false)
const userEditSaving = ref(false)
const userEdit = reactive({ id: null, username: '', role: 'user' })

function openUserEdit(row) {
  Object.assign(userEdit, { id: row.id, username: row.username, role: row.role || 'user' })
  userEditOpen.value = true
}

async function saveUserEdit() {
  const name = userEdit.username.trim()
  if (!name) return ElMessage.warning('请输入用户名')
  if (name.length > 40) return ElMessage.warning('用户名需在 40 字以内')
  userEditSaving.value = true
  try {
    await http.put(`/users/${userEdit.id}`, { username: name, role: userEdit.role })
    ElMessage.success('用户已更新')
    userEditOpen.value = false
    loadUsers()
    // 改自己时刷新全局状态（用户名、头像等）
    if (userEdit.id === store.user?.id) await store.init(true)
  } finally { userEditSaving.value = false }
}

async function resetUserPwd(row) {
  let value
  try {
    ({ value } = await ElMessageBox.prompt(`为「${row.username}」设置新密码`, '重置密码', {
      inputType: 'password', inputPattern: /^.{4,}$/, inputErrorMessage: '密码至少 4 位',
      confirmButtonText: '重置', cancelButtonText: '取消'
    }))
  } catch { return }
  await http.put(`/users/${row.id}`, { password: value })
  ElMessage.success('密码已重置')
}

async function deleteUser(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${row.username}」吗？其创建的数据将保留。`, '删除用户',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  await http.post(`/users/${row.id}`)
  ElMessage.success('用户已删除')
  loadUsers()
}

/* ---------------- 仪表盘卡片 ---------------- */
const CARD_TYPES = { stat: '数值卡', pie: '分布饼图', rank: '排行榜' }
const cards = ref([])
const cardsSaving = ref(false)
const cardOpen = ref(false)
const cardForm = reactive({
  index: null, title: '', type: 'stat', scope: 'all', period: 'all',
  agg: 'count', metric: '', dimension: '', limit: 10
})
const cardTableId = computed(() => {
  const s = cardForm.scope || 'all'
  return s.startsWith('table:') ? Number(s.slice(6)) : 0
})
const cardFields = computed(() => {
  if (!cardTableId.value) return tables.value.flatMap(t => t.fields || [])
  const t = tables.value.find(x => x.id === cardTableId.value)
  return t ? (t.fields || []) : []
})
const numberFields = computed(() => cardFields.value.filter(f => f.type === 'number'))

async function loadCards() {
  const res = await http.get('/settings')
  try {
    cards.value = JSON.parse(res.settings.dashboard_cards || '[]')
  } catch {
    cards.value = []
  }
}

async function saveCards() {
  cardsSaving.value = true
  try {
    await http.put('/settings', { dashboard_cards: JSON.stringify(cards.value) })
  } finally { cardsSaving.value = false }
}

function cardScopeName(c) {
  if (c.scope === 'table' && c.table_id) {
    const t = tables.value.find(x => x.id === c.table_id)
    return t ? t.name : '已删除的表'
  }
  return '全部数据表'
}

function fieldLabel(c) {
  const t = c.scope === 'table' ? tables.value.find(x => x.id === c.table_id) : null
  const pool = t ? (t.fields || []) : tables.value.flatMap(x => x.fields || [])
  const f = pool.find(x => x.key === c.dimension)
  return f ? f.label : (c.dimension || '')
}

function cardSummary(c) {
  const agg = { count: '计数', sum: '求和', avg: '平均值' }[c.agg || 'count']
  const metric = c.agg !== 'count' && c.metric ? `（${c.metric}）` : ''
  if (c.type === 'stat') {
    const p = { all: '全部', today: '今日', week: '近 7 天', month: '近 30 天' }[c.period || 'all']
    return `${p} · ${agg}${metric}`
  }
  const dim = c.dimension === '__table__' ? '数据表' : fieldLabel(c)
  return `按${dim} · ${agg}${metric}`
}

function openCardEdit(row) {
  if (row) {
    Object.assign(cardForm, {
      index: cards.value.indexOf(row), title: row.title || '', type: row.type || 'stat',
      scope: row.scope === 'table' && row.table_id ? `table:${row.table_id}` : 'all',
      period: row.period || 'all', agg: row.agg || 'count',
      metric: row.metric || '', dimension: row.dimension || '', limit: row.limit || 10
    })
  } else {
    Object.assign(cardForm, {
      index: null, title: '', type: 'stat', scope: 'all', period: 'all',
      agg: 'count', metric: '', dimension: '', limit: 10
    })
  }
  cardOpen.value = true
}

async function saveCard() {
  if (!cardForm.title.trim()) return ElMessage.warning('请填写卡片标题')
  if (cardForm.type !== 'stat' && !cardForm.dimension) return ElMessage.warning('请选择分组字段')
  if (cardForm.agg !== 'count' && !cardForm.metric) return ElMessage.warning('请选择数值字段')
  const isTable = cardForm.scope.startsWith('table:')
  const cfg = {
    id: cardForm.index === null
      ? `c${Date.now()}`
      : (cards.value[cardForm.index].id || `c${Date.now()}`),
    title: cardForm.title.trim(),
    type: cardForm.type,
    scope: isTable ? 'table' : 'all',
    table_id: isTable ? Number(cardForm.scope.slice(6)) : null,
    period: cardForm.period,
    agg: cardForm.agg,
    metric: cardForm.agg === 'count' ? '' : cardForm.metric,
    dimension: cardForm.type === 'stat' ? '' : cardForm.dimension,
    limit: Number(cardForm.limit) || 10
  }
  if (cardForm.index === null) cards.value.push(cfg)
  else cards.value.splice(cardForm.index, 1, cfg)
  cardOpen.value = false
  await saveCards()
  ElMessage.success('仪表盘配置已保存')
}

async function moveCard(index, delta) {
  const target = index + delta
  if (target < 0 || target >= cards.value.length) return
  const list = [...cards.value]
  const [item] = list.splice(index, 1)
  list.splice(target, 0, item)
  cards.value = list
  await saveCards()
}

async function deleteCard(index) {
  try {
    await ElMessageBox.confirm(`确定删除卡片「${cards.value[index].title}」吗？`, '删除卡片',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  cards.value.splice(index, 1)
  await saveCards()
  ElMessage.success('已删除')
}

async function resetCards() {
  await http.put('/settings', { dashboard_cards: '' })
  await loadCards()
  ElMessage.success('已恢复默认卡片')
}

/* ---------------- 账户安全 ---------------- */
const pwd = reactive({ old: '', new: '', confirm: '' })
const pwdSaving = ref(false)
const avatarStamp = ref(0)
const avatarUrl = computed(() =>
  store.user?.avatar ? `${store.user.avatar}?t=${avatarStamp.value}` : '')

async function changePwd() {
  if (!pwd.new || pwd.new.length < 4) return ElMessage.warning('新密码至少 4 位')
  if (pwd.new !== pwd.confirm) return ElMessage.warning('两次输入的密码不一致')
  pwdSaving.value = true
  try {
    await http.post('/auth/password', { old: pwd.old, new: pwd.new, confirm: pwd.confirm })
    ElMessage.success('密码已修改，请重新登录')
    await store.logout()
    router.push('/login')
  } finally { pwdSaving.value = false }
}

async function onAvatarChange(file) {
  const fd = new FormData()
  fd.append('file', file.raw)
  const res = await http.post('/auth/avatar', fd)
  store.user.avatar = res.avatar
  avatarStamp.value = Date.now()
  ElMessage.success('头像已更新')
}

onMounted(() => {
  if (route.query.tab) tab.value = String(route.query.tab)
  // 非管理员仅可见账户安全与关于，其余 tab 数据不加载
  if (!store.isAdmin && !['security', 'about'].includes(tab.value)) tab.value = 'security'
  if (store.isAdmin) {
    loadSettings()
    loadTables()
    loadCards()
    loadBackups()
    loadFonts()
    loadUsers()
  }
})
</script>

<style scoped>
.settings-page { height: 100%; overflow: hidden; }
.settings-tabs { height: 100%; background: transparent; display: flex; flex-direction: column; }
/* 横向 tabs：样式走全局 .dc-tabs，此处只管布局 */
.settings-tabs :deep(.el-tabs__header) { margin: 0 0 12px; flex: none; }
.settings-tabs :deep(.el-tabs__content) { flex: 1; min-height: 0; overflow-y: auto; }
.pane {
  background: var(--dc-card); border: 1px solid var(--dc-border);
  border-radius: var(--dc-radius); padding: 20px;
  width: fit-content; min-width: 560px; max-width: 760px;
}
/* 表管理页保持通栏卡片 */
.pane.pane-table { width: 100%; min-width: 0; max-width: none; }
/* 备份页：表单头 + 表格 + 提示 */
.pane-backup { min-width: 700px; }
.backup-actions { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.backup-tip { margin-top: 12px; font-size: 12px; line-height: 1.6; }

/* 通知字体管理 */
.font-manage { width: 100%; max-width: 460px; }
.font-row { display: flex; align-items: center; gap: 10px; }
.font-list { margin-top: 10px; display: flex; flex-direction: column; gap: 6px; }
.font-item {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 10px; border: 1px solid var(--dc-border);
  border-radius: 8px; font-size: 13px;
}
.font-item .font-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.font-item .font-size { font-size: 12px; flex: none; }
.font-manage .field-hint { margin-top: 8px; }


.pane-title { font-size: 16px; font-weight: 700; margin-bottom: 18px; }
.pane-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.pane-head .pane-title { margin-bottom: 0; }
.pane-center { width: 100%; }
.set-form { max-width: 680px; }
.field-hint { font-size: 12px; width: 100%; margin-top: 3px; }
.inline-row { display: flex; align-items: center; gap: 10px; }

.theme-grid { display: grid; grid-template-columns: repeat(3, minmax(120px, 1fr)); gap: 12px; margin-bottom: 16px; }
.theme-card {
  position: relative; border: 2px solid var(--dc-border); border-radius: var(--dc-radius);
  padding: 12px 10px; cursor: pointer; text-align: center; transition: all .18s;
}
.theme-card:hover { border-color: var(--dc-primary); }
.theme-card.active { border-color: var(--dc-primary); background: var(--dc-primary-soft); }
.theme-colors { display: flex; gap: 6px; justify-content: center; margin-bottom: 8px; }
.theme-colors span { width: 30px; height: 14px; border-radius: 6px; display: block; }
.theme-name { font-size: 13px; font-weight: 600; }
.theme-check { position: absolute; top: 6px; right: 8px; color: var(--dc-primary); }
.dark-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 14px; border: 1px solid var(--dc-border); border-radius: var(--dc-radius);
  width: 100%;
}
.dark-row + .dark-row { margin-top: 12px; }
.about-log-title { margin: 20px 0 8px; }

.avatar-row {
  display: flex; align-items: center; gap: 14px;
  padding-top: 20px; margin-top: 22px;
  border-top: 1px solid var(--dc-border);
}
.avatar-info { flex: 1; min-width: 0; }
.avatar-name { font-size: 15px; font-weight: 600; margin-bottom: 2px; }

.about-hero { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
.about-full { font-size: 19px; font-weight: 700; }
.about-items { display: flex; flex-direction: column; gap: 8px; }
.about-li { display: flex; align-items: center; gap: 12px; font-size: 14px; }
.about-li span:first-child { width: 70px; }
.changelog b { font-size: 13px; }
.changelog ul { margin: 6px 0 14px; padding-left: 18px; }
.changelog li { font-size: 13px; color: var(--dc-text-soft); line-height: 1.8; }

.fields-head {
  display: flex; justify-content: space-between; align-items: center;
  gap: 10px; margin-bottom: 10px;
}
.tpl-group { display: flex; flex-wrap: wrap; gap: 8px; row-gap: 8px; }
.tpl-group :deep(.el-radio) { margin-right: 0; }
.w-full { width: 100%; }

@media (max-width: 768px) {
  .settings-page { overflow-y: auto; }
  .theme-grid { grid-template-columns: repeat(2, 1fr); }
  .pane { width: 100%; min-width: 0; max-width: none; }
  /* 表单改纵向标签（标签置顶）：释放被固定 120/130px 标签列挤占的内容宽度，
     使下拉/复选框/按钮等不再被压缩换行 */
  .pane .set-form :deep(.el-form-item) { display: block; }
  .pane .set-form :deep(.el-form-item__label) {
    width: auto !important;
    display: block;
    text-align: left;
    padding: 0;
    margin-bottom: 6px;
  }
  .pane .set-form :deep(.el-form-item__content) { margin-left: 0 !important; }
  .inline-row { flex-wrap: wrap; }
}

/* 字段管理：可选值展示与彩色标签编辑器 */
.opt-cell { display: flex; align-items: center; gap: 4px; flex-wrap: nowrap; overflow: hidden; }
.opt-badge { display: inline-block; padding: 1px 8px; border-radius: 5px; font-size: 12px;
             font-weight: 600; line-height: 18px; white-space: nowrap; }
.type-tag { max-width: 100%; }
.field-tip { font-size: 12px; margin-top: 4px; line-height: 1.5; }
.ct-editor { width: 100%; }
.ct-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.ct-row :deep(.el-input) { flex: 1; }
.color-field-sel { width: 100%; }
</style>
