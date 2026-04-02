"""
Apple Calendar同步模块
使用osascript与macOS Calendar交互
"""
import subprocess
import json
import sys
from datetime import datetime, date, timedelta, timezone, timedelta as td
from pathlib import Path
from typing import List, Dict, Optional

# 东八区当前日期
def today_cst() -> date:
    """返回 Asia/Shanghai 时区的今日日期"""
    return datetime.now(timezone(td(hours=8))).date()

# 处理相对导入
try:
    from .db import get_weekly_plan, get_today_tasks
    from ..config import DOMAIN_NAMES
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from core.db import get_weekly_plan, get_today_tasks
    from config import DOMAIN_NAMES

CALENDAR_NAME = "学习助手"


def ensure_calendar_exists():
    """确保学习助手日历存在"""
    # 先激活Calendar应用获取权限
    activate_script = '''
    tell application "Calendar"
        activate
        return "Activated"
    end tell
    '''
    _run_applescript(activate_script)

    # 检查/创建日历
    script = f'''
    tell application "Calendar"
        set calName to "{CALENDAR_NAME}"
        try
            set myCal to first calendar whose name is calName
            return "OK"
        on error
            try
                set myCal to make new calendar with properties {{name:calName}}
                return "OK"
            on error errMsg
                return "Error: " & errMsg
            end try
        end try
    end tell
    '''
    result = _run_applescript(script)
    print(f"  [Debug] ensure_calendar_exists: {result}")
    return result == "OK"


def sync_week_to_calendar(week_start: date):
    """将本周计划同步到Apple Calendar"""
    if not ensure_calendar_exists():
        print("⚠️ 无法创建日历，请检查权限")
        return False

    # 先清除本周旧事件
    _clear_week_events(week_start)

    # 获取本周计划
    plans = get_weekly_plan(week_start)

    synced = 0
    for plan in plans:
        if _create_event(plan):
            synced += 1

    print(f"✓ 已同步 {synced} 个事件到Apple Calendar")
    return True


def _create_event(plan: Dict, override_start_time: str = None, override_end_time: str = None) -> bool:
    """创建单个日历事件
    Args:
        plan: 计划字典，必须包含 scheduled_date, time_slot, title, domain, planned_hours, id
        override_start_time: 可选，覆盖起始时间（格式 HH:MM）
        override_end_time: 可选，覆盖结束时间（格式 HH:MM）
    """
    scheduled_date = plan['scheduled_date']
    if isinstance(scheduled_date, str):
        scheduled_date = date.fromisoformat(scheduled_date)
    elif not isinstance(scheduled_date, date):
        scheduled_date = today_cst()

    # 解析时间段
    time_slot = plan['time_slot']  # "09:00-12:00"
    start_time_str, end_time_str = time_slot.split('-')

    # 事件标题和描述
    domain_name = DOMAIN_NAMES.get(plan['domain'], plan['domain'])
    title = f"[学习] {domain_name} | {plan['title']}"

    description = f"学习资料: {plan['title']}; 领域: {domain_name}; 预估: {plan['planned_hours']}h; ID: {plan['id']}"

    # 使用覆盖时间（完成计划时）或默认时间段
    actual_start = override_start_time or start_time_str
    actual_end = override_end_time or end_time_str
    print(f"    创建事件: {title} @ {scheduled_date} {actual_start}-{actual_end}")

    # 解析时间分量
    start_h, start_m = actual_start.split(':')
    end_h, end_m = actual_end.split(':')

    # 关键：先设 day=1 避免溢出，再设 month/year，再设 hours/minutes
    script = f'''tell application "Calendar"
    set calName to "{CALENDAR_NAME}"
    set myCal to first calendar whose name is calName
    set startDate to (current date)
    set day of startDate to {scheduled_date.day}
    set month of startDate to {scheduled_date.month}
    set year of startDate to {scheduled_date.year}
    set hours of startDate to {int(start_h)}
    set minutes of startDate to {int(start_m)}
    set seconds of startDate to 0
    set endDate to (current date)
    set day of endDate to {scheduled_date.day}
    set month of endDate to {scheduled_date.month}
    set year of endDate to {scheduled_date.year}
    set hours of endDate to {int(end_h)}
    set minutes of endDate to {int(end_m)}
    set seconds of endDate to 0
    make new event at end of events of myCal with properties {{summary:"{title}", start date:startDate, end date:endDate, description:"{description}"}}
    return "Created"
end tell'''

    result = _run_applescript(script)
    success = result == "Created"
    if not success:
        print(f"    [创建失败] {result[:100]}")
    return success


