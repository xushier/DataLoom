# -*- coding: utf-8 -*-
"""数据表：表、字段、记录、导入导出"""
import json
import sqlite3
import re
from datetime import datetime
from flask import Blueprint, request, jsonify, g

from . import db as D

tables_bp = Blueprint("tables", __name__)

SELECT_TYPES = ("select", "multi_select", "radio", "checkbox", "color_tag")
FIELD_TYPES = ("text", "textarea", "number", "select", "multi_select",
               "radio", "checkbox", "switch", "date", "datetime",
               "color_tag", "rating", "date_diff", "quantity", "contact")
DATE_TYPES = ("date", "datetime")
COLOR_PALETTE = getattr(D, "COLOR_PALETTE", ["#5470c6", "#2f9e44", "#e8a33d"])


# ---------------- 选项结构 ----------------

def auto_color(i):
    return COLOR_PALETTE[i % len(COLOR_PALETTE)]


def color_options(options):
    """彩色标签选项统一为 [{"value","color"}]，兼容纯字符串旧数据"""
    out = []
    for o in options or []:
        if isinstance(o, dict):
            v = str(o.get("value") or "").strip()
            if v:
                out.append({"value": v, "color": str(o.get("color") or "") or
                            auto_color(len(out))})
        else:
            v = str(o or "").strip()
            if v:
                out.append({"value": v, "color": auto_color(len(out))})
    return out


def norm_field_options(ftype, raw):
    """按字段类型规范化 options，落库统一为 JSON"""
    if ftype == "color_tag":
        return color_options(raw)
    if ftype == "rating":
        m = (raw or {}).get("max") if isinstance(raw, dict) else 5
        try:
            m = int(m)
        except (TypeError, ValueError):
            m = 5
        return {"max": min(10, max(3, m))}
    if ftype == "date_diff":
        r = raw if isinstance(raw, dict) else {}
        vals = r.get("end_values")
        svals = r.get("start_values")
        return {"start": str(r.get("start") or "").strip(),
                "end": str(r.get("end") or "").strip(),
                "end_field": str(r.get("end_field") or "").strip(),
                "end_values": [str(v) for v in (vals or []) if str(v).strip()],
                "start_field": str(r.get("start_field") or "").strip(),
                "start_values": [str(v) for v in (svals or []) if str(v).strip()]}
    if ftype == "quantity":
        r = raw if isinstance(raw, dict) else {}
        return {"mode": "manual" if r.get("mode") == "manual" else "auto",
                "unit": str(r.get("unit") or "").strip()[:8]}
    if ftype == "number":
        r = raw if isinstance(raw, dict) else {}
        p = r.get("precision")
        try:
            p = int(p)
        except (TypeError, ValueError):
            p = None
        return {"precision": min(6, max(0, p))} if p is not None else {}
    if ftype == "contact":
        return {}
    return [str(o).strip() for o in (raw or []) if str(o).strip()]


def option_map(field):
    """选项值 -> 颜色 映射（仅彩色标签字段有值）"""
    if field.get("type") != "color_tag":
        return {}
    return {o["value"]: o["color"] for o in color_options(field.get("options"))}


# ---------------- 日期差值（计算字段，不落库） ----------------

