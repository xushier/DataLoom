# -*- coding: utf-8 -*-
"""数据库初始化与通用工具"""
import os
import json
import sqlite3
import threading
import secrets
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash, check_password_hash

APP_NAME = "DataLoom"

DATA_DIR = os.environ.get("DATALOOM_DATA_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DATA_DIR, "dataloom.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
AVATAR_DIR = os.path.join(UPLOAD_DIR, "avatars")

_write_lock = threading.Lock()

# 时区：Docker 容器默认 UTC（比北京时间少 8 小时），显式按东八区取时间，
# 可用环境变量 DATALOOM_TZ 覆盖；时区库不可用时回退系统本地时间
try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo(os.environ.get("DATALOOM_TZ") or "Asia/Shanghai")
except Exception:
    _TZ = None


def now():
    """当前时间（默认东八区）"""
    return datetime.now(_TZ)

VERSION = "2.0.0"
GITHUB_URL = "https://github.com/xushier/dataloom"
AUTHOR = "段松博"

CHANGELOG = [
    {
        "version": "2.0.0",
        "date": "2026-11-13",
        "items": [
            "全新通用数据登记与台账系统「数织 DataLoom」：不再绑定图号业务，任何数据都可建表登记",
            "系统名称、副标题、机构名称与 Logo 可在「系统设置 - 基本设置」中自定义",
            "内置表改为示例台账：可自由重命名、删除，也可作为模板复制新表；字段全部可编辑可删除",
            "仪表盘汇总卡片可自定义：自由增删卡片，指定统计范围（全部表 / 指定表）、维度字段与聚合方式",
            "条数类统计（总量 / 今日新增 / 增长曲线 / 数据日历 / 最近数据 / 各表分布）跨表合计",
            "微信通知改为通用文案，正文字段按数据表字段自动选取",
            "主题、多用户、角色权限、回收站、备份恢复、Excel 导入导出等能力全部保留",
        ],
    },
]

DEFAULT_SETTINGS = {
    "site_name": "数织",              # 系统名称（侧边栏、登录页、浏览器标题）
    "site_org": "",                  # 机构名称（用于副标题）
    "site_subtitle": "",             # 系统副标题（留空自动生成）
    "site_logo": "",                 # 自定义 Logo 图片地址（/uploads/...，空则用内置图标）
    "guest_mode": "off",              # off 关闭 | readonly 只读浏览 | add 可添加
    "allow_register": "0",           # 是否开放自助注册 1/0
    "notify_enabled": "0",
    "notify_type": "robot",          # robot | wecom_app
    "notify_webhook": "",
    "notify_corpid": "",
    "notify_secret": "",
    "notify_agentid": "",
    "notify_touser": "@all",
    "notify_style": "text",          # text | image_text
    "notify_font": "",               # 自定义字体文件名（空 = 系统默认）
    "notify_on_add": "1",
    "notify_on_delete": "1",
    "log_auto_clear": "1",
    "log_retention_days": "30",
    "table_vborder": "0",
    "backup_enabled": "1",
    "dashboard_cards": "",           # 仪表盘卡片配置 JSON（空 = 使用默认卡片）
}

# 默认仪表盘卡片：只放与具体字段无关、可跨表合计的统计
DEFAULT_DASHBOARD_CARDS = [
    {"id": "total", "title": "数据总量", "type": "stat", "scope": "all",
     "table_id": None, "period": "all", "agg": "count", "metric": "",
     "dimension": "", "limit": 10},
    {"id": "today", "title": "今日新增", "type": "stat", "scope": "all",
     "table_id": None, "period": "today", "agg": "count", "metric": "",
     "dimension": "", "limit": 10},
    {"id": "week", "title": "近 7 天新增", "type": "stat", "scope": "all",
     "table_id": None, "period": "week", "agg": "count", "metric": "",
     "dimension": "", "limit": 10},
    {"id": "by_table", "title": "各表数据分布", "type": "pie", "scope": "all",
     "table_id": None, "period": "all", "agg": "count", "metric": "",
     "dimension": "__table__", "limit": 12},
]

# 设置读取时也应返回默认卡片，便于「系统设置 - 仪表盘」直接编辑与恢复默认
DEFAULT_SETTINGS["dashboard_cards"] = json.dumps(
    DEFAULT_DASHBOARD_CARDS, ensure_ascii=False)

# 彩色标签字段的默认色板（新建选项未指定颜色时按顺序取用）
COLOR_PALETTE = ["#5470c6", "#2f9e44", "#e8a33d", "#d94b4b", "#13a8a8",
                 "#8f5bd6", "#d969a8", "#6b7a8f"]

# 种子表：仅首次初始化时创建，之后与普通表完全一致（可改名、可删除、字段可改）
SEED_TABLES = [
    {
        "name": "示例台账",
        "color_field": "status",
        "fields": [
            ("sn", "序号", "number", 1, "[]"),
            ("name", "名称", "text", 2, "[]"),
            ("category", "分类", "select", 3, "[]"),
            ("project", "所属项目", "select", 4, "[]"),
            ("applicant", "登记人", "select", 5, "[]"),
            ("apply_time", "登记时间", "datetime", 6, "[]"),
            ("amount", "数量", "number", 7, "[]"),
            # 状态：彩色标签（进行中 / 近期落地 / 已终止）
            ("status", "状态", "color_tag", 8, json.dumps([
                {"value": "进行中", "color": "#2f9e44"},
                {"value": "近期落地", "color": "#e8a33d"},
                {"value": "已终止", "color": "#d94b4b"},
            ], ensure_ascii=False)),
            ("remark", "备注", "text", 9, "[]"),
        ],
    },
]


def now_str():
    return now().strftime("%Y-%m-%d %H:%M:%S")


def site_names(s):
    """系统名称 / 副标题 / 机构名：均可在设置中自定义，副标题留空时自动生成"""
    s = s or {}
    org = (s.get("site_org") or "").strip()
    name = (s.get("site_name") or "").strip() or "数织"
    sub = (s.get("site_subtitle") or "").strip()
    if not sub:
        sub = f"{org} · 数据登记与台账" if org else "通用数据登记与台账"
    return {"full": name, "subtitle": sub, "org": org}


def get_dashboard_cards():
    """读取仪表盘卡片配置，未配置时返回默认卡片"""
    raw = get_setting("dashboard_cards")
    if raw:
        try:
            cards = json.loads(raw)
            if isinstance(cards, list):
                return [c for c in cards if isinstance(c, dict)]
        except Exception:
            pass
    return json.loads(json.dumps(DEFAULT_DASHBOARD_CARDS))


def get_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def query(sql, args=(), one=False):
    conn = get_db()
    try:
        rows = conn.execute(sql, args).fetchall()
        if one:
            return dict(rows[0]) if rows else None
        return [dict(r) for r in rows]
    finally:
        conn.close()


def execute(sql, args=()):
    """带写锁的写入，返回 lastrowid"""
    with _write_lock:
        conn = get_db()
        try:
            cur = conn.execute(sql, args)
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()


def get_setting(key, default=None):
    row = query("SELECT value FROM settings WHERE key=?", (key,), one=True)
    if row is None:
        return DEFAULT_SETTINGS.get(key, default) if default is None else default
    return row["value"]


def get_settings():
    stored = {r["key"]: r["value"] for r in query("SELECT key, value FROM settings")}
    merged = dict(DEFAULT_SETTINGS)
    merged.update(stored)
    return merged


def set_setting(key, value):
    execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)))