def _delete_event_by_plan_id(plan_id: int) -> bool:
    """根据计划ID删除日历事件"""
    if not ensure_calendar_exists():
        return False

    script = f'''tell application "Calendar"
    set calName to "{CALENDAR_NAME}"
    try
        set myCal to first calendar whose name is calName
        set evtList to every event of myCal
        set targetUID to ""
        repeat with i from 1 to (count of evtList)
            set evt to item i of evtList
            set evtDesc to description of evt
            if evtDesc contains "ID: {plan_id}" then
                set targetUID to uid of evt
                delete evt
                exit repeat
            end if
        end repeat
        if targetUID is "" then
            return "NotFound"
        else
            return "Deleted"
        end if
    on error errMsg
        return "Error:" & errMsg
    end try
end tell'''

    result = _run_applescript(script)
    return result.startswith("Deleted")


def _update_event(plan_id: int, scheduled_date: date, new_start_time: str, new_end_time: str, plan_info: Dict = None) -> bool:
    """更新日历事件的时间"""
    if not ensure_calendar_exists():
        return False

    # 先查找并删除旧事件
    deleted = _delete_event_by_plan_id(plan_id)
    if not deleted:
        print(f"    [更新失败] 未找到事件 ID:{plan_id}")
        return False

    # 如果提供了计划信息，创建新事件（使用真实时间）
    if plan_info:
        return _create_event(plan_info, override_start_time=new_start_time, override_end_time=new_end_time)

    return True


def _clear_week_events(week_start: date, week_end: date = None):
    """清除本周学习助手日历中的学习事件（只删除以[学习]开头的事件）"""
    if week_end is None:
        week_end = week_start + timedelta(days=7)

    script = f'''tell application "Calendar"
    set calName to "{CALENDAR_NAME}"
    try
        set myCal to first calendar whose name is calName
        set eventIDs to {{}}
        set startRange to (current date)
        set day of startRange to {week_start.day}
        set month of startRange to {week_start.month}
        set year of startRange to {week_start.year}
        set hours of startRange to 0
        set minutes of startRange to 0
        set seconds of startRange to 0
        set endRange to (current date)
        set day of endRange to {week_end.day}
        set month of endRange to {week_end.month}
        set year of endRange to {week_end.year}
        set hours of endRange to 0
        set minutes of endRange to 0
        set seconds of endRange to 0

        set evtList to every event of myCal
        repeat with i from 1 to (count of evtList)
            set evt to item i of evtList
            set evtStart to start date of evt
            if evtStart >= startRange and evtStart < endRange then
                if summary of evt starts with "[学习]" then
                    set end of eventIDs to uid of evt
                end if
            end if
        end repeat

        set deletedCount to 0
        repeat with evtID in eventIDs
            try
                set evtToDelete to first event of myCal whose uid is evtID
                delete evtToDelete
                set deletedCount to deletedCount + 1
            end try
        end repeat

        return "Cleared:" & deletedCount
    on error errMsg
        return "Error:" & errMsg
    end try
end tell'''

    result = _run_applescript(script)
    print(f"  [Calendar] {result}")


