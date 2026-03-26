"""
优先级评估算法模块
多维度评分系统
"""
import math
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Tuple, Dict

# 处理相对导入
try:
    from .db import get_connection, get_user_profile
    from ..config import PRIORITY_WEIGHTS, DOMAIN_NAMES
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from core.db import get_connection, get_user_profile
    from config import PRIORITY_WEIGHTS, DOMAIN_NAMES


def calculate_all_priorities() -> List[Tuple[int, float]]:
    """
    计算所有待学习资料的优先级分数
    返回: [(material_id, priority_score), ...]
    """
    with get_connection() as conn:
        cursor = conn.execute('''
            SELECT id, title, domain, estimated_hours, created_at, progress
            FROM materials
            WHERE status IN ('pending', 'in_progress')
        ''')
        materials = cursor.fetchall()

    user_profile = get_user_profile()
    recent_domains = get_recent_domains(days=7)

    results = []
    for material in materials:
        score = calculate_single_priority(
            material=material,
            user_profile=user_profile.get(material[2], {}),
            recent_domains=recent_domains
        )
        results.append((material[0], round(score, 2)))

    return sorted(results, key=lambda x: x[1], reverse=True)


def calculate_single_priority(material: Tuple, user_profile: Dict,
                               recent_domains: List[str]) -> float:
    """
    计算单个资料的优先级分数

    material: (id, title, domain, estimated_hours, created_at, progress)
    """
    _, title, domain, estimated_hours, created_at, progress = material

    scores = {}

    # 1. 技能树匹配度 (25%)
    # 熟练度越低，学习价值越高（工作技能优先）
    proficiency = user_profile.get('proficiency', 5)
    if domain == 'work-ai':
        scores['skill_match'] = (11 - proficiency) * 1.5  # 工作技能加权
    else:
        scores['skill_match'] = 11 - proficiency

    # 2. 投入产出比 (20%)
    # 预估时间适中（2-10小时）最优，太长的不利于快速迭代
    if estimated_hours <= 2:
        scores['cost_benefit'] = 8
    elif estimated_hours <= 10:
        scores['cost_benefit'] = 10
    elif estimated_hours <= 30:
        scores['cost_benefit'] = 6
    else:
        scores['cost_benefit'] = 3  # 太长的资料降低优先级

    # 3. 时效性 (15%)
    # 新添加的资料有轻微加分（避免永远积压）
    created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00')) if isinstance(created_at, str) else datetime.now()
    days_old = (datetime.now() - created_date).days
    if days_old < 7:
        scores['timeliness'] = 9
    elif days_old < 30:
        scores['timeliness'] = 7
    else:
        scores['timeliness'] = 5

    # 4. 用户偏好 (15%)
    # 基于历史成功率
    avg_ratio = user_profile.get('avg_time_ratio', 1.0)
    completed = user_profile.get('completed_count', 0)
    if completed > 0:
        # 完成多的领域说明更有信心
        scores['preference'] = min(10, 5 + completed * 0.5)
    else:
        scores['preference'] = 5

    # 5. 领域轮换 (15%)
    # 最近学过的领域降低优先级，鼓励多样化
    if domain in recent_domains:
        # 如果最近学过，大幅降低优先级
        recent_count = recent_domains.count(domain)
        scores['rotation'] = max(2, 8 - recent_count * 2)
    else:
        scores['rotation'] = 10  # 好久没学，加分

    # 6. 周末适配度 (10%)
    # 周末适合技术类，周内适合阅读类
    weekend_domains = ['work-ai', 'dsml', 'quant', 'physics']
    if domain in weekend_domains:
        scores['weekend_fit'] = 10
    else:
        scores['weekend_fit'] = 6

    # 加权计算总分
    total_score = 0
    for key, weight in PRIORITY_WEIGHTS.items():
        total_score += scores.get(key, 5) * weight

    # 进度调整：已经开始的给予小幅加成（鼓励完成）
    if progress and progress > 0:
        total_score *= (1 + progress / 200)  # 最多+50%

    return total_score


def get_recent_domains(days: int = 7) -> List[str]:
    """获取最近学习的领域"""
    with get_connection() as conn:
        cursor = conn.execute('''
            SELECT m.domain
            FROM sessions s
            JOIN materials m ON s.material_id = m.id
            WHERE s.actual_start >= date('now', ?)
            ORDER BY s.actual_start DESC
        ''', (f'-{days} days',))
        return [row[0] for row in cursor.fetchall()]


def get_priority_explanation(material_id: int) -> str:
    """获取优先级评分的详细解释"""
    # 重新计算并返回各维度得分
    with get_connection() as conn:
        cursor = conn.execute('''
            SELECT id, title, domain, estimated_hours, created_at, progress
            FROM materials WHERE id = ?
        ''', (material_id,))
        material = cursor.fetchone()

    if not material:
        return "未找到资料"

    user_profile = get_user_profile().get(material[2], {})
    recent_domains = get_recent_domains(days=7)

    # 重新计算获取各维度分数
    scores = {}
    _, title, domain, estimated_hours, created_at, progress = material

    proficiency = user_profile.get('proficiency', 5)
    scores['skill_match'] = (11 - proficiency) * (1.5 if domain == 'work-ai' else 1)

    if estimated_hours <= 2:
        scores['cost_benefit'] = 8
    elif estimated_hours <= 10:
        scores['cost_benefit'] = 10
    elif estimated_hours <= 30:
        scores['cost_benefit'] = 6
    else:
        scores['cost_benefit'] = 3

    created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00')) if isinstance(created_at, str) else datetime.now()
    days_old = (datetime.now() - created_date).days
    scores['timeliness'] = 9 if days_old < 7 else (7 if days_old < 30 else 5)

    completed = user_profile.get('completed_count', 0)
    scores['preference'] = min(10, 5 + completed * 0.5) if completed > 0 else 5

    recent_count = recent_domains.count(domain)
    scores['rotation'] = max(2, 8 - recent_count * 2) if domain in recent_domains else 10

    weekend_domains = ['work-ai', 'dsml', 'quant', 'physics']
    scores['weekend_fit'] = 10 if domain in weekend_domains else 6

    # 生成解释
    lines = [f"优先级分析: {title}", "=" * 40]
    lines.append(f"技能匹配度: {scores['skill_match']:.1f}/10 (熟练度{proficiency})")
    lines.append(f"投入产出比: {scores['cost_benefit']:.1f}/10 (预估{estimated_hours}小时)")
    lines.append(f"时效性:     {scores['timeliness']:.1f}/10 (创建{days_old}天前)")
    lines.append(f"用户偏好:   {scores['preference']:.1f}/10 (已完成{completed}项)")
    lines.append(f"领域轮换:   {scores['rotation']:.1f}/10 (近7天学习{recent_count}次)")
    lines.append(f"周末适配:   {scores['weekend_fit']:.1f}/10")

    return '\n'.join(lines)


def update_priority_scores():
    """批量更新所有资料的优先级分数"""
    priorities = calculate_all_priorities()
    with get_connection() as conn:
        for material_id, score in priorities:
            conn.execute('''
                UPDATE materials SET priority_score = ? WHERE id = ?
            ''', (score, material_id))
        conn.commit()