def _to_date(v):
    s = str(v or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def human_duration(days):
    """天数 -> 可读时长：N 天 / N 个月 / N 年 M 个月"""
    if days is None:
        return ""
    if days < 0:
        return "—"
    if days < 31:
        return f"{days} 天"
    years = days // 365
    months = (days % 365) // 30
    if not years:
        return f"{months} 个月" if months else f"{days} 天"
    return f"{years} 年 {months} 个月" if months else f"{years} 年"


def _cond_met(value, values):
    """记录值是否命中终态取值（兼容多选数组）"""
    vals = {str(v) for v in (values or []) if str(v).strip()}
    if not vals:
        return False
    if isinstance(value, list):
        return any(str(v) in vals for v in value)
    return str(value if value is not None else "") in vals


def date_diff_start(field, data):
    """日期差值的起始日期：起始条件命中日 > 起始日期字段

    返回 (起始日期|None, 是否处于计算状态)。
    配置了起始条件但当前未命中时返回 (None, False)，表示未开始、按 0 天展示。
    """
    cfg = field.get("options") if isinstance(field.get("options"), dict) else {}
    data = data or {}
    if cfg.get("start_field") and cfg.get("start_values"):
        if not _cond_met(data.get(cfg.get("start_field")), cfg.get("start_values")):
            return None, False
        started = data.get("_started")
        if isinstance(started, dict):
            sd = _to_date(started.get(field["key"]))
            if sd is not None:
                return sd, True
    return _to_date(data.get(cfg.get("start") or "")), True


def date_diff_end(field, data):
    """日期差值的结束日期：结束字段 > 终态冻结日 > 今天"""
    cfg = field.get("options") if isinstance(field.get("options"), dict) else {}
    data = data or {}
    end = _to_date(data.get(cfg.get("end") or "")) if cfg.get("end") else None
    if end is not None:
        return end, None
    if cfg.get("end_field") and _cond_met(data.get(cfg["end_field"]), cfg.get("end_values")):
        frozen = data.get("_frozen")
        if isinstance(frozen, dict):
            fz = _to_date(frozen.get(field["key"]))
            if fz is not None:
                return fz, fz.strftime("%Y-%m-%d")
    return D.now().date(), None


def calc_values(table, data):
    """计算字段取值：{key: {"days": 天数, "text": 可读文本}}"""
    out = {}
    for f in table.get("fields") or []:
        if f.get("type") != "date_diff":
            continue
        start, active = date_diff_start(f, data)
        if not active:
            out[f["key"]] = {"days": 0, "text": "0 天", "pending": True}
            continue
        if start is None:
            continue
        end, frozen = date_diff_end(f, data)
        days = (end - start).days
        item = {"days": days, "text": human_duration(days),
                "started": start.strftime("%Y-%m-%d")}
        if frozen:
            item["frozen"] = frozen
        out[f["key"]] = item
    return out


def stamp_started(table, data, old_data=None, updated_at=None):
    """命中起始条件时记录起始日，使日期差值从切换那一刻起算"""
    today = D.now().strftime("%Y-%m-%d")
    started = dict(data["_started"]) if isinstance(data.get("_started"), dict) else {}
    old_data = old_data or {}
    for f in table.get("fields") or []:
        if f.get("type") != "date_diff":
            continue
        cfg = f.get("options") if isinstance(f.get("options"), dict) else {}
        sf = cfg.get("start_field")
        vals = cfg.get("start_values") or []
        if not sf or not vals:
            continue
        if _cond_met(data.get(sf), vals):
            if not started.get(f["key"]):
                # 首次命中记为今天；历史数据（保存前已命中）沿用最后更新日
                fb = today
                if _cond_met(old_data.get(sf), vals):
                    fb = str(updated_at or "")[:10] or today
                started[f["key"]] = fb
        else:
            started.pop(f["key"], None)
    if started:
        data["_started"] = started
    else:
        data.pop("_started", None)
    return data


def stamp_frozen(table, data, old_data=None, updated_at=None):
    """命中终态条件时记录冻结日期，使日期差值停在结束那一刻"""
    today = D.now().strftime("%Y-%m-%d")
    frozen = dict(data["_frozen"]) if isinstance(data.get("_frozen"), dict) else {}
    old_data = old_data or {}
    for f in table.get("fields") or []:
        if f.get("type") != "date_diff":
            continue
        cfg = f.get("options") if isinstance(f.get("options"), dict) else {}
        sf = cfg.get("end_field")
        vals = cfg.get("end_values") or []
        if not sf or not vals:
            continue
        if _cond_met(data.get(sf), vals):
            if not frozen.get(f["key"]):
                # 首次进入终态记为今天；若旧记录已是终态（历史数据）则沿用其最后更新日
                fb = today
                if _cond_met(old_data.get(sf), vals):
                    fb = str(updated_at or "")[:10] or today
                frozen[f["key"]] = fb
        else:
            frozen.pop(f["key"], None)
    if frozen:
        data["_frozen"] = frozen
    else:
        data.pop("_frozen", None)
    return data



def decorate(table, records):
    """为记录附加计算字段结果（不写库）"""
    for r in records:
        r["calc"] = calc_values(table, r["data"])
    return records


# ---------------- 数量明细 ----------------

def qty_config(field):
    """数量明细字段配置：合计方式与单位"""
    cfg = field.get("options") if isinstance(field.get("options"), dict) else {}
    return {"mode": "manual" if cfg.get("mode") == "manual" else "auto",
            "unit": str(cfg.get("unit") or "")}


def _num(v):
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    if n != n or n in (float("inf"), float("-inf")):
        return None
    return int(n) if n == int(n) else round(n, 3)


def qty_total(v):
    """数量明细的总数，兼容纯数字旧值"""
    if isinstance(v, dict):
        return _num(v.get("total"))
    return _num(v)


def qty_items(v):
    """数量明细的分项列表 [{name, qty}]"""
    if not isinstance(v, dict):
        return []
    out = []
    for it in v.get("items") or []:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or "").strip()
        qty = _num(it.get("qty"))
        if name and qty is not None:
            out.append({"name": name[:20], "qty": qty})
    return out[:30]


def quantity_text(v, unit=""):
    """数量明细的可读文本：64 套（远控 2；接地刀闸 16）"""
    total = qty_total(v)
    if total is None:
        return ""
    u = f" {unit}" if unit else ""
    items = qty_items(v)
    if not items:
        return f"{total}{u}"
    inner = "；".join(f"{it['name']} {it['qty']}" for it in items)
    return f"{total}{u}（{inner}）"


def norm_quantity(field, raw):
    """记录中的数量明细值：{total, items}；空值返回 None"""
    if raw is None or raw == "":
        return None
    cfg = qty_config(field)
    total = qty_total(raw)
    items = qty_items(raw)
    if cfg["mode"] == "auto":
        # 自动合计：总数始终等于分项之和
        total = sum(it["qty"] for it in items) if items else total
    elif total is None:
        total = sum(it["qty"] for it in items) if items else None
    if total is None and not items:
        return None
    if total is None:
        total = 0
    return {"total": total, "items": items}


def norm_record_values(table, data):
    """按字段类型规范化记录值（数量明细统一成结构体、数字按精度取整）"""
    for f in table.get("fields") or []:
        if f["key"] not in data:
            continue
        if f.get("type") == "quantity":
            data[f["key"]] = norm_quantity(f, data[f["key"]])
        elif f.get("type") == "number":
            data[f["key"]] = norm_number(f, data[f["key"]])
        elif f.get("type") == "contact":
            data[f["key"]] = str(data[f["key"]] or "").strip()
    return data


def num_precision(field):
    cfg = field.get("options") if isinstance(field.get("options"), dict) else {}
    try:
        p = int(cfg.get("precision"))
        return p if 0 <= p <= 6 else None
    except (TypeError, ValueError):
        return None


def norm_number(field, v):
    """按字段配置的小数位取整；空值原样返回"""
    if v is None or v == "":
        return v
    try:
        n = float(v)
    except (TypeError, ValueError):
        return v
    if n != n or n in (float("inf"), float("-inf")):
        return v
    p = num_precision(field)
    if p is not None:
        n = round(n, p)
    return int(n) if n == int(n) else n


# ---------------- 联系方式 ----------------

CONTACT_SPLIT = re.compile(r"[、,，;；/\n]+")
CONTACT_PATTERNS = (
    re.compile(r"^1[3-9]\d{9}$"),                              # 手机
    re.compile(r"^(?:0\d{2,3}-?)?\d{7,8}(?:-\d{1,6})?$"),      # 座机
    re.compile(r"^400-?\d{3}-?\d{4}$"),                        # 400 热线
    re.compile(r"^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$"),             # 邮箱
)


def contact_bad_tokens(v):
    """返回不符合常见通信方式格式的值（手机 / 座机 / 400 / 邮箱）"""
    out = []
    for t in CONTACT_SPLIT.split(str(v or "")):
        t = t.strip()
        if not t:
            continue
        if not any(p.match(t) for p in CONTACT_PATTERNS):
            out.append(t)
    return out


