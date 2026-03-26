"""
推荐引擎模块 - 扫描和推荐学习资源
"""
import sys
import random
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional

# 处理相对导入
try:
    from .db import add_recommendation, get_pending_recommendations
    from ..config import RECOMMENDATION_SOURCES, DOMAIN_NAMES
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from core.db import add_recommendation, get_pending_recommendations
    from config import RECOMMENDATION_SOURCES, DOMAIN_NAMES


def scan_all_sources() -> List[Dict]:
    """
    扫描所有推荐源，返回发现的推荐资源

    当前提供精选资源列表（已验证的链接），而非随机生成
    """
    print("正在扫描推荐源...")

    # 精选资源列表 - 已验证的官方链接
    curated_resources = [
        # AI开发
        {
            'title': 'Claude官方文档 - API使用指南',
            'url': 'https://docs.anthropic.com/en/docs/',
            'source_type': 'documentation',
            'domain': 'work-ai',
            'reason': 'Claude官方文档，与你正在学习的Anthropic Skill直接相关'
        },
        {
            'title': 'LangChain官方文档',
            'url': 'https://python.langchain.com/docs/introduction/',
            'source_type': 'documentation',
            'domain': 'work-ai',
            'reason': '构建AI应用的完整框架文档'
        },
        {
            'title': 'Hugging Face Transformers文档',
            'url': 'https://huggingface.co/docs/transformers/index',
            'source_type': 'documentation',
            'domain': 'work-ai',
            'reason': '大模型应用开发必备'
        },
        # DS/ML
        {
            'title': 'Kaggle Competitions主页',
            'url': 'https://www.kaggle.com/competitions',
            'source_type': 'competition',
            'domain': 'dsml',
            'reason': '实战练习机器学习的最佳平台'
        },
        {
            'title': '吴恩达深度学习课程 (Coursera)',
            'url': 'https://www.coursera.org/specializations/deep-learning',
            'source_type': 'course',
            'domain': 'dsml',
            'reason': '系统学习深度学习的经典课程'
        },
        {
            'title': 'Fast.ai实用深度学习',
            'url': 'https://www.fast.ai/',
            'source_type': 'course',
            'domain': 'dsml',
            'reason': '以实践为导向的深度学习课程'
        },
        {
            'title': 'Pytorch官方教程',
            'url': 'https://pytorch.org/tutorials/',
            'source_type': 'documentation',
            'domain': 'dsml',
            'reason': '深度学习框架官方教程'
        },
        # Quant
        {
            'title': 'QuantConnect算法交易平台',
            'url': 'https://www.quantconnect.com/',
            'source_type': 'tool',
            'domain': 'quant',
            'reason': '量化策略回测和实盘平台'
        },
        {
            'title': 'arXiv量化金融 (q-fin)',
            'url': 'https://arxiv.org/list/q-fin/recent',
            'source_type': 'paper',
            'domain': 'quant',
            'reason': '最新量化金融研究论文'
        },
        {
            'title': 'Investopedia量化交易教程',
            'url': 'https://www.investopedia.com/quantitative-trading-5114683',
            'source_type': 'article',
            'domain': 'quant',
            'reason': '量化交易基础概念学习'
        },
        # 哲学
        {
            'title': '斯坦福哲学百科',
            'url': 'https://plato.stanford.edu/',
            'source_type': 'reference',
            'domain': 'philosophy',
            'reason': '权威的哲学概念参考'
        },
        {
            'title': 'PhilPapers哲学论文库',
            'url': 'https://philpapers.org/',
            'source_type': 'paper',
            'domain': 'philosophy',
            'reason': '当代哲学研究论文索引'
        },
        # 物理
        {
            'title': '费曼物理学讲义 (在线版)',
            'url': 'https://www.feynmanlectures.caltech.edu/',
            'source_type': 'book',
            'domain': 'physics',
            'reason': '物理学经典教材'
        },
        {
            'title': '3Blue1Brown物理系列',
            'url': 'https://www.youtube.com/c/3blue1brown',
            'source_type': 'video',
            'domain': 'physics',
            'reason': '直观的物理数学可视化讲解'
        }
    ]

    # 根据用户画像选择最相关的3-5个推荐
    import random
    # 简单随机选择（未来可以根据用户画像智能选择）
    num_recommendations = random.randint(3, 5)
    discoveries = random.sample(curated_resources, k=min(num_recommendations, len(curated_resources)))

    # 保存到数据库
    added_count = 0
    for item in discoveries:
        try:
            add_recommendation(
                title=item['title'],
                url=item['url'],
                source_type=item['source_type'],
                domain=item['domain'],
                reason=item['reason']
            )
            added_count += 1
        except Exception as e:
            print(f"  添加推荐失败: {e}")

    print(f"✓ 发现 {added_count} 个新推荐")
    return discoveries


def get_recommendations_for_display() -> List[Dict]:
    """获取待审批推荐用于显示"""
    return get_pending_recommendations()


def approve_and_add_to_plan(rec_id: int, week_start: Optional[date] = None) -> bool:
    """
    审批推荐并添加到学习计划

    Args:
        rec_id: 推荐ID
        week_start: 计划周开始日期，默认本周

    Returns:
        是否成功
    """
    from .db import get_connection, approve_recommendation as db_approve
    from .planner import create_plan

    if week_start is None:
        week_start = date.today() - (date.today().weekday())

    # 获取推荐信息
    with get_connection() as conn:
        cursor = conn.execute(
            'SELECT * FROM recommendations WHERE id = ? AND status = ?',
            (rec_id, 'pending')
        )
        rec = cursor.fetchone()

    if not rec:
        print(f"❌ 推荐 #{rec_id} 不存在或已处理")
        return False

    # 解析推荐信息
    rec_dict = dict(zip([c[0] for c in cursor.description], rec))

    # 添加到materials
    from .db import add_material
    from .priority import calculate_all_priorities

    material_id = add_material(
        title=rec_dict['title'],
        url=rec_dict['url'],
        source_type=rec_dict['source_type'],
        domain=rec_dict['domain'],
        estimated_hours=2.0  # 默认预估
    )

    # 更新优先级
    calculate_all_priorities()

    # 标记推荐为已批准
    db_approve(rec_id)

    print(f"✓ 已添加 '{rec_dict['title']}' 到学习资料")

    # 询问是否立即安排到计划
    print(f"  建议: 运行 /learn-plan 重新生成计划以包含此资料")

    return True