def log_op(user, action, table_id=None, table_name="", target="", detail=None):
    execute(
        "INSERT INTO ops(user, action, table_id, table_name, target, detail, created_at) "
        "VALUES(?,?,?,?,?,?,?)",
        (user, action, table_id, table_name, target,
         json.dumps(detail, ensure_ascii=False) if detail else "", now_str()))


def sys_log(level, module, message, detail=""):
    try:
        execute(
            "INSERT INTO sys_logs(level, module, message, detail, created_at) VALUES(?,?,?,?,?)",
            (level, module, message, detail, now_str()))
    except Exception:
        pass


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(AVATAR_DIR, exist_ok=True)
    conn = get_db()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            avatar TEXT DEFAULT '',
            role TEXT DEFAULT 'user',
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS sessions(
            token TEXT PRIMARY KEY,
            user_id INTEGER,
            created_at TEXT,
            expires_at TEXT
        );
        CREATE TABLE IF NOT EXISTS tables(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            is_system INTEGER DEFAULT 0,
            template TEXT DEFAULT '',
            color_field TEXT DEFAULT '',
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS fields(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER,
            key TEXT,
            label TEXT,
            type TEXT,
            required INTEGER DEFAULT 0,
            default_value TEXT DEFAULT '',
            options TEXT DEFAULT '[]',
            is_system INTEGER DEFAULT 0,
            sort INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS records(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER,
            data TEXT,
            created_at TEXT,
            updated_at TEXT,
            created_by TEXT,
            deleted_at TEXT,
            deleted_by TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_records_table ON records(table_id);
        CREATE TABLE IF NOT EXISTS ops(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT, action TEXT,
            table_id INTEGER, table_name TEXT, target TEXT, detail TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS sys_logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT, module TEXT, message TEXT, detail TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY, value TEXT
        );
        """)
        conn.commit()

        # 迁移：多用户角色列（存量用户此前均为管理员）
        cols = {r["name"] for r in query("PRAGMA table_info(users)")}
        if "role" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
            conn.execute("UPDATE users SET role='admin'")
        # 迁移：访客模式三档（旧值 1 → add，0 → off）
        conn.execute("UPDATE settings SET value='add' WHERE key='guest_mode' AND value='1'")
        conn.execute("UPDATE settings SET value='off' WHERE key='guest_mode' AND value='0'")
        # 迁移：回收站软删除列（存量库补列）
        rcols = {r["name"] for r in query("PRAGMA table_info(records)")}
        if "deleted_at" not in rcols:
            conn.execute("ALTER TABLE records ADD COLUMN deleted_at TEXT")
        if "deleted_by" not in rcols:
            conn.execute("ALTER TABLE records ADD COLUMN deleted_by TEXT")
        # 迁移：表级「行色条」字段（存量库补列）
        tcols = {r["name"] for r in query("PRAGMA table_info(tables)")}
        if "color_field" not in tcols:
            conn.execute("ALTER TABLE tables ADD COLUMN color_field TEXT DEFAULT ''")
        # 通用化后不再对任何字段做唯一约束（旧版图号唯一索引一并移除）
        conn.execute("DROP INDEX IF EXISTS uniq_records_drawing")
        conn.commit()

        # 种子：管理员
        if not query("SELECT id FROM users LIMIT 1", one=True):
            conn.execute(
                "INSERT INTO users(username, password_hash, avatar, role, created_at) VALUES(?,?,?,?,?)",
                ("admin", generate_password_hash("admin"), "", "admin", now_str()))
            conn.commit()

        # 种子：示例台账（仅首次初始化，之后与普通表完全一致）
        if not query("SELECT id FROM tables LIMIT 1", one=True):
            for t in SEED_TABLES:
                cur = conn.execute(
                    "INSERT INTO tables(name, is_system, template, color_field, created_at) "
                    "VALUES(?,0,?,?,?)",
                    (t["name"], "", t.get("color_field", ""), now_str()))
                tid = cur.lastrowid
                for key, label, ftype, sort, opts in t["fields"]:
                    conn.execute(
                        "INSERT INTO fields(table_id, key, label, type, required, default_value,"
                        " options, is_system, sort) VALUES(?,?,?,?,0,'',?,0,?)",
                        (tid, key, label, ftype, opts, sort))
                conn.commit()
        conn.commit()
    finally:
        conn.close()


def create_session(user_id):
    token = secrets.token_hex(32)
    expires = (now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    execute(
        "INSERT INTO sessions(token, user_id, created_at, expires_at) VALUES(?,?,?,?)",
        (token, user_id, now_str(), expires))
    return token


def check_password(username, password):
    row = query("SELECT * FROM users WHERE username=?", (username,), one=True)
    if row and check_password_hash(row["password_hash"], password):
        return row
    return None