def parse_qty_items(text):
    """「远控 2；接地刀闸 16 套」-> [{name, qty}]"""
    out = []
    for seg in re.split(r"[；;，,、]", str(text or "")):
        seg = seg.strip()
        if not seg:
            continue
        m = re.match(r"^(.+?)\s*[×xX*]?\s*([\d.]+)\s*[^\d]*$", seg)
        if not m:
            continue
        name = m.group(1).strip()
        qty = _num(m.group(2))
        if name and qty is not None:
            out.append({"name": name[:20], "qty": qty})
    return out


def parse_quantity_cell(text):
    """导入用：解析「64（远控 2，接地刀闸 16）」或纯数字"""
    s = str(text if text is not None else "").strip()
    if not s:
        return None
    m = re.match(r"^([\d.]+)\s*(?:[（(](.*)[）)])?\s*$", s)
    total, inner = None, ""
    if m:
        total = _num(m.group(1))
        inner = m.group(2) or ""
    else:
        inner = s
    items = parse_qty_items(inner) if inner else []
    if total is None and not items:
        return None
    return {"total": total, "items": items}


# ---------------- 工具 ----------------

def get_table(tid):
    t = D.query("SELECT * FROM tables WHERE id=?", (tid,), one=True)
    if not t:
        return None
    t["fields"] = D.query(
        "SELECT * FROM fields WHERE table_id=? ORDER BY sort, id", (tid,))
    for f in t["fields"]:
        try:
            f["options"] = json.loads(f["options"] or "[]")
        except Exception:
            f["options"] = []
        f["required"] = bool(f["required"])
        f["is_system"] = bool(f["is_system"])
    return t


def field_map(table):
    return {f["key"]: f for f in table["fields"]}


def sort_key(v):
    """混合类型安全排序：数值类在前，空值在后"""
    if v is None or v == "":
        return (2, 0.0, "")
    s = str(v).strip()
    try:
        return (0, float(s), "")
    except ValueError:
        return (1, 0.0, s.lower())


def load_records(tid):
    """未删除（不在回收站）的记录"""
    rows = D.query(
        "SELECT id, table_id, data, created_at, updated_at, created_by "
        "FROM records WHERE table_id=? AND deleted_at IS NULL ORDER BY id DESC", (tid,))
    out = []
    for r in rows:
        try:
            r["data"] = json.loads(r["data"])
        except Exception:
            r["data"] = {}
        out.append(r)
    return out


def apply_query(records, table, args):
    """搜索 / 筛选 / 排序（内存中完成）"""
    fmap = field_map(table)
    kw = (args.get("search") or "").strip().lower()

    filters = {}
    try:
        filters = json.loads(args.get("filters") or "{}")
    except Exception:
        filters = {}

    result = []
    for r in records:
        data = r["data"]
        # 全局搜索
        if kw:
            parts = []
            for k, f in fmap.items():
                v = data.get(k)
                if f["type"] == "quantity":
                    parts.append(quantity_text(v, qty_config(f)["unit"]))
                else:
                    parts.append(str(v if v is not None else ""))
            hay = " ".join(parts) + " " + r.get("created_at", "")
            if kw not in hay.lower():
                continue
        # 字段筛选
        ok = True
        for key, cond in (filters or {}).items():
            if not isinstance(cond, dict):
                continue
            op = cond.get("op")
            val = cond.get("value")
            ftype = fmap.get(key, {}).get("type")
            if ftype == "date_diff":
                target = (r.get("calc") or {}).get(key, {}).get("days", "")
            elif ftype == "quantity":
                # 区间按总数比较，其余按可读文本匹配
                if op == "range":
                    target = qty_total(data.get(key))
                    if target is None:
                        target = ""
                else:
                    target = quantity_text(data.get(key),
                                           qty_config(fmap[key])["unit"])
            else:
                target = data.get(key, "")
            tstr = str(target if target is not None else "")
            if op == "in":
                vals = [str(x) for x in (val or [])]
                if vals and tstr not in vals:
                    ok = False
                    break
            elif op == "like":
                if (val or "") and (val or "").lower() not in tstr.lower():
                    ok = False
                    break
            elif op == "eq":
                if val is not None and val != "" and tstr != str(val):
                    ok = False
                    break
            elif op == "range":
                lo, hi = (val or [None, None])
                lo, hi = str(lo or ""), str(hi or "")
                try:  # 数值范围
                    tv, lv, hv = float(tstr or 0), (float(lo) if lo else None), (float(hi) if hi else None)
                    if lv is not None and tv < lv:
                        ok = False
                        break
                    if hv is not None and tv > hv:
                        ok = False
                        break
                except ValueError:  # 字符串范围（日期/时间）
                    if lo and tstr < lo:
                        ok = False
                        break
                    if hi and tstr > hi + " 23:59:59":
                        ok = False
                        break
            elif op == "empty":
                # val 为 true：仅看空值；为 false：仅看非空值
                if val is True and tstr != "":
                    ok = False
                    break
                if val is False and tstr == "":
                    ok = False
                    break
        if ok:
            result.append(r)

    # 排序
    sort = args.get("sort", "sn")
    order = args.get("order", "desc")
    if sort == "id":
        result.sort(key=lambda r: r["id"], reverse=(order == "desc"))
    elif sort in fmap and fmap[sort]["type"] == "date_diff":
        result.sort(key=lambda r: (r.get("calc") or {}).get(sort, {}).get("days", -1),
                    reverse=(order == "desc"))
    elif sort in fmap and fmap[sort]["type"] == "quantity":
        result.sort(key=lambda r: sort_key(qty_total(r["data"].get(sort))),
                    reverse=(order == "desc"))
    elif sort in fmap:
        result.sort(key=lambda r: sort_key(r["data"].get(sort)),
                    reverse=(order == "desc"))
    else:
        result.sort(key=lambda r: sort_key(r["data"].get("sn")))
    return result


def record_row(r, table=None):
    return {"id": r["id"], "table_id": r["table_id"], "data": r["data"],
            "calc": r.get("calc") or {},
            "created_at": r["created_at"], "updated_at": r["updated_at"],
            "created_by": r["created_by"]}


