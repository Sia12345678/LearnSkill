"""
极简文件读写服务
只做 MD 文件读写 + 计划生成，不做业务逻辑
"""
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pathlib import Path
import sys
import re
import sqlite3
from datetime import date, timedelta

app = Flask(__name__)
CORS(app)

# Dashboard 路径
DASHBOARD_PATH = Path.home() / "Documents" / "self_learning" / "learning-assistant" / "dashboard" / "index.html"

@app.route('/')
def serve_dashboard():
    """服务 Dashboard 页面"""
    return send_file(DASHBOARD_PATH, mimetype='text/html; charset=utf-8')

@app.route('/dashboard')
def serve_dashboard_alt():
    return send_file(DASHBOARD_PATH, mimetype='text/html; charset=utf-8')

# 配置文件路径
OBSIDIAN_PATH = Path.home() / "Documents" / "Obsidian Vault" / "学习助手" / "学习资料库.md"
ACHIEVEMENTS_PATH = Path.home() / "Documents" / "Obsidian Vault" / "学习助手" / "学习成果.md"
SKILL_PATH = Path(__file__).parent


def parse_md_table(content: str) -> list:
    """解析 MD 表格"""
    materials = []
    lines = content.split('\n')
    in_table = False
    header_indices = {}

    for line in lines:
        line = line.strip()
        if '标题' in line and line.startswith('|'):
            in_table = True
            headers = [h.strip() for h in line.split('|')[1:-1]]
            for i, h in enumerate(headers):
                header_indices[h] = i
            continue
        if in_table and not line.startswith('|'):
            break
        if in_table and line.startswith('|') and not line.startswith('|---'):
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) < 2:
                continue
            try:
                title = cells[header_indices.get('标题', 0)]
                domain = cells[header_indices.get('领域', 1)]
                estimated = cells[header_indices.get('预估(h)', 2)]
                progress = cells[header_indices.get('进度(%)', 3)]
                actual = cells[header_indices.get('已用(h)', 4)]
                link = cells[header_indices.get('链接', 5)]
                status = cells[header_indices.get('状态', 6)] if 6 < len(cells) else ''
                frozen = cells[header_indices.get('冻结', 7)].strip().lower() == 'true' if 7 < len(cells) else False

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
                    'actual_hours': float(actual) if actual and actual != '' else 0.0,
                    'url': url,
                    'status': status,
                    'frozen': frozen
                })
            except (ValueError, IndexError):
                continue
    return materials


def generate_md_table(materials: list) -> str:
    """生成 MD 表格"""
    lines = [
        "# 学习资料库",
        "",
        f"> 最后更新: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}",
        "",
        "## 学习资源",
        "",
        "| 标题 | 领域 | 预估(h) | 进度(%) | 已用(h) | 链接 | 状态 | 冻结 |",
        "|------|------|----------|----------|----------|------|------|------|"
    ]

    for m in materials:
        title = m.get('title', '')
        domain = m.get('domain', 'work-ai')
        estimated = m.get('estimated_hours', 0)
        progress = m.get('progress', 0)
        actual = m.get('actual_hours', 0)
        url = m.get('url', '')
        status = m.get('status', '')
        frozen = 'true' if m.get('frozen') else ''

        link = f"[链接]({url})" if url else ""

        lines.append(f"| {title} | {domain} | {estimated} | {progress} | {actual} | {link} | {status} | {frozen} |")

    lines.extend([
        "",
        "## 说明",
        "",
        "- 直接编辑表格即可添加/修改/删除资源",
        "- 领域可选：work-ai, dsml, quant, philosophy, literature, physics"
    ])

    return "\n".join(lines)


# ========== API 端点 ==========

