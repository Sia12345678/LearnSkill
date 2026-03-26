"""
学习助手 API 服务器 - 为Dashboard提供后端服务
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
from pathlib import Path
import sys
import sqlite3

# 添加core目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from core.obsidian_sync import add_material_to_obsidian, import_from_obsidian, sync_progress_to_obsidian, get_note_path, delete_resource_from_obsidian
from core.db import add_material, update_material_progress, get_materials
from core.db import add_to_progress, get_progress_list, update_progress as update_resource_progress, remove_from_progress, is_in_progress
from core.calendar_sync import sync_session_to_calendar

app = Flask(__name__)
CORS(app)  # 允许跨域请求


@app.route('/api/materials', methods=['GET'])
def get_materials_list():
    """获取学习资料列表（从Obsidian导入）"""
    try:
        # 先导入Obsidian资料到数据库
        materials = import_from_obsidian()

        # 将新资料添加到数据库
        for m in materials:
            existing = get_materials(title=m['title'])
            if not existing:
                add_material(
                    title=m['title'],
                    url=m.get('url'),
                    source_type='obsidian',
                    domain=m.get('domain', 'work-ai'),
                    estimated_hours=m.get('estimated_hours', 2.0),
                    priority_score=0
                )

        return jsonify({'success': True, 'materials': materials})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/materials', methods=['POST'])
def create_material():
    """添加新资料（直接写入Obsidian）"""
    data = request.json
    title = data.get('title', '').strip()
    url = data.get('url', '').strip() or None
    domain = data.get('domain', 'work-ai')
    hours = float(data.get('hours', 2.0))

    if not title:
        return jsonify({'success': False, 'error': '标题不能为空'}), 400

    try:
        # 1. 先写入Obsidian（主数据源）
        success = add_material_to_obsidian(title, url, domain, hours)
        if not success:
            return jsonify({'success': False, 'error': '写入Obsidian失败'}), 500

        # 2. 同时添加到本地数据库（缓存）
        material_id = add_material(
            title=title,
            url=url,
            source_type='obsidian',
            domain=domain,
            estimated_hours=hours
        )

        return jsonify({
            'success': True,
            'material': {
                'id': material_id,
                'title': title,
                'url': url,
                'domain': domain,
                'estimated_hours': hours
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/materials/<int:material_id>/progress', methods=['PUT'])
def update_progress(material_id):
    """更新资料进度（同步到Obsidian和Calendar）"""
    data = request.json
    progress = int(data.get('progress', 0))
    actual_hours = float(data.get('actual_hours', 0))
    title = data.get('title', '')

    try:
        # 1. 更新Obsidian
        if title:
            sync_progress_to_obsidian(title, progress, actual_hours)

        # 2. 更新数据库
        update_material_progress(material_id, progress, actual_hours)

        # 3. 如果完成，同步到Calendar
        if progress >= 100 and data.get('sync_calendar'):
            sync_session_to_calendar(
                material_id=material_id,
                actual_start=data.get('start_time'),
                actual_end=data.get('end_time'),
                actual_hours=actual_hours,
                quality_rating=data.get('quality_rating', 3)
            )

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/calendar/sync', methods=['POST'])
def sync_to_calendar():
    """同步学习记录到Apple Calendar"""
    data = request.json

    try:
        success = sync_session_to_calendar(
            material_id=data.get('material_id'),
            actual_start=data.get('start_time'),
            actual_end=data.get('end_time'),
            actual_hours=data.get('hours'),
            quality_rating=data.get('quality_rating', 3)
        )

        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Calendar同步失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/sync/obsidian', methods=['POST'])
def sync_obsidian():
    """手动触发Obsidian双向同步"""
    try:
        from core.obsidian_sync import bidirectional_sync
        new_materials, updated_materials = bidirectional_sync()
        return jsonify({
            'success': True,
            'new': len(new_materials),
            'updated': len(updated_materials)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# === 资源总览页 API ===

@app.route('/api/resources', methods=['GET'])
def get_resources():
    """获取所有资源（从Obsidian读取）"""
    try:
        materials = import_from_obsidian()

        # 检查每个资源是否已在进程中
        from core.db import _make_resource_key
        for m in materials:
            resource_key = _make_resource_key(m['title'], m.get('domain', 'work-ai'))
            m['in_progress'] = is_in_progress(resource_key)

        # 按领域分组
        domains = {}
        for m in materials:
            domain = m.get('domain', 'work-ai')
            if domain not in domains:
                domains[domain] = []
            domains[domain].append(m)

        return jsonify({
            'success': True,
            'resources': materials,
            'domains': domains
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/progress', methods=['GET'])
def get_progress():
    """获取所有进程记录"""
    try:
        progress_list = get_progress_list()
        return jsonify({
            'success': True,
            'progress': progress_list
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/progress/add', methods=['POST'])
def add_to_progress_api():
    """将资源加入进程记录"""
    data = request.json
    title = data.get('title', '').strip()
    domain = data.get('domain', 'work-ai')
    url = data.get('url')
    estimated_hours = float(data.get('estimated_hours', 2.0))

    if not title:
        return jsonify({'success': False, 'error': '标题不能为空'}), 400

    try:
        # 检查是否已在进程中
        from core.db import _make_resource_key
        resource_key = _make_resource_key(title, domain)
        if is_in_progress(resource_key):
            return jsonify({'success': False, 'error': '资源已在进程记录中'}), 400

        progress_id = add_to_progress(title, domain, url, estimated_hours)
        return jsonify({
            'success': True,
            'id': progress_id,
            'resource_key': resource_key
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/progress/update', methods=['POST'])
def update_progress_api():
    """更新资源进度"""
    data = request.json
    resource_key = data.get('resource_key')
    progress = int(data.get('progress', 0))
    actual_hours = data.get('actual_hours')

    if not resource_key:
        return jsonify({'success': False, 'error': '资源标识不能为空'}), 400

    try:
        update_resource_progress(resource_key, progress, actual_hours)

        # 同步更新到 Obsidian
        # 解析 resource_key 获取标题
        title = resource_key.split('|')[0] if '|' in resource_key else resource_key
        if title and actual_hours is not None:
            sync_progress_to_obsidian(title, progress, actual_hours)
        elif title:
            # 如果没有提供实际时间，也尝试同步
            current = get_progress_list()
            for p in current:
                if p.get('resource_key') == resource_key:
                    sync_progress_to_obsidian(title, progress, p.get('actual_hours', 0))
                    break

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/progress/remove', methods=['POST'])
def remove_from_progress_api():
    """从进程记录中移除"""
    data = request.json
    resource_key = data.get('resource_key')

    if not resource_key:
        return jsonify({'success': False, 'error': '资源标识不能为空'}), 400

    try:
        remove_from_progress(resource_key)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# === 学习评估 API ===

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取学习统计数据"""
    try:
        from core.db import get_connection
        from datetime import date, timedelta

        with get_connection() as conn:
            # 总体统计
            row = conn.execute('''
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(actual_hours) as total_hours
                FROM materials
            ''').fetchone()

            # 本周统计
            week_start = date.today() - timedelta(days=date.today().weekday())
            week_row = conn.execute('''
                SELECT COALESCE(SUM(actual_hours), 0) as hours
                FROM sessions
                WHERE actual_start >= ?
            ''', (week_start,)).fetchone()

        return jsonify({
            'success': True,
            'stats': {
                'total': row[0] if row else 0,
                'completed': row[1] if row else 0,
                'total_hours': row[2] if row and row[2] else 0,
                'week_hours': week_row[0] if week_row else 0
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """获取学习历史记录"""
    try:
        from core.db import get_connection

        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute('''
                SELECT s.*, m.title
                FROM sessions s
                JOIN materials m ON s.material_id = m.id
                ORDER BY s.actual_start DESC
                LIMIT 50
            ''').fetchall()

        sessions = [dict(row) for row in rows]
        return jsonify({
            'success': True,
            'sessions': sessions
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/resources/delete', methods=['POST'])
def delete_resource():
    """从 Obsidian 删除资源"""
    data = request.json
    title = data.get('title', '').strip()
    domain = data.get('domain', 'work-ai')

    if not title:
        return jsonify({'success': False, 'error': '标题不能为空'}), 400

    try:
        # 从 Obsidian 删除
        success = delete_resource_from_obsidian(title, domain)
        if success:
            # 同时从进程记录中移除（如果存在）
            from core.db import _make_resource_key
            resource_key = _make_resource_key(title, domain)
            remove_from_progress(resource_key)

            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '删除失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    print("🚀 学习助手API服务器启动...")
    print("📍 http://localhost:5000")
    print("\n可用的端点:")
    print("  GET  /api/materials          - 获取学习资料")
    print("  POST /api/materials          - 添加新资料（写入Obsidian）")
    print("  PUT  /api/materials/<id>/progress - 更新进度")
    print("  POST /api/calendar/sync      - 同步到Calendar")
    print("  POST /api/sync/obsidian      - 同步Obsidian")
    print("  GET  /api/resources          - 获取所有资源（从Obsidian）")
    print("  GET  /api/progress           - 获取进程记录")
    print("  POST /api/progress/add       - 加入进程记录")
    print("  POST /api/progress/update    - 更新进度")
    print("  POST /api/progress/remove    - 移除进程记录")
    print()

    app.run(host='0.0.0.0', port=5001, debug=True)