def record_title(data):
    """记录标题：优先常见标题字段，其次取第一个非空值"""
    for k in ("name", "title", "drawing_no", "sn"):
        v = data.get(k)
        if isinstance(v, list):
            v = "、".join(str(x) for x in v if str(x).strip())
        s = str(v if v is not None else "").strip()
        if s:
            return s
    for v in data.values():
        if isinstance(v, dict):
            continue
        s = str(v if v is not None else "").strip()
        if s:
            return s
    return ""


def merge_options(table, data, user=""):
    """下拉类字段新值自动加入可选值（彩色标签自动分配颜色）"""
    changed = False
    for f in table["fields"]:
        if f["type"] not in SELECT_TYPES or f["key"] not in data:
            continue
        vals = data[f["key"]]
        if f["type"] in ("multi_select", "checkbox"):
            vals = vals if isinstance(vals, list) else [vals]
        else:
            vals = [vals]
        if f["type"] == "color_tag":
            old = color_options(f["options"])
            known = {o["value"] for o in old}
            new_opts = list(old)
            for v in vals:
                v = str(v or "").strip()
                if v and v not in known:
                    new_opts.append({"value": v, "color": auto_color(len(new_opts))})
                    known.add(v)
        else:
            old = list(f["options"])
            new_opts = list(old)
            for v in vals:
                v = str(v or "").strip()
                if v and v not in new_opts:
                    new_opts.append(v)
        if new_opts != old:
            D.execute("UPDATE fields SET options=? WHERE id=?",
                      (json.dumps(new_opts, ensure_ascii=False), f["id"]))
            changed = True
    return changed


def contact_errors(table, data):
    bad = []
    for f in table.get("fields") or []:
        if f.get("type") == "contact":
            bad.extend(contact_bad_tokens((data or {}).get(f["key"])))
    return bad


def build_create_data(table, raw, existing_records=None):
    """规范化新记录数据：自动序号、自动申请时间"""
    fmap = field_map(table)
    data = {}
    for k, v in (raw or {}).items():
        if k in fmap:
            data[k] = v
    # 数量明细：统一成 {total, items}；数字按精度取整
    norm_record_values(table, data)
    bad = contact_errors(table, data)
    if bad:
        return None, f"联系方式格式不正确：{'、'.join(bad[:5])}"
    # 起始条件命中日 / 终态冻结日期（使日期差值按条件起算与停止）
    stamp_started(table, data)
    stamp_frozen(table, data)
    # 自动序号
    if "sn" in fmap:
        sn = raw.get("sn")
        try:
            data["sn"] = int(sn) if sn not in (None, "",) else None
        except (TypeError, ValueError):
            data["sn"] = None
        if data["sn"] is None:
            mx = 0
            for r in (existing_records or load_records(table["id"])):
                try:
                    mx = max(mx, int(r["data"].get("sn") or 0))
                except (TypeError, ValueError):
                    pass
            data["sn"] = mx + 1
    # 申请时间：不填则自动
    if "apply_time" in fmap and not str(data.get("apply_time") or "").strip():
        data["apply_time"] = D.now_str()
    # 必填校验
    missing = [f["label"] for f in table["fields"]
               if f["required"] and not str(data.get(f["key"], "") or "").strip()
               and f["key"] != "sn"]
    if missing:
        return None, f"必填项未填写：{ '、'.join(missing) }"
    return data, None


def do_create_record(table, raw, user):
    """创建记录，返回 (record|None, error_message)"""
    existing = load_records(table["id"])
    data, err = build_create_data(table, raw, existing)
    if err:
        return None, err
    now = D.now_str()
    rid = D.execute(
        "INSERT INTO records(table_id, data, created_at, updated_at, created_by) "
        "VALUES(?,?,?,?,?)",
        (table["id"], json.dumps(data, ensure_ascii=False), now, now, user))
    merge_options(table, data, user)
    return {"id": rid, "table_id": table["id"], "data": data,
            "created_at": now, "updated_at": now, "created_by": user}, None


# ---------------- 表与字段 ----------------

@tables_bp.get("/tables")
def list_tables():
    if not g.can_read():
        return jsonify(ok=False, message="请先登录"), 401
    tables = D.query("SELECT * FROM tables ORDER BY id")
    counts = {r["table_id"]: r["c"] for r in D.query(
        "SELECT table_id, COUNT(*) c FROM records "
        "WHERE deleted_at IS NULL GROUP BY table_id")}
    for t in tables:
        t["count"] = counts.get(t["id"], 0)
        t["fields"] = D.query(
            "SELECT * FROM fields WHERE table_id=? ORDER BY sort, id", (t["id"],))
        for f in t["fields"]:
            try:
                f["options"] = json.loads(f["options"] or "[]")
            except Exception:
                f["options"] = []
            f["required"] = bool(f["required"])
            f["is_system"] = bool(f["is_system"])
    return jsonify(ok=True, tables=tables)


@tables_bp.post("/tables")
def create_table():
    if not g.is_admin():
        return jsonify(ok=False, message="需要管理员权限"), 401
    body = request.get_json(force=True, silent=True) or {}
    name = (body.get("name") or "").strip()
    template = body.get("template", "blank")
    if not name:
        return jsonify(ok=False, message="请填写表名"), 400
    if D.query("SELECT id FROM tables WHERE name=?", (name,), one=True):
        return jsonify(ok=False, message="表名已存在，请更换"), 400
    src = None
    if isinstance(template, str) and template.startswith("table:"):
        try:
            src = int(template.split(":", 1)[1])
        except ValueError:
            src = None
    elif isinstance(template, int):
        src = template
    if src and not D.query("SELECT id FROM tables WHERE id=?", (src,), one=True):
        src = None
    src_row = D.query("SELECT * FROM tables WHERE id=?", (src,), one=True) if src else None
    tid = D.execute(
        "INSERT INTO tables(name, is_system, template, color_field, created_at) "
        "VALUES(?,0,?,?,?)",
        (name, template if isinstance(template, str) else "",
         (src_row or {}).get("color_field") or "", D.now_str()))
    if src:
        for f in D.query("SELECT * FROM fields WHERE table_id=? ORDER BY sort, id", (src,)):
            D.execute(
                "INSERT INTO fields(table_id, key, label, type, required, default_value,"
                " options, is_system, sort) VALUES(?,?,?,?,?,?,?,?,?)",
                (tid, f["key"], f["label"], f["type"], f["required"],
                 f["default_value"], f["options"], 0, f["sort"]))
    D.log_op(g.req_user_name(), "table_create", tid, name,
             detail={"name": name, "template": template})
    D.sys_log("INFO", "TABLES", f"新建数据表: {name} (模板: {template})")
    return jsonify(ok=True, id=tid)