def _clear_future_events(from_date: date):
    """清除学习助手日历中从指定日期开始的所有未来事件"""
    script = f'''tell application "Calendar"
    set calName to "{CALENDAR_NAME}"
    try
        set myCal to first calendar whose name is calName
        set eventsToDelete to {{}}
        set startRange to (current date)
        set day of startRange to {from_date.day}
        set month of startRange to {from_date.month}
        set year of startRange to {from_date.year}
        set hours of startRange to 0
        set minutes of startRange to 0
        set seconds of startRange to 0

        set evtList to every event of myCal
        repeat with i from 1 to (count of evtList)
            set evt to item i of evtList
            if start date of evt >= startRange then
                set end of eventsToDelete to evt
            end if
        end repeat

        repeat with evt in eventsToDelete
            delete evt
        end repeat

        return "Cleared"
    on error
        return "Error"
    end try
end tell'''

    result = _run_applescript(script)
    return result == "Cleared"


def check_today_completion() -> List[Dict]:
    """检查今日日历事件的完成情况"""
    today = today_cst()

    # 从Calendar获取今日事件
    events = _get_today_events()

    # 从数据库获取今日计划
    db_tasks = get_today_tasks()
    db_task_ids = {t['id'] for t in db_tasks}

    results = []
    for event in events:
        # 解析事件中的计划ID
        plan_id = _extract_plan_id(event.get('description', ''))

        if plan_id and plan_id in db_task_ids:
            results.append({
                'plan_id': plan_id,
                'title': event['title'],
                'start_time': event['start_time'],
                'completed': False,  # 需要用户确认
                'in_calendar': True
            })

    return results


def _get_today_events() -> List[Dict]:
    """获取今日学习助手日历中的事件"""
    today = today_cst()
    tomorrow = today + timedelta(days=1)

    script = f'''
    tell application "Calendar"
        set calName to "{CALENDAR_NAME}"
        try
            set myCal to first calendar whose name is calName
            set eventList to {{}}

            set startRange to (current date)
            set day of startRange to {today.day}
            set month of startRange to {today.month}
            set year of startRange to {today.year}
            set hours of startRange to 0
            set minutes of startRange to 0
            set seconds of startRange to 0
            set endRange to (current date)
            set day of endRange to {tomorrow.day}
            set month of endRange to {tomorrow.month}
            set year of endRange to {tomorrow.year}
            set hours of endRange to 0
            set minutes of endRange to 0
            set seconds of endRange to 0

            set evtList to every event of myCal
            repeat with i from 1 to (count of evtList)
                set evt to item i of evtList
                if start date of evt >= startRange and start date of evt < endRange then
                    set eventInfo to "TITLE:" & (summary of evt) & "|START:" & (start date of evt) & "|DESC:" & (description of evt)
                    set end of eventList to eventInfo
                end if
            end repeat

            return eventList as string
        on error errMsg
            return "Error: " & errMsg
        end try
    end tell
    '''

    result = _run_applescript(script)
    if result.startswith("Error"):
        return []

    # 解析结果
    events = []
    for line in result.split('|'):
        if line.startswith('TITLE:'):
            events.append({
                'title': line.replace('TITLE:', '').strip(),
                'start_time': '',
                'description': ''
            })
        elif line.startswith('START:'):
            if events:
                events[-1]['start_time'] = line.replace('START:', '').strip()
        elif line.startswith('DESC:'):
            if events:
                events[-1]['description'] = line.replace('DESC:', '').strip()

    return events


def _extract_plan_id(description: str) -> Optional[int]:
    """从事件描述中提取计划ID"""
    import re
    match = re.search(r'计划ID:\s*(\d+)', description)
    if match:
        return int(match.group(1))
    return None


def _run_applescript(script: str) -> str:
    """运行AppleScript"""
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
        # Debug
        if result.returncode != 0:
            print(f"  [AppleScript Error] {output[:200]}")
        return output
    except Exception as e:
        print(f"  [Exception] {e}")
        return f"Error: {e}"


