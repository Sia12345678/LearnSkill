"""
学习计划生成模块
策略：周末冲刺 + 周内保温
数据来源：Obsidian MD 表格
"""
import sys
import re
from datetime import date, timedelta, datetime, timezone, timedelta as td
from pathlib import Path
from typing import List, Dict, Optional

# 处理相对导入
try:
    from .db import get_connection, create_plan
    from ..config import TIME_RULES, DOMAIN_NAMES
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from core.db import get_connection, create_plan
    from config import TIME_RULES, DOMAIN_NAMES


# Obsidian 文件路径
OBSIDIAN_PATH = Path.home() / "Documents" / "Obsidian Vault" / "学习助手" / "学习资料库.md"


# 东八区当前日期
def today_cst() -> date:
    """返回 Asia/Shanghai 时区的今日日期"""
    return datetime.now(timezone(td(hours=8))).date()


def parse_md_table(content: str) -> List[Dict]:
    """从 MD 表格解析资源"""
    materials = []
    lines = content.split('\n')
    in_table = False
    header_indices = {}

    for line in lines:
        line = line.strip()

        # 检测表格开始
        if '标题' in line and line.startswith('|'):
            in_table = True
            headers = [h.strip() for h in line.split('|')[1:-1]]
            for i, h in enumerate(headers):
                header_indices[h] = i
            continue

        # 检测表格结束
        if in_table and not line.startswith('|'):
            break

        # 解析表格数据行
        if in_table and line.startswith('|') and not line.startswith('|---'):
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) < 2:
                continue

            try:
                title = cells[header_indices.get('标题', 0)]
                domain = cells[header_indices.get('领域', 1)]
                estimated = cells[header_indices.get('预估(h)', 2)]
                progress = cells[header_indices.get('进度(%)', 3)]
                link = cells[header_indices.get('链接', 5)]
                frozen_str = cells[header_indices.get('冻结', 7)].strip().lower() if 7 < len(cells) else ''

                # 解析链接
                url = None
                if link.startswith('['):
                    url_match = re.search(r'\[.*?\]\((.*?)\)', link)
                    if url_match:
                        url = url_match.group(1)

                # 清理标题
                if title.startswith('《') and title.endswith('》'):
                    title = title[1:-1]

                materials.append({
                    'title': title,
                    'domain': domain if domain else 'work-ai',
                    'estimated_hours': float(estimated) if estimated and estimated != '' else 2.0,
                    'progress': int(progress) if progress and progress != '' else 0,
                    'url': url,
                    'status': 'completed' if (progress and int(progress) >= 100) else ('in_progress' if (progress and int(progress) > 0) else 'pending'),
                    'frozen': frozen_str == 'true'
                })
            except (ValueError, IndexError):
                continue

    return materials


def get_active_materials() -> List[Dict]:
    """获取进行中的资料（用于生成计划）：progress > 0 && < 100 && 未冻结"""
    if not OBSIDIAN_PATH.exists():
        return []

    content = OBSIDIAN_PATH.read_text(encoding='utf-8')
    materials = parse_md_table(content)

    # 只选已开始但未完成的、未冻结的（右边栏）
    return [m for m in materials if 0 < m.get('progress', 0) < 100 and not m.get('frozen', False)]


def calculate_priority(material: Dict) -> float:
    """简单优先级计算"""
    score = 5.0

    # 熟练度越低优先级越高
    # 技术类加分
    if material['domain'] in ['work-ai', 'dsml', 'quant']:
        score += 2

    # 已经开始的给予加分
    if material['progress'] > 0:
        score += 1

    return score


def generate_weekly_plan(week_start: Optional[date] = None, clear_existing: bool = True) -> List[Dict]:
    """
    生成本周学习计划

    策略:
    1. 读取 MD 表格，过滤未完成、未冻结的资料
    2. 周末(六日): 技术类任务，2-3小时/段
    3. 周内(一至五): 阅读类任务，1小时/晚
    4. 只安排今天或未来的日期
    """
    today = today_cst()

    if week_start is None:
        week_start = today - timedelta(days=today.weekday())  # 本周一

    # 清除本周已有计划
    if clear_existing:
        clear_weekly_plan(week_start)

    # 从 MD 读取未完成、未冻结的资料
    materials = get_active_materials()

    if not materials:
        return []

    # 按优先级排序
    materials.sort(key=calculate_priority, reverse=True)

    # 构建材料字典
    materials_dict = {}
    for i, m in enumerate(materials):
        materials_dict[i] = m

    plan = []

    # 周六安排
    saturday = week_start + timedelta(days=5)
    if saturday >= today:
        saturday_tasks = _plan_day(
            date=saturday,
            available_slots=TIME_RULES['weekend']['slots'],
            preferred_domains=TIME_RULES['weekend']['domains'],
            materials=materials_dict,
            used_keys=set()
        )
        plan.extend(saturday_tasks)

    # 周日安排
    sunday = week_start + timedelta(days=6)
    if sunday >= today:
        used_keys = {t['key'] for t in plan}
        sunday_tasks = _plan_day(
            date=sunday,
            available_slots=TIME_RULES['weekend']['slots'],
            preferred_domains=TIME_RULES['weekend']['domains'],
            materials=materials_dict,
            used_keys=used_keys
        )
        plan.extend(sunday_tasks)

    # 周内安排（周一到周五）
    used_keys = {t['key'] for t in plan}
    for i in range(5):
        weekday = week_start + timedelta(days=i)
        if weekday < today:
            continue
        weekday_tasks = _plan_day(
            date=weekday,
            available_slots=TIME_RULES['weekday']['slots'],
            preferred_domains=TIME_RULES['weekday']['domains'],
            materials=materials_dict,
            used_keys=used_keys,
            max_tasks_per_day=1
        )
        plan.extend(weekday_tasks)
        used_keys.update(t['key'] for t in weekday_tasks)

    # 保存到数据库
    saved_plans = []
    for task in plan:
        plan_id = create_plan(
            week_start=week_start,
            material_id=task['key'],
            planned_hours=task['hours'],
            scheduled_date=task['date'],
            time_slot=task['time_slot'],
            material_title=task['title'],
            material_domain=task['domain'],
            material_url=task.get('url')
        )
        task['id'] = plan_id
        saved_plans.append(task)

    # 同步到 Calendar
    _sync_to_calendar(saved_plans, week_start)

    return saved_plans