@tables_bp.route("/tables/<int:tid>", methods=["PUT", "DELETE", "POST"])
def manage_table(tid):
    if not g.is_admin():
        return jsonify(ok=False, message="需要管理员权限"), 401
    table = get_table(tid)
    if not table:
        return jsonify(ok=False, message="表不存在"), 404
    if request.method == "PUT":
        body = request.get_json(force=True, silent=True) or {}
        if "color_field" in body:
            # 行色条依据字段：仅接受本表中的彩色标签字段，空串表示不显示
            cf = str(body.get("color_field") or "").strip()
            if cf and not any(f["key"] == cf and f["type"] == "color_tag"
                              for f in table["fields"]):
                cf = ""
            D.execute("UPDATE tables SET color_field=? WHERE id=?", (cf, tid))
        name = (body.get("name") or table["name"]).strip()
        if not name:
            return jsonify(ok=False, message="请填写表名"), 400
        dup = D.query("SELECT id FROM tables WHERE name=? AND id<>?",
                      (name, tid), one=True)
        if dup:
            return jsonify(ok=False, message="表名已存在，请更换"), 400
        if name != table["name"]:
            D.execute("UPDATE tables SET name=? WHERE id=?", (name, tid))
            D.log_op(g.req_user_name(), "table_rename", tid, name,
                     detail={"old": table["name"], "new": name})
        return jsonify(ok=True)
    # DELETE：任何表都可删除（含内置示例表）
    D.execute("DELETE FROM records WHERE table_id=?", (tid,))
    D.execute("DELETE FROM fields WHERE table_id=?", (tid,))
    D.execute("DELETE FROM tables WHERE id=?", (tid,))
    D.log_op(g.req_user_name(), "table_delete", tid, table["name"],
             detail={"name": table["name"]})
    D.sys_log("WARN", "TABLES", f"删除数据表: {table['name']}（含全部数据）")
    return jsonify(ok=True)


@tables_bp.post("/tables/<int:tid>/fields")
def add_field(tid):
    if not g.is_admin():
        return jsonify(ok=False, message="需要管理员权限"), 401
    table = get_table(tid)
    if not table:
        return jsonify(ok=False, message="表不存在"), 404
    body = request.get_json(force=True, silent=True) or {}
    label = (body.get("label") or "").strip()
    ftype = body.get("type", "text")
    if not label:
        return jsonify(ok=False, message="请填写字段名称"), 400
    if ftype not in FIELD_TYPES:
        return jsonify(ok=False, message="字段类型不合法"), 400
    if any(f["label"] == label for f in table["fields"]):
        return jsonify(ok=False, message="字段名称重复"), 400
    n = 1
    keys = {f["key"] for f in table["fields"]}
    while f"f_{n}" in keys:
        n += 1
    sort = max([f["sort"] for f in table["fields"]], default=0) + 1
    opts = norm_field_options(ftype, body.get("options"))
    fid = D.execute(
        "INSERT INTO fields(table_id, key, label, type, required, default_value,"
        " options, is_system, sort) VALUES(?,?,?,?,?,?,?,0,?)",
        (tid, f"f_{n}", label, ftype, 1 if body.get("required") else 0,
         str(body.get("default_value") or ""), json.dumps(opts, ensure_ascii=False),
         sort))
    D.log_op(g.req_user_name(), "field_add", tid, table["name"],
             detail={"label": label, "type": ftype})
    return jsonify(ok=True, id=fid)


@tables_bp.route("/fields/<int:fid>", methods=["PUT", "DELETE", "POST"])
def manage_field(fid):
    if not g.is_admin():
        return jsonify(ok=False, message="需要管理员权限"), 401
    f = D.query("SELECT * FROM fields WHERE id=?", (fid,), one=True)
    if not f:
        return jsonify(ok=False, message="字段不存在"), 404
    table = get_table(f["table_id"])
    body = request.get_json(force=True, silent=True) or {}
    if request.method == "PUT":
        # 所有字段均可改名称与类型（内置示例表字段同样可编辑）
        required = 1 if body.get("required") else 0
        default_value = str(body.get("default_value") or "")
        label = (body.get("label") or f["label"]).strip()
        ftype = body.get("type") or f["type"]
        if ftype not in FIELD_TYPES:
            return jsonify(ok=False, message="字段类型不合法"), 400
        options = json.dumps(norm_field_options(ftype, body.get("options")),
                             ensure_ascii=False)
        D.execute(
            "UPDATE fields SET label=?, type=?, required=?, default_value=?,"
            " options=? WHERE id=?",
            (label, ftype, required, default_value, options, fid))
        # 行色条字段被改成非彩色标签时，取消该表的行色条
        if ftype != "color_tag" and (table.get("color_field") or "") == f["key"]:
            D.execute("UPDATE tables SET color_field='' WHERE id=?", (f["table_id"],))
        D.log_op(g.req_user_name(), "field_update", f["table_id"],
                 table["name"], detail={"label": f["label"]})
        return jsonify(ok=True)
    # DELETE：任何字段都可删除
    if (table.get("color_field") or "") == f["key"]:
        D.execute("UPDATE tables SET color_field='' WHERE id=?", (f["table_id"],))
    D.execute("DELETE FROM fields WHERE id=?", (fid,))
    # 清理记录中的该字段数据
    for r in load_records(f["table_id"]):
        if f["key"] in r["data"]:
            r["data"].pop(f["key"])
            D.execute("UPDATE records SET data=?, updated_at=? WHERE id=?",
                      (json.dumps(r["data"], ensure_ascii=False), D.now_str(), r["id"]))
    D.log_op(g.req_user_name(), "field_delete", f["table_id"],
             table["name"], detail={"label": f["label"]})
    return jsonify(ok=True)