def quick_add_event(title: str, date_str: str, start_time: str, end_time: str):
    """快速添加单个事件到日历"""
    if not ensure_calendar_exists():
        return False

    start_h, start_m = start_time.split(':')
    end_h, end_m = end_time.split(':')
    y, m, d = map(int, date_str.split('-'))

    script_template = '''tell application "Calendar"
    set myCal to first calendar whose name is "{cal_name}"
    set startDate to (current date)
    set day of startDate to {d}
    set month of startDate to {m}
    set year of startDate to {y}
    set hours of startDate to {start_h}
    set minutes of startDate to {start_m}
    set endDate to (current date)
    set day of endDate to {d}
    set month of endDate to {m}
    set year of endDate to {y}
    set hours of endDate to {end_h}
    set minutes of endDate to {end_m}
    make new event at end of events of myCal with properties {{summary:"{title}", start date:startDate, end date:endDate}}
    return "Created"
end tell'''

    script = script_template.format(
        cal_name=CALENDAR_NAME,
        y=y, m=m, d=d,
        start_h=start_h, start_m=start_m,
        end_h=end_h, end_m=end_m,
        title=title
    )

    return _run_applescript(script)


def sync_session_to_calendar(material_id: int, actual_start: str, actual_end: str,
                             actual_hours: float, quality_rating: int = 3) -> bool:
    """
    将学习记录同步到Apple Calendar的过去时间中
    """
    if not ensure_calendar_exists():
        print("⚠️ 无法创建日历，请检查权限")
        return False

    # 从数据库获取资料信息
    try:
        from .db import get_connection
        with get_connection() as conn:
            row = conn.execute(
                'SELECT title, domain FROM materials WHERE id = ?',
                (material_id,)
            ).fetchone()
            if not row:
                print(f"❌ 资料 #{material_id} 不存在")
                return False
            title, domain = row
    except Exception as e:
        print(f"❌ 获取资料信息失败: {e}")
        return False

    # 解析时间
    try:
        if isinstance(actual_start, str):
            start_dt = datetime.fromisoformat(actual_start.replace('Z', '+00:00').replace('+00:00', ''))
        else:
            start_dt = actual_start

        if isinstance(actual_end, str):
            end_dt = datetime.fromisoformat(actual_end.replace('Z', '+00:00').replace('+00:00', ''))
        else:
            end_dt = actual_end
    except Exception as e:
        print(f"❌ 时间格式错误: {e}")
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(hours=actual_hours)

    # 构建事件标题和描述
    domain_name = DOMAIN_NAMES.get(domain, domain)
    event_title = f"[✓已完成] {domain_name} | {title}"
    description = f"实际学习: {actual_hours}小时\n质量评分: {'⭐' * quality_rating}\n资料ID: {material_id}"

    script = f'''tell application "Calendar"
    set calName to "{CALENDAR_NAME}"
    set myCal to first calendar whose name is calName
    set startDate to (current date)
    set day of startDate to {start_dt.day}
    set month of startDate to {start_dt.month}
    set year of startDate to {start_dt.year}
    set hours of startDate to {start_dt.hour}
    set minutes of startDate to {start_dt.minute}
    set seconds of startDate to 0
    set endDate to (current date)
    set day of endDate to {end_dt.day}
    set month of endDate to {end_dt.month}
    set year of endDate to {end_dt.year}
    set hours of endDate to {end_dt.hour}
    set minutes of endDate to {end_dt.minute}
    set seconds of endDate to 0
    make new event at end of events of myCal with properties {{summary:"{event_title}", start date:startDate, end date:endDate, description:"{description}"}}
    return "Created"
end tell'''

    result = _run_applescript(script)
    success = result == "Created"

    if success:
        print(f"✓ 已记录到Calendar: {event_title}")
        print(f"  时间: {start_dt.strftime('%Y-%m-%d %H:%M')} - {end_dt.strftime('%H:%M')}")
        print(f"  时长: {actual_hours}小时")
    else:
        print(f"❌ 记录到Calendar失败: {result[:100]}")

    return success
