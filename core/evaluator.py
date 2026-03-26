"""
学习评估模块
多维度分析学习效果，优化后续计划
"""
import math
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# 处理相对导入
try:
    from .db import get_connection, get_user_profile, update_learning_stats
    from ..config import DOMAIN_NAMES
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from core.db import get_connection, get_user_profile, update_learning_stats
    from config import DOMAIN_NAMES


def evaluate_session(plan_id: int, actual_hours: float, quality_rating: int) -> Dict:
    """
    评估单次学习会话

    返回评估报告
    """
    with get_connection() as conn:
        # 获取计划和资料信息
        cursor = conn.execute('''
            SELECT p.*, m.title, m.domain, m.estimated_hours
            FROM plans p
            JOIN materials m ON p.material_id = m.id
            WHERE p.id = ?
        ''', (plan_id,))
        plan = cursor.fetchone()

    if not plan:
        return {"error": "计划不存在"}

    # 计算各项指标
    metrics = {}

    # 1. 时间准确度
    planned_hours = plan['planned_hours']
    time_accuracy = planned_hours / actual_hours if actual_hours > 0 else 0
    metrics['time_accuracy'] = min(time_accuracy, 2.0)  # 封顶2倍

    # 2. 时间偏差率
    time_deviation = abs(actual_hours - planned_hours) / planned_hours if planned_hours > 0 else 0
    metrics['time_deviation_pct'] = round(time_deviation * 100, 1)

    # 3. 质量评分（用户自评）
    metrics['quality_rating'] = quality_rating

    # 4. 效率指数
    efficiency = (quality_rating / 5.0) * min(time_accuracy, 1.0)
    metrics['efficiency_index'] = round(efficiency, 2)

    # 5. 更新用户画像
    domain = plan['domain']
    time_ratio = actual_hours / plan['estimated_hours'] if plan['estimated_hours'] > 0 else 1.0
    update_learning_stats(domain, actual_hours, time_ratio)

    return {
        'material_title': plan['title'],
        'domain': DOMAIN_NAMES.get(domain, domain),
        'planned_hours': planned_hours,
        'actual_hours': actual_hours,
        'metrics': metrics,
        'feedback': _generate_feedback(metrics)
    }


def _generate_feedback(metrics: Dict) -> str:
    """生成反馈建议"""
    feedback = []

    if metrics['time_deviation_pct'] > 50:
        feedback.append("预估时间偏差较大，建议调整该类型任务的预估系数")

    if metrics['quality_rating'] >= 4:
        feedback.append("学习质量很高！保持这个节奏")
    elif metrics['quality_rating'] <= 2:
        feedback.append("学习质量偏低，建议下次选择更合适的时间段或调整任务难度")

    if metrics['efficiency_index'] > 0.8:
        feedback.append("效率优秀")
    elif metrics['efficiency_index'] < 0.5:
        feedback.append("效率有待提升，建议检查 distractions")

    return " | ".join(feedback) if feedback else "表现正常"


def get_weekly_report(week_start: Optional[date] = None) -> Dict:
    """
    生成周报
    """
    if week_start is None:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)

    with get_connection() as conn:
        # 总体统计
        cursor = conn.execute('''
            SELECT
                COUNT(*) as session_count,
                SUM(actual_hours) as total_hours,
                AVG(quality_rating) as avg_quality,
                AVG(completion_rate) as avg_completion
            FROM sessions
            WHERE actual_start >= ? AND actual_start < ?
        ''', (week_start, week_end))
        overall = cursor.fetchone()

        # 各领域分布
        cursor = conn.execute('''
            SELECT
                m.domain,
                COUNT(*) as count,
                SUM(s.actual_hours) as hours,
                AVG(s.quality_rating) as quality
            FROM sessions s
            JOIN materials m ON s.material_id = m.id
            WHERE s.actual_start >= ? AND s.actual_start < ?
            GROUP BY m.domain
        ''', (week_start, week_end))
        by_domain = cursor.fetchall()

        # 完成情况统计
        cursor = conn.execute('''
            SELECT
                COUNT(*) as completed_plans,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as done
            FROM plans
            WHERE week_start = ?
        ''', (week_start,))
        completion = cursor.fetchone()

    return {
        'week': f"{week_start} ~ {week_end}",
        'overall': {
            'sessions': overall['session_count'] if overall else 0,
            'total_hours': round(overall['total_hours'], 1) if overall else 0,
            'avg_quality': round(overall['avg_quality'], 1) if overall and overall['avg_quality'] else 0,
            'plan_completion_rate': round(completion['done'] / completion['completed_plans'] * 100, 1) if completion and completion['completed_plans'] else 0
        },
        'by_domain': [
            {
                'domain': DOMAIN_NAMES.get(row['domain'], row['domain']),
                'sessions': row['count'],
                'hours': round(row['hours'], 1),
                'quality': round(row['quality'], 1) if row['quality'] else 0
            }
            for row in (by_domain or [])
        ]
    }


def analyze_learning_patterns() -> Dict:
    """
    分析长期学习模式
    """
    with get_connection() as conn:
        # 最佳学习时段分析
        cursor = conn.execute('''
            SELECT
                strftime('%H', actual_start) as hour,
                AVG(quality_rating) as avg_quality,
                COUNT(*) as count
            FROM sessions
            GROUP BY hour
            HAVING count >= 2
            ORDER BY avg_quality DESC
        ''')
        hour_patterns = cursor.fetchall()

        # 最佳领域分析
        cursor = conn.execute('''
            SELECT
                m.domain,
                AVG(s.quality_rating) as avg_quality,
                AVG(s.actual_hours / p.planned_hours) as time_accuracy,
                COUNT(*) as count
            FROM sessions s
            JOIN materials m ON s.material_id = m.id
            JOIN plans p ON s.plan_id = p.id
            GROUP BY m.domain
            HAVING count >= 2
        ''')
        domain_patterns = cursor.fetchall()

    return {
        'best_hours': [f"{row['hour']}:00" for row in (hour_patterns or [])[:3]],
        'best_domains': [
            {
                'domain': DOMAIN_NAMES.get(row['domain'], row['domain']),
                'avg_quality': round(row['avg_quality'], 1),
                'time_accuracy': round(row['time_accuracy'], 2)
            }
            for row in (domain_patterns or [])
        ]
    }


def export_stats_json() -> str:
    """导出统计数据为JSON"""
    import json

    with get_connection() as conn:
        # 所有统计
        stats = {}

        # 资料统计
        cursor = conn.execute('''
            SELECT
                status,
                COUNT(*) as count,
                SUM(estimated_hours) as hours
            FROM materials
            GROUP BY status
        ''')
        stats['materials'] = {row['status']: {'count': row['count'], 'hours': row['hours']} for row in cursor.fetchall()}

        # 领域分布
        cursor = conn.execute('''
            SELECT domain, COUNT(*) as count, SUM(actual_hours) as hours
            FROM materials
            GROUP BY domain
        ''')
        stats['by_domain'] = {row['domain']: {'count': row['count'], 'hours': row['hours']} for row in cursor.fetchall()}

        # 最近4周趋势
        cursor = conn.execute('''
            SELECT
                strftime('%Y-%W', actual_start) as week,
                COUNT(*) as sessions,
                SUM(actual_hours) as hours
            FROM sessions
            WHERE actual_start >= date('now', '-28 days')
            GROUP BY week
            ORDER BY week DESC
        ''')
        stats['weekly_trend'] = [{"week": row['week'], "sessions": row['sessions'], "hours": row['hours']} for row in cursor.fetchall()]

    return json.dumps(stats, indent=2, ensure_ascii=False)