@tables_bp.post("/tables/<int:tid>/fields/reorder")
def reorder_fields(tid):
    """按传入的字段 id 顺序重排（数据表列顺序与字段管理顺序一致）"""
    if not g.is_admin():
        return jsonify(ok=False, message="需要管理员权限"), 401
    table = get_table(tid)
    if not table:
        return jsonify(ok=False, message="表不存在"), 404
    body = request.get_json(force=True, silent=True) or {}
    ids = body.get("ids")
    if not isinstance(ids, list) or not ids:
        return jsonify(ok=False, message="缺少字段顺序"), 400
    exist = [f["id"] for f in table["fields"]]
    ordered = []
    for i in ids:
        try:
            i = int(i)
        except (TypeError, ValueError):
            continue
        if i in exist and i not in ordered:
            ordered.append(i)
    ordered += [i for i in exist if i not in ordered]
    for sort, fid in enumerate(ordered, 1):
        D.execute("UPDATE fields SET sort=? WHERE id=? AND table_id=?",
                  (sort, fid, tid))
    D.log_op(g.req_user_name(), "field_reorder", tid, table["name"],
             detail={"order": ordered})
    return jsonify(ok=True)


# ---------------- 可选值 ----------------

@tables_bp.get("/tables/<int:tid>/options")
def table_options(tid):
    if not g.can_read():
        return jsonify(ok=False, message="请先登录"), 401
    table = get_table(tid)
    if not table:
        return jsonify(ok=False, message="表不存在"), 404
    records = load_records(tid)
    out = {}
    for f in table["fields"]:
        if f["type"] == "color_tag":
            opts = color_options(f["options"])
            known = {o["value"] for o in opts}
            for r in records:
                v = str(r["data"].get(f["key"]) or "").strip()
                if v and v not in known:
                    opts.append({"value": v, "color": auto_color(len(opts))})
                    known.add(v)
            out[f["key"]] = opts
        elif f["type"] in ("select", "multi_select", "radio", "checkbox"):
            vals = list(f["options"])
            for r in records:
                v = r["data"].get(f["key"])
                items = v if isinstance(v, list) else [v]
                for it in items:
                    it = str(it or "").strip()
                    if it and it not in vals:
                        vals.append(it)
            out[f["key"]] = vals
        else:
            out[f["key"]] = None
    return jsonify(ok=True, options=out)


# ---------------- 记录 ----------------

@tables_bp.get("/tables/<int:tid>/records")
def list_records(tid):
    if not g.can_read():
        return jsonify(ok=False, message="请先登录"), 401
    table = get_table(tid)
    if not table:
        return jsonify(ok=False, message="表不存在"), 404
    records = apply_query(decorate(table, load_records(tid)), table, request.args)
    total = len(records)
    mode = request.args.get("mode", "lazy")
    page = max(1, int(request.args.get("page", 1)))
    size = min(500, max(1, int(request.args.get("page_size", 100 if mode == "page" else 50))))
    start = (page - 1) * size
    items = records[start:start + size]
    return jsonify(ok=True, total=total, page=page, page_size=size,
                   has_more=start + size < total,
                   items=[record_row(r) for r in items],
                   fields=table["fields"])


@tables_bp.post("/tables/<int:tid>/records")
def create_record(tid):
    if not g.can_add():
        return jsonify(ok=False, message="当前未开放申请权限，请先登录"), 401
    table = get_table(tid)
    if not table:
        return jsonify(ok=False, message="表不存在"), 404
    body = request.get_json(force=True, silent=True) or {}
    user = g.req_user_name()
    data = body.get("data") or {}
    # 登录用户：申请人锁定为当前用户名；访客：保留下拉选择/自行输入的值
    u = g.current_user()
    if u and any(f["key"] == "applicant" for f in table["fields"]):
        data["applicant"] = u["username"]
    record, err = do_create_record(table, data, user)
    if err:
        return jsonify(ok=False, message=err), 400
    D.log_op(user, "record_add", tid, table["name"],
             target=record_title(record["data"]),
             detail={"data": record["data"]})
    # 通知（后台线程，不阻塞响应）
    if D.get_setting("notify_enabled") == "1" and D.get_setting("notify_on_add") == "1":
        from .notify import send_notification_async
        send_notification_async("add", table, record["data"], user)
    return jsonify(ok=True, record=record_row(record))


@tables_bp.post("/tables/<int:tid>/records/batch")
def create_records_batch(tid):
    """批量申请：逐条创建（成功的先入库），失败的返回原因由前端标红重交；
    通知整批只发一条汇总"""
    if not g.can_add():
        return jsonify(ok=False, message="当前未开放申请权限，请先登录"), 401
    table = get_table(tid)
    if not table:
        return jsonify(ok=False, message="表不存在"), 404
    body = request.get_json(force=True, silent=True) or {}
    items = body.get("items")
    if not isinstance(items, list) or not items:
        return jsonify(ok=False, message="没有可提交的数据"), 400
    if len(items) > 20:
        return jsonify(ok=False, message="单次最多批量申请 20 条"), 400
    user = g.req_user_name()
    u = g.current_user()
    has_applicant = any(f["key"] == "applicant" for f in table["fields"])
    results, added = [], []
    for i, it in enumerate(items):
        data = ((it or {}).get("data")) or {}
        # 登录用户：申请人锁定为当前用户名；访客：保留下拉选择/自行输入的值
        if u and has_applicant:
            data["applicant"] = u["username"]
        try:
            record, err = do_create_record(table, data, user)
        except Exception as e:  # 单条异常不中断整批
            results.append({"index": i, "ok": False, "message": f"创建失败: {e}"})
            continue
        if err:
            results.append({"index": i, "ok": False, "message": err})
            continue
        D.log_op(user, "record_add", tid, table["name"],
                 target=record_title(record["data"]),
                 detail={"data": record["data"]})
        added.append(record)
        results.append({"index": i, "ok": True, "record": record_row(record)})
    # 批量合并通知：至少 1 条成功才发；仅 1 条时用单条样式，多条才用批量汇总样式
    if added and D.get_setting("notify_enabled") == "1" and D.get_setting("notify_on_add") == "1":
        from .notify import send_notification_async, send_batch_notification_async
        if len(added) == 1:
            send_notification_async("add", table, added[0]["data"], user)
        else:
            send_batch_notification_async(table, added, user)
    # 部分失败时 ok 仍为 true（由 partial 标记），避免前端拦截器全局弹错
    return jsonify(ok=True, partial=len(added) < len(items),
                   added=len(added), results=results)