@app.route('/api/resources', methods=['GET'])
def get_resources():
    """获取所有资源"""
    try:
        if not OBSIDIAN_PATH.exists():
            return jsonify({'success': False, 'error': '文件不存在'}), 404

        content = OBSIDIAN_PATH.read_text(encoding='utf-8')
        materials = parse_md_table(content)

        return jsonify({
            'success': True,
            'resources': materials
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/resources/update', methods=['POST'])
def update_resource():
    """更新资源（进度、时间）"""
    try:
        data = request.json
        title = data.get('title')
        progress = data.get('progress')
        actual_hours = data.get('actual_hours')
        frozen = data.get('frozen')

        if not title:
            return jsonify({'success': False, 'error': '标题不能为空'}), 400

        content = OBSIDIAN_PATH.read_text(encoding='utf-8')
        materials = parse_md_table(content)

        # 查找并更新
        updated = False
        for m in materials:
            if m['title'] == title:
                if progress is not None:
                    m['progress'] = progress
                    # 进度100%时自动标记done
                    m['status'] = 'done' if progress >= 100 else ''
                if actual_hours is not None:
                    m['actual_hours'] = actual_hours
                if frozen is not None:
                    m['frozen'] = bool(frozen)
                updated = True
                break

        if not updated:
            return jsonify({'success': False, 'error': '资源不存在'}), 404

        # 写回文件
        new_content = generate_md_table(materials)
        OBSIDIAN_PATH.write_text(new_content, encoding='utf-8')

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/resources/add', methods=['POST'])
def add_resource():
    """新增学习资源"""
    try:
        data = request.json
        title = data.get('title')
        domain = data.get('domain', 'work-ai')
        url = data.get('url', '')
        estimated_hours = float(data.get('estimated_hours', 0)) or 1.0

        if not title:
            return jsonify({'success': False, 'error': '标题不能为空'}), 400

        content = OBSIDIAN_PATH.read_text(encoding='utf-8')
        materials = parse_md_table(content)

        # 检查是否已存在
        for m in materials:
            if m['title'] == title:
                return jsonify({'success': False, 'error': '该资源已存在'}), 409

        # 添加新资源
        materials.append({
            'title': title,
            'domain': domain,
            'estimated_hours': estimated_hours,
            'progress': 0,
            'actual_hours': 0.0,
            'url': url,
            'status': '',
            'frozen': False
        })

        # 写回文件
        new_content = generate_md_table(materials)
        OBSIDIAN_PATH.write_text(new_content, encoding='utf-8')

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/resources/delete', methods=['POST'])
def delete_resource():
    """从 Obsidian MD 中删除资源"""
    try:
        data = request.json
        title = data.get('title')

        if not title:
            return jsonify({'success': False, 'error': '标题不能为空'}), 400

        content = OBSIDIAN_PATH.read_text(encoding='utf-8')
        materials = parse_md_table(content)

        # 过滤掉目标资源
        original_count = len(materials)
        materials = [m for m in materials if m['title'] != title]

        if len(materials) == original_count:
            return jsonify({'success': False, 'error': '资源不存在'}), 404

        # 写回文件
        new_content = generate_md_table(materials)
        OBSIDIAN_PATH.write_text(new_content, encoding='utf-8')

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/plans', methods=['GET'])
def get_plans():
    """获取本周计划"""
    try:
        sys.path.insert(0, str(SKILL_PATH))
        from core.planner import get_plan_summary

        result = get_plan_summary()
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/plans/generate', methods=['POST'])
def generate_plans():
    """生成学习计划"""
    try:
        sys.path.insert(0, str(SKILL_PATH))
        from core.planner import generate_weekly_plan

        plans = generate_weekly_plan(clear_existing=True)
        return jsonify({'success': True, 'plans': plans})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/plans/clear', methods=['POST'])
def clear_plans():
    """清除本周计划"""
    try:
        sys.path.insert(0, str(SKILL_PATH))
        from core.planner import clear_weekly_plan

        count = clear_weekly_plan(None)  # 内部用 today_cst() 计算周一开始
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/plans/add', methods=['POST'])
def add_plan():
    """新增一条学习计划（用于记录计划外的实际学习行为）"""
    try:
        data = request.json
        material_title = data.get('material_title')
        material_domain = data.get('material_domain', 'work-ai')
        material_url = data.get('material_url', '')
        planned_hours = float(data.get('planned_hours', 0)) or 1.0
        scheduled_date_str = data.get('scheduled_date')  # "YYYY-MM-DD"
        time_slot = data.get('time_slot')  # "HH:MM-HH:MM"

        if not material_title or not scheduled_date_str or not time_slot:
            return jsonify({'success': False, 'error': '请填写资源、日期和时间段'}), 400

        sched_date = date.fromisoformat(scheduled_date_str)
        week_start = sched_date - timedelta(days=sched_date.weekday())

        from core.db import get_connection
        # 查找或创建 material_id
        with get_connection() as conn:
            row = conn.execute(
                'SELECT id FROM materials WHERE title = ?', (material_title,)
            ).fetchone()
            db_material_id = row[0] if row else None

        if db_material_id is None:
            # 同步到 materials 表（只存基础字段）
            with get_connection() as conn:
                cursor = conn.execute('''
                    INSERT INTO materials (title, domain, url, source_type, estimated_hours, status)
                    VALUES (?, ?, ?, 'manual', ?, 'in_progress')
                ''', (material_title, material_domain, material_url, planned_hours))
                db_material_id = cursor.lastrowid

        from core.db import create_plan
        plan_id = create_plan(
            week_start=week_start,
            material_id=db_material_id,
            planned_hours=planned_hours,
            scheduled_date=sched_date,
            time_slot=time_slot,
            material_title=material_title,
            material_domain=material_domain,
            material_url=material_url
        )

        # 同步到 Calendar
        if plan_id:
            try:
                from core.calendar_sync import _create_event
                plan_info = {
                    'id': plan_id,
                    'title': material_title,
                    'domain': material_domain,
                    'url': material_url,
                    'planned_hours': planned_hours,
                    'scheduled_date': sched_date,
                    'time_slot': time_slot,
                }
                _create_event(plan_info)
            except Exception as e:
                print(f"Calendar 同步失败: {e}")

        return jsonify({'success': True, 'plan_id': plan_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/plans/delete', methods=['POST'])
def delete_plan():
    """删除单个计划"""
    try:
        data = request.json
        plan_id = data.get('plan_id')

        if not plan_id:
            return jsonify({'success': False, 'error': '缺少 plan_id'}), 400

        from core.db import get_connection
        from core.calendar_sync import _delete_event_by_plan_id

        # 获取计划日期（用于从 Calendar 删除）
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            plan = conn.execute(
                'SELECT id, scheduled_date FROM plans WHERE id = ?', (plan_id,)
            ).fetchone()

            if not plan:
                return jsonify({'success': False, 'error': '计划不存在'}), 404

        # 从数据库删除
        with get_connection() as conn:
            conn.execute('DELETE FROM plans WHERE id = ?', (plan_id,))

        # 从 Calendar 删除事件
        try:
            _delete_event_by_plan_id(plan_id)
        except Exception as e:
            print(f"Calendar 删除失败: {e}")

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/plans/modify', methods=['POST'])
def modify_plan():
    """修改计划内容或时间"""
    try:
        data = request.json
        plan_id = data.get('plan_id')
        new_material_title = data.get('material_title')
        new_material_domain = data.get('material_domain')
        new_material_url = data.get('material_url')
        new_scheduled_date = data.get('scheduled_date')  # "YYYY-MM-DD"
        new_time_slot = data.get('time_slot')  # "HH:MM-HH:MM"

        if not plan_id:
            return jsonify({'success': False, 'error': '缺少 plan_id'}), 400

        from core.db import get_connection
        from core.calendar_sync import _delete_event_by_plan_id, _create_event

        # 获取现有计划
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            plan = conn.execute(
                'SELECT * FROM plans WHERE id = ?', (plan_id,)
            ).fetchone()
            if not plan:
                return jsonify({'success': False, 'error': '计划不存在'}), 404
            plan = dict(plan)

        # 更新数据库
        sched_date = date.fromisoformat(new_scheduled_date)
        week_start = sched_date - timedelta(days=sched_date.weekday())

        with get_connection() as conn:
            conn.execute('''
                UPDATE plans SET
                    material_title = ?,
                    material_domain = ?,
                    material_url = ?,
                    scheduled_date = ?,
                    time_slot = ?,
                    week_start = ?
                WHERE id = ?
            ''', (
                new_material_title or plan['material_title'],
                new_material_domain or plan['material_domain'],
                new_material_url or plan['material_url'],
                new_scheduled_date,
                new_time_slot or plan['time_slot'],
                str(week_start),
                plan_id
            ))

        # 从 Calendar 删除旧事件
        try:
            _delete_event_by_plan_id(plan_id)
        except Exception as e:
            print(f"Calendar 删除旧事件失败: {e}")

        # 创建新事件
        try:
            updated_plan = {
                'id': plan_id,
                'title': new_material_title or plan['material_title'],
                'domain': new_material_domain or plan['material_domain'],
                'url': new_material_url or plan['material_url'],
                'planned_hours': plan['planned_hours'],
                'scheduled_date': sched_date,
                'time_slot': new_time_slot or plan['time_slot'],
            }
            _create_event(updated_plan)
        except Exception as e:
            print(f"Calendar 创建新事件失败: {e}")

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/plans/complete', methods=['POST'])
def complete_plan():
    """完成计划任务"""
    try:
        data = request.json
        plan_id = data.get('plan_id')
        actual_start_time = data.get('actual_start_time')  # "21:00"
        actual_end_time = data.get('actual_end_time')      # "22:30"

        if not plan_id or not actual_start_time or not actual_end_time:
            return jsonify({'success': False, 'error': '缺少必要参数'}), 400

        # 计算用时
        start_h, start_m = map(int, actual_start_time.split(':'))
        end_h, end_m = map(int, actual_end_time.split(':'))
        actual_hours = (end_h * 60 + end_m - start_h * 60 - start_m) / 60

        if actual_hours <= 0:
            return jsonify({'success': False, 'error': '结束时间必须晚于起始时间'}), 400

        # 从数据库获取计划详情
        sys.path.insert(0, str(SKILL_PATH))
        from core.db import get_connection

        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            plan = conn.execute('''
                SELECT id, material_title, material_domain, material_url,
                       planned_hours, scheduled_date, time_slot
                FROM plans WHERE id = ?
            ''', (plan_id,)).fetchone()

            if not plan:
                return jsonify({'success': False, 'error': '计划不存在'}), 404

            plan = dict(plan)

        # 更新计划状态
        with get_connection() as conn:
            conn.execute('''
                UPDATE plans
                SET status = 'completed',
                    actual_start_time = ?,
                    actual_end_time = ?,
                    actual_hours = ?
                WHERE id = ?
            ''', (actual_start_time, actual_end_time, actual_hours, plan_id))

        # 更新 Apple Calendar
        try:
            from core.calendar_sync import _update_event
            # 构建 _create_event 期望的 plan_info 格式
            plan_info = {
                'id': plan_id,
                'title': plan['material_title'],
                'domain': plan['material_domain'],
                'url': plan['material_url'],
                'planned_hours': plan['planned_hours'],
                'scheduled_date': plan['scheduled_date'],
                'time_slot': plan['time_slot'],
            }
            _update_event(
                plan_id=plan_id,
                scheduled_date=plan['scheduled_date'],
                new_start_time=actual_start_time,
                new_end_time=actual_end_time,
                plan_info=plan_info
            )
        except Exception as e:
            print(f"Calendar 更新失败: {e}")

        return jsonify({
            'success': True,
            'actual_hours': round(actual_hours, 1)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/achievements', methods=['GET'])
def get_achievements():
    """获取成果数据（统计 + 两个MD的内容）"""
    try:
        # 读取已完成资源
        if OBSIDIAN_PATH.exists():
            content = OBSIDIAN_PATH.read_text(encoding='utf-8')
            materials = parse_md_table(content)
        else:
            materials = []

        # 读取成果记录
        completed_records = []
        if ACHIEVEMENTS_PATH.exists():
            ach_content = ACHIEVEMENTS_PATH.read_text(encoding='utf-8')
            completed_records = _parse_achievements_md(ach_content)

        # 统计
        total = len(materials)
        completed = [m for m in materials if m['progress'] >= 100]
        in_progress = [m for m in materials if 0 < m['progress'] < 100]
        pending = [m for m in materials if m['progress'] == 0]

        # 累计学习时长（从数据库读已完成计划的 actual_hours）
        from core.db import get_connection
        total_hours = 0.0
        with get_connection() as conn:
            row = conn.execute(
                "SELECT SUM(actual_hours) FROM plans WHERE status='completed' AND actual_hours IS NOT NULL"
            ).fetchone()
            total_hours = row[0] or 0.0

        # 领域分布
        domain_count = {}
        for m in completed:
            d = m.get('domain', 'other')
            domain_count[d] = domain_count.get(d, 0) + 1

        return jsonify({
            'success': True,
            'stats': {
                'total': total,
                'completed': len(completed),
                'in_progress': len(in_progress),
                'pending': len(pending),
                'total_hours': round(total_hours, 1),
            },
            'domain_count': domain_count,
            'completed_materials': completed,
            'in_progress_materials': in_progress,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/achievements/save', methods=['POST'])
def save_achievement():
    """保存完成项到学习成果.md"""
    try:
        data = request.json
        title = data.get('title')
        domain = data.get('domain', 'other')
        actual_hours = data.get('actual_hours', 0)
        rating = data.get('rating', '⭐')
        note = data.get('note', '')

        if not title:
            return jsonify({'success': False, 'error': '标题不能为空'}), 400

        from datetime import date
        today = date.today().strftime('%Y-%m-%d')

        # 读取现有成果
        records = []
        if ACHIEVEMENTS_PATH.exists():
            ach_content = ACHIEVEMENTS_PATH.read_text(encoding='utf-8')
            records = _parse_achievements_md(ach_content)

        # 检查是否已存在
        for r in records:
            if r['title'] == title:
                return jsonify({'success': False, 'error': '该成果已存在'}), 409

        # 添加新记录
        records.append({
            'title': title,
            'domain': domain,
            'completed_date': today,
            'actual_hours': actual_hours,
            'rating': rating,
            'note': note,
        })

        # 写回文件
        _write_achievements_md(records)

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _parse_achievements_md(content: str) -> list:
    """解析学习成果.md"""
    records = []
    lines = content.split('\n')
    in_table = False
    header_indices = {}

    for line in lines:
        line = line.strip()
        if '标题' in line and line.startswith('|'):
            in_table = True
            headers = [h.strip() for h in line.split('|')[1:-1]]
            for i, h in enumerate(headers):
                header_indices[h] = i
            continue
        if in_table and not line.startswith('|'):
            break
        if in_table and line.startswith('|') and not line.startswith('|---'):
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) < 2 or not cells[0]:
                continue
            records.append({
                'title': cells[header_indices.get('标题', 0)],
                'domain': cells[header_indices.get('领域', 1)] if len(cells) > 1 else '',
                'completed_date': cells[header_indices.get('完成日期', 2)] if len(cells) > 2 else '',
                'actual_hours': float(cells[header_indices.get('实际用时(h)', 3)]) if len(cells) > 3 and cells[header_indices.get('实际用时(h)', 3)] else 0,
                'rating': cells[header_indices.get('评分', 4)] if len(cells) > 4 else '',
                'note': cells[header_indices.get('备注', 5)] if len(cells) > 5 else '',
            })
    return records


def _write_achievements_md(records: list):
    """写入学习成果.md"""
    import datetime
    total_hours = sum(r.get('actual_hours', 0) for r in records)

    lines = [
        "# 学习成果",
        "",
        "> 记录每一份学习的收获与完成",
        "",
        "## 已完成项目",
        "",
        "| 标题 | 领域 | 完成日期 | 实际用时(h) | 评分 | 备注 |",
        "|------|------|----------|-------------|------|------|",
    ]

    for r in records:
        lines.append(f"| {r['title']} | {r['domain']} | {r['completed_date']} | {r['actual_hours']} | {r['rating']} | {r['note']} |")

    lines.extend([
        "",
        "## 统计",
        "",
        f"- 总完成数: {len(records)}",
        f"- 累计学习时长: {total_hours}h",
        f"- 更新时间: {datetime.datetime.now().strftime('%Y-%m-%d')}",
        "",
        "## 说明",
        "",
        "- 直接编辑上方表格添加已完成项目",
        "- 评分: ⭐ 到 ⭐⭐⭐⭐⭐",
        "- 实际用时可从数据库自动填充",
    ])

    ACHIEVEMENTS_PATH.write_text("\n".join(lines), encoding='utf-8')


if __name__ == '__main__':
    print("📚 学习助手 - 极简文件服务")
    print(f"📂 Obsidian 路径: {OBSIDIAN_PATH}")
    print(f"📊 成果文件: {ACHIEVEMENTS_PATH}")
    print(f"🌐 http://localhost:5001")
    print("\n可用端点:")
    print("  GET  /api/resources           - 获取所有资源")
    print("  POST /api/resources/update    - 更新资源")
    print("  POST /api/resources/delete    - 删除资源")
    print("  GET  /api/plans              - 获取本周计划")
    print("  POST /api/plans/generate     - 生成计划")
    print("  POST /api/plans/clear        - 清除计划")
    print("  GET  /api/achievements       - 获取成果数据")
    print("  POST /api/achievements/save  - 保存成果")
    print()

    app.run(host='0.0.0.0', port=5001, debug=True)