def _plan_day(date: date, available_slots: List[tuple],
              preferred_domains: List[str], materials: Dict,
              used_keys: set, max_tasks_per_day: int = 2) -> List[Dict]:
    """为一天安排任务"""
    tasks = []

    # 筛选候选材料
    candidates = [
        (key, m) for key, m in materials.items()
        if m['domain'] in preferred_domains and key not in used_keys
    ]

    # 按优先级排序
    candidates.sort(key=lambda x: calculate_priority(x[1]), reverse=True)

    slot_idx = 0
    for key, material in candidates:
        if slot_idx >= len(available_slots):
            break
        if len(tasks) >= max_tasks_per_day:
            break

        start_time, end_time = available_slots[slot_idx]
        estimated = material.get('estimated_hours', 2)
        allocated_hours = min(3, estimated)

        tasks.append({
            'key': key,
            'title': material['title'],
            'domain': material['domain'],
            'domain_name': DOMAIN_NAMES.get(material['domain'], material['domain']),
            'date': date.isoformat(),
            'time_slot': f"{start_time}-{end_time}",
            'hours': allocated_hours,
            'url': material.get('url')
        })

        used_keys.add(key)
        slot_idx += 1

    return tasks


def _sync_to_calendar(plans: List[Dict], week_start: date):
    """同步计划到 Apple Calendar"""
    try:
        from .calendar_sync import sync_week_to_calendar
        sync_week_to_calendar(week_start)  # 同步 week_start 到 week_start+6，覆盖今天到周日
    except Exception as e:
        print(f"Calendar 同步失败: {e}")


def clear_weekly_plan(week_start: Optional[date] = None) -> int:
    """清除本周的学习计划（按 week_start 锚点）"""
    if week_start is None:
        today = today_cst()
        week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)
    # 清除 Calendar
    try:
        from .calendar_sync import _clear_week_events
        _clear_week_events(week_start, week_end)
    except Exception as e:
        print(f"清除 Calendar 失败: {e}")

    # 清除数据库
    with get_connection() as conn:
        cursor = conn.execute(
            'SELECT COUNT(*) FROM plans WHERE week_start = ?',
            (week_start,)
        )
        count = cursor.fetchone()[0]

        if count > 0:
            conn.execute('DELETE FROM plans WHERE week_start = ?', (week_start,))
            conn.commit()
            print(f"已清除 {count} 个计划")
        else:
            print("本周暂无计划")

        return count


def get_plan_summary(week_start: Optional[date] = None) -> Dict:
    """获取计划摘要（返回结构化数据）：本周一到本周日"""
    today = today_cst()

    if week_start is None:
        week_start = today - timedelta(days=today.weekday())  # 本周一

    with get_connection() as conn:
        cursor = conn.execute('''
            SELECT id, material_title, material_domain, material_url,
                   planned_hours, scheduled_date, time_slot, status,
                   actual_start_time, actual_end_time, actual_hours
            FROM plans
            WHERE week_start = ?
            ORDER BY scheduled_date, time_slot
        ''', (week_start,))
        rows = cursor.fetchall()

    week_end = week_start + timedelta(days=6)

    if not rows:
        return {'plans': [], 'week': str(week_start), 'week_end': str(week_end)}

    plans = []
    for row in rows:
        plans.append({
            'id': row[0],
            'title': row[1],
            'domain': row[2] or 'work-ai',
            'url': row[3],
            'hours': row[4],
            'date': row[5],
            'time_slot': row[6],
            'status': row[7],
            'actual_start_time': row[8],
            'actual_end_time': row[9],
            'actual_hours': row[10]
        })

    return {
        'plans': plans,
        'week': str(week_start),
        'week_end': str(week_end)
    }