def _check_owner(rid):
    """登录用户可操作自己的记录，管理员可操作全部；返回 (user, record) 或错误响应"""
    u = g.current_user()
    if not u:
        return None, None, (jsonify(ok=False, message="请先登录"), 401)
    r = D.query("SELECT * FROM records WHERE id=?", (rid,), one=True)
    if not r:
        return None, None, (jsonify(ok=False, message="记录不存在"), 404)
    if u["role"] != "admin" and r["created_by"] != u["username"]:
        return None, None, (jsonify(ok=False, message="只能操作自己创建的数据"), 403)
    return u, r, None


@tables_bp.put("/records/<int:rid>")
def update_record(rid):
    u, r, err = _check_owner(rid)
    if err:
        return err
    if r.get("deleted_at"):
        return jsonify(ok=False, message="记录已在回收站中，请先恢复"), 404
    table = get_table(r["table_id"])
    old = json.loads(r["data"])
    body = request.get_json(force=True, silent=True) or {}
    raw = body.get("data") or {}
    fmap = field_map(table)
    data = {k: v for k, v in raw.items() if k in fmap}
    if isinstance(old.get("_frozen"), dict):
        data["_frozen"] = dict(old["_frozen"])  # 沿用已冻结日期
    if isinstance(old.get("_started"), dict):
        data["_started"] = dict(old["_started"])  # 沿用起始条件命中日
    norm_record_values(table, data)
    bad = contact_errors(table, data)
    if bad:
        return jsonify(ok=False,
                       message=f"联系方式格式不正确：{'、'.join(bad[:5])}"), 400
    stamp_started(table, data, old_data=old, updated_at=r.get("updated_at"))
    stamp_frozen(table, data, old_data=old, updated_at=r.get("updated_at"))
    if "sn" in fmap:
        data["sn"] = old.get("sn")  # 序号不可改
    if "applicant" in fmap and u["role"] != "admin":
        data["applicant"] = old.get("applicant")  # 申请人不可篡改（管理员可修正）
    if "apply_time" in fmap and not str(data.get("apply_time") or "").strip():
        data["apply_time"] = D.now_str()
    missing = [f["label"] for f in table["fields"]
               if f["required"] and not str(data.get(f["key"], "") or "").strip()
               and f["key"] != "sn"]
    if missing:
        return jsonify(ok=False, message=f"必填项未填写：{'、'.join(missing)}"), 400
    try:
        D.execute("UPDATE records SET data=?, updated_at=? WHERE id=?",
                  (json.dumps(data, ensure_ascii=False), D.now_str(), rid))
    except sqlite3.Error as e:
        return jsonify(ok=False, message=f"保存失败：{e}"), 400
    merge_options(table, data)
    changes = {}
    for k, v in data.items():
        if str(old.get(k, "")) != str(v):
            changes[fmap[k]["label"] if k in fmap else k] = [old.get(k), v]
    D.log_op(g.req_user_name(), "record_update", table["id"], table["name"],
             target=record_title(data),
             detail={"changes": changes})
    return jsonify(ok=True)


@tables_bp.route("/records/<int:rid>", methods=["DELETE", "POST"])
def delete_record(rid):
    """删除记录（软删除进回收站；POST 为兼容拦截 DELETE 方法的代理环境）"""
    u, r, err = _check_owner(rid)
    if err:
        return err
    if r.get("deleted_at"):
        return jsonify(ok=False, message="记录已在回收站中"), 404
    table = get_table(r["table_id"])
    data = json.loads(r["data"])
    D.execute("UPDATE records SET deleted_at=?, deleted_by=? WHERE id=?",
              (D.now_str(), g.req_user_name(), rid))
    D.log_op(g.req_user_name(), "record_delete", table["id"], table["name"],
             target=record_title(data),
             detail={"data": data})
    if D.get_setting("notify_enabled") == "1" and D.get_setting("notify_on_delete") == "1":
        from .notify import send_notification_async
        send_notification_async("delete", table, data, g.req_user_name())
    return jsonify(ok=True, message="已移入回收站")


# ---------------- 回收站 ----------------

def _recycle_user():
    """回收站操作者：管理员管全部，普通用户管自己删除的；访客无权限"""
    u = g.current_user()
    return u, u["role"] == "admin" if u else None


def _recycle_target(r, u, admin):
    """校验一条回收站记录是否可被当前用户操作，返回错误信息或 None"""
    if not r:
        return "记录不存在"
    if not r["deleted_at"]:
        return "记录不在回收站中"
    if not admin and r["created_by"] != u["username"]:
        return "只能操作自己删除的数据"
    return None


def _recycle_where(u, admin, tid=None):
    cond, args = ["r.deleted_at IS NOT NULL"], []
    if not admin:
        cond.append("r.created_by=?")
        args.append(u["username"])
    if tid:
        cond.append("r.table_id=?")
        args.append(int(tid))
    return " AND ".join(cond), args


@tables_bp.get("/recycle")
def list_recycle():
    u, admin = _recycle_user()
    if not u:
        return jsonify(ok=False, message="请先登录"), 401
    where, args = _recycle_where(u, admin, request.args.get("table_id"))
    rows = D.query(
        "SELECT r.id, r.table_id, r.data, r.created_at, r.updated_at, r.created_by, "
        "r.deleted_at, r.deleted_by, "
        "t.name table_name FROM records r JOIN tables t ON t.id = r.table_id "
        f"WHERE {where} ORDER BY r.deleted_at DESC, r.id DESC", tuple(args))
    kw = (request.args.get("search") or "").strip().lower()
    items = []
    for r in rows:
        try:
            r["data"] = json.loads(r["data"])
        except Exception:
            r["data"] = {}
        if kw:
            hay = json.dumps(r["data"], ensure_ascii=False).lower() + \
                  " " + (r["table_name"] or "").lower()
            if kw not in hay:
                continue
        items.append(r)
    tables = D.query("SELECT id, name FROM tables ORDER BY id")
    return jsonify(ok=True, items=items, total=len(items), tables=tables)


@tables_bp.post("/recycle/restore")
def recycle_restore():
    """恢复回收站记录：序号冲突时自动重排"""
    u, admin = _recycle_user()
    if not u:
        return jsonify(ok=False, message="请先登录"), 401
    body = request.get_json(force=True, silent=True) or {}
    ids = body.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify(ok=False, message="未选择要恢复的数据"), 400
    results, restored = [], []
    for rid in ids[:100]:
        r = D.query("SELECT * FROM records WHERE id=?", (rid,), one=True)
        err = _recycle_target(r, u, admin)
        if err:
            results.append({"id": rid, "ok": False, "message": err})
            continue
        data = json.loads(r["data"])
        # 序号与现有数据冲突时自动改为最大序号 + 1
        try:
            sn = int(data.get("sn") or 0)
        except (TypeError, ValueError):
            sn = 0
        if sn and D.query(
                "SELECT id FROM records WHERE table_id=? AND deleted_at IS NULL "
                "AND CAST(json_extract(data,'$.sn') AS TEXT)=? AND id<>?",
                (r["table_id"], str(sn), rid), one=True):
            mx = D.query(
                "SELECT MAX(CAST(json_extract(data,'$.sn') AS INTEGER)) m FROM records "
                "WHERE table_id=? AND deleted_at IS NULL", (r["table_id"],), one=True)["m"] or 0
            data["sn"] = int(mx) + 1
            D.execute("UPDATE records SET data=? WHERE id=?",
                      (json.dumps(data, ensure_ascii=False), rid))
        D.execute("UPDATE records SET deleted_at=NULL, deleted_by=NULL, updated_at=? WHERE id=?",
                  (D.now_str(), rid))
        results.append({"id": rid, "ok": True})
        restored.append(data)
    if restored:
        nos = [record_title(d) for d in restored]
        D.log_op(u["username"], "recycle_restore", detail={"count": len(restored), "nos": nos})
    return jsonify(ok=True, restored=len(restored), results=results)


@tables_bp.post("/recycle/delete")
def recycle_delete():
    """彻底删除回收站记录（不可恢复）"""
    u, admin = _recycle_user()
    if not u:
        return jsonify(ok=False, message="请先登录"), 401
    body = request.get_json(force=True, silent=True) or {}
    ids = body.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify(ok=False, message="未选择要删除的数据"), 400
    results, removed = [], []
    for rid in ids[:100]:
        r = D.query("SELECT * FROM records WHERE id=?", (rid,), one=True)
        err = _recycle_target(r, u, admin)
        if err:
            results.append({"id": rid, "ok": False, "message": err})
            continue
        data = json.loads(r["data"])
        D.execute("DELETE FROM records WHERE id=?", (rid,))
        results.append({"id": rid, "ok": True})
        removed.append(record_title(data))
    if removed:
        D.log_op(u["username"], "recycle_delete", detail={"count": len(removed), "nos": removed})
    return jsonify(ok=True, removed=len(removed), results=results)


@tables_bp.post("/recycle/clear")
def recycle_clear():
    """清空回收站（可按表清空），普通用户仅清空自己删除的部分"""
    u, admin = _recycle_user()
    if not u:
        return jsonify(ok=False, message="请先登录"), 401
    body = request.get_json(force=True, silent=True) or {}
    tid = body.get("table_id")
    where, args = _recycle_where(u, admin, tid)
    cnt = D.query(f"SELECT COUNT(*) c FROM records r WHERE {where}", tuple(args), one=True)["c"]
    if not cnt:
        return jsonify(ok=True, removed=0, message="回收站已是空的")
    D.execute(f"DELETE FROM records WHERE id IN (SELECT r.id FROM records r WHERE {where})",
              tuple(args))
    D.log_op(u["username"], "recycle_clear",
             table_id=int(tid) if tid else None, detail={"count": cnt})
    return jsonify(ok=True, removed=cnt, message=f"已清空 {cnt} 条记录")


# ---------------- 导入 / 导出 ----------------

@tables_bp.post("/tables/<int:tid>/import")
def import_records(tid):
    if not g.is_admin():
        return jsonify(ok=False, message="需要管理员权限"), 401
    table = get_table(tid)
    if not table:
        return jsonify(ok=False, message="表不存在"), 404
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(ok=False, message="未选择文件"), 400
    from . import excelio
    result = excelio.import_xlsx(table, f)
    if result["added"] > 0:
        D.log_op(g.req_user_name(), "import", tid, table["name"],
                 detail={"added": result["added"],
                         "failed": len(result["failed"]),
                         "file": f.filename})
    D.sys_log("INFO", "IMPORT",
             f"导入 {table['name']}: 成功 {result['added']} 条，失败 {len(result['failed'])} 条")
    return jsonify(ok=True, **result)


@tables_bp.get("/tables/<int:tid>/export")
def export_records(tid):
    if not g.can_read():
        return jsonify(ok=False, message="请先登录"), 401
    table = get_table(tid)
    if not table:
        return jsonify(ok=False, message="表不存在"), 404
    records = apply_query(load_records(tid), table, request.args)
    from . import excelio
    resp = excelio.export_xlsx(table, records)
    D.log_op(g.req_user_name(), "export", tid, table["name"],
             detail={"count": len(records)})
    return resp


@tables_bp.get("/tables/<int:tid>/template")
def import_template(tid):
    if not g.is_admin():
        return jsonify(ok=False, message="需要管理员权限"), 401
    table = get_table(tid)
    if not table:
        return jsonify(ok=False, message="表不存在"), 404
    from . import excelio
    return excelio.export_xlsx(table, [], template=True)
