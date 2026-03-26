"""
测验生成模块 - 基于学习内容生成测验题目
"""
import sys
from pathlib import Path
from typing import List, Dict, Optional

# 处理相对导入
try:
    from ..config import DOMAIN_NAMES
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import DOMAIN_NAMES


def generate_quiz(material_id: int, content: str = "") -> List[Dict]:
    """
    基于学习资料生成测验

    Args:
        material_id: 资料ID
        content: 爬取的内容文本（可选，如果为空则基于标题/URL生成）

    Returns:
        测验题目列表
    """
    from .db import get_connection

    # 获取资料信息
    with get_connection() as conn:
        cursor = conn.execute('SELECT * FROM materials WHERE id = ?', (material_id,))
        material = cursor.fetchone()

    if not material:
        return []

    material_dict = dict(zip([c[0] for c in cursor.description], material))
    domain = material_dict['domain']
    title = material_dict['title']
    source_type = material_dict['source_type']

    # 根据领域和类型生成不同测验
    if domain == 'literature':
        # 文学不出题
        return []
    elif domain == 'philosophy':
        # 哲学出思考题
        return _generate_philosophy_questions(title, content)
    elif domain in ['work-ai', 'dsml', 'quant']:
        # 技术类出代码题和应用题
        return _generate_tech_quiz(title, content, source_type)
    else:
        # 默认通用测验
        return _generate_general_quiz(title, content)


def _generate_philosophy_questions(title: str, content: str) -> List[Dict]:
    """生成哲学思考题"""
    # 基于标题识别哲学主题
    questions = []

    # 格式化标题，避免重复书名号
    formatted_title = title if title.startswith('《') and title.endswith('》') else f'《{title}》'

    # 核心概念理解
    questions.append({
        'type': 'short_answer',
        'question': f'{formatted_title}的核心论点是什么？请用你自己的话概括。',
        'difficulty': 'medium',
        'hint': '思考作者试图解决什么根本问题'
    })

    # 论证分析
    questions.append({
        'type': 'essay',
        'question': f'作者如何论证其观点？请梳理主要论证步骤并评价其有效性。',
        'difficulty': 'hard',
        'hint': '关注前提、推理过程和结论'
    })

    # 批判性思考
    questions.append({
        'type': 'essay',
        'question': f'你同意{formatted_title}的观点吗？请提出至少一个支持理由和一个反对理由。',
        'difficulty': 'hard',
        'hint': '尝试站在对立面思考'
    })

    # 现实意义
    questions.append({
        'type': 'short_answer',
        'question': f'这本书的思想对当代社会/你的生活有什么启示？',
        'difficulty': 'medium',
        'hint': '联系实际应用场景'
    })

    return questions


def _generate_tech_quiz(title: str, content: str, source_type: str) -> List[Dict]:
    """生成技术类测验"""
    questions = []

    # 概念理解题
    questions.append({
        'type': 'short_answer',
        'question': f'{title}的核心概念是什么？请解释其作用和适用场景。',
        'difficulty': 'easy',
        'hint': '从基础定义出发'
    })

    # 代码实践题（如果有足够内容）
    if content and len(content) > 500:
        # 尝试从内容中提取代码示例
        questions.append({
            'type': 'coding',
            'question': f'根据学习内容，完成以下代码：\n\n# TODO: 实现{title}的核心功能\n\ndef main():\n    # 你的代码\n    pass\n\nif __name__ == "__main__":\n    main()',
            'difficulty': 'medium',
            'hint': '参考官方文档的Quick Start部分'
        })
    else:
        # 简化的代码理解题
        questions.append({
            'type': 'coding',
            'question': f'写一个最小化的代码示例，展示{title}的基本用法。',
            'difficulty': 'medium',
            'hint': '从Hello World级别开始'
        })

    # 应用场景题
    questions.append({
        'type': 'scenario',
        'question': f'在什么场景下你会选择使用{title}？请描述一个具体的使用案例。',
        'difficulty': 'medium',
        'hint': '考虑实际工作中遇到的问题'
    })

    # 进阶题
    questions.append({
        'type': 'coding',
        'question': f'使用{title}实现一个小项目（如：命令行工具、数据处理脚本、简单Web应用等），提交代码和README。',
        'difficulty': 'hard',
        'hint': '项目规模控制在4小时内完成'
    })

    return questions


def _generate_general_quiz(title: str, content: str) -> List[Dict]:
    """生成通用测验"""
    return [
        {
            'type': 'short_answer',
            'question': f'《{title}》的主要内容是什么？',
            'difficulty': 'easy',
            'hint': '列出3-5个要点'
        },
        {
            'type': 'short_answer',
            'question': f'你从中学到了什么最重要的概念/技能？',
            'difficulty': 'medium',
            'hint': '思考对你最有价值的部分'
        },
        {
            'type': 'essay',
            'question': f'如何应用《{title}》的知识到实践中？',
            'difficulty': 'hard',
            'hint': '制定一个具体的行动计划'
        }
    ]


def generate_stages(material_id: int) -> List[Dict]:
    """
    为学习资料生成阶段性学习计划

    返回每个阶段的目标、时长、检查点和测验
    """
    from .db import get_connection

    with get_connection() as conn:
        cursor = conn.execute('SELECT * FROM materials WHERE id = ?', (material_id,))
        material = cursor.fetchone()

    if not material:
        return []

    material_dict = dict(zip([c[0] for c in cursor.description], material))
    domain = material_dict['domain']
    source_type = material_dict['source_type']
    estimated_hours = material_dict['estimated_hours'] or 2

    # 根据类型定义阶段
    stages = []

    if source_type == 'video':
        stages = [
            {
                'name': '概念理解',
                'progress_range': (0, 30),
                'hours': estimated_hours * 0.3,
                'goal': '理解核心概念，能复述主要内容',
                'tasks': ['观看前30%视频', '记录关键概念', '画出知识结构图'],
                'checkpoint': '能向他人解释这个技术是做什么的'
            },
            {
                'name': '动手实践',
                'progress_range': (30, 70),
                'hours': estimated_hours * 0.4,
                'goal': '完成示例代码，解决基础问题',
                'tasks': ['跟着视频完成示例', '尝试修改参数看效果', '记录遇到的问题'],
                'checkpoint': '能独立完成教程中的示例'
            },
            {
                'name': '综合应用',
                'progress_range': (70, 100),
                'hours': estimated_hours * 0.3,
                'goal': '完成独立项目，解决实际问题',
                'tasks': ['设计一个小项目', '独立完成开发', '写学习总结'],
                'checkpoint': '不借助教程完成一个真实需求'
            }
        ]
    elif source_type == 'book':
        stages = [
            {
                'name': '通读理解',
                'progress_range': (0, 40),
                'hours': estimated_hours * 0.4,
                'goal': '理解书籍整体框架和核心论点',
                'tasks': ['快速阅读全书', '每章写一句话摘要', '标记不懂的地方'],
                'checkpoint': '能说出这本书在讲什么'
            },
            {
                'name': '深入思考',
                'progress_range': (40, 80),
                'hours': estimated_hours * 0.4,
                'goal': '深入理解关键章节，完成思考题',
                'tasks': ['精读重点章节', '完成每章思考题', '查阅相关背景知识'],
                'checkpoint': '能回答书中提出的核心问题'
            },
            {
                'name': '融会贯通',
                'progress_range': (80, 100),
                'hours': estimated_hours * 0.2,
                'goal': '形成自己的理解，应用到实践',
                'tasks': ['写读书笔记或书评', '与其他知识建立联系', '制定实践计划'],
                'checkpoint': '能将书中思想应用到实际'
            }
        ]
    elif source_type == 'documentation':
        stages = [
            {
                'name': '概览',
                'progress_range': (0, 20),
                'hours': estimated_hours * 0.2,
                'goal': '了解整体架构和核心概念',
                'tasks': ['阅读Overview部分', '了解主要模块', '画出架构图'],
                'checkpoint': '能说出这个文档涵盖哪些内容'
            },
            {
                'name': 'Quick Start',
                'progress_range': (20, 60),
                'hours': estimated_hours * 0.4,
                'goal': '完成官方入门教程',
                'tasks': ['完成Quick Start', '运行官方示例', '记录关键API'],
                'checkpoint': '能运行官方提供的示例代码'
            },
            {
                'name': '核心功能',
                'progress_range': (60, 100),
                'hours': estimated_hours * 0.4,
                'goal': '掌握核心API，能独立开发',
                'tasks': ['学习核心API文档', '实现一个完整功能', '解决实际问题'],
                'checkpoint': '不看文档也能写出基本用法'
            }
        ]
    else:
        # 通用3阶段
        stages = [
            {
                'name': '入门',
                'progress_range': (0, 30),
                'hours': estimated_hours * 0.3,
                'goal': '了解基础概念',
                'tasks': ['通读/浏览内容', '记录关键概念'],
                'checkpoint': '能说出这是什么'
            },
            {
                'name': '进阶',
                'progress_range': (30, 70),
                'hours': estimated_hours * 0.4,
                'goal': '掌握核心内容',
                'tasks': ['深入学习', '完成练习'],
                'checkpoint': '能完成基础任务'
            },
            {
                'name': '精通',
                'progress_range': (70, 100),
                'hours': estimated_hours * 0.3,
                'goal': '独立应用',
                'tasks': ['实践项目', '总结输出'],
                'checkpoint': '能独立解决问题'
            }
        ]

    return stages


def save_stages_to_db(material_id: int, stages_data: List[Dict]) -> bool:
    """保存学习阶段到数据库"""
    import json
    from .db import get_connection

    try:
        with get_connection() as conn:
            # 检查是否已有阶段表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS learning_stages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    material_id INTEGER NOT NULL,
                    stage_number INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    goal TEXT,
                    tasks TEXT,
                    checkpoint TEXT,
                    progress_start INTEGER,
                    progress_end INTEGER,
                    estimated_hours REAL,
                    FOREIGN KEY (material_id) REFERENCES materials(id)
                )
            ''')

            # 删除旧阶段
            conn.execute('DELETE FROM learning_stages WHERE material_id = ?', (material_id,))

            # 插入新阶段
            for i, stage in enumerate(stages_data):
                conn.execute('''
                    INSERT INTO learning_stages
                    (material_id, stage_number, name, goal, tasks, checkpoint,
                     progress_start, progress_end, estimated_hours)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    material_id,
                    i,
                    stage['name'],
                    stage['goal'],
                    json.dumps(stage.get('tasks', [])),
                    stage['checkpoint'],
                    stage['progress_range'][0],
                    stage['progress_range'][1],
                    stage['hours']
                ))

            conn.commit()
            return True
    except Exception as e:
        print(f"保存阶段失败: {e}")
        return False


def save_quiz_to_db(material_id: int, quiz_data: List[Dict]) -> bool:
    """保存测验到数据库"""
    import json
    from .db import get_connection

    try:
        with get_connection() as conn:
            # 检查是否已有测验表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS quizzes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    material_id INTEGER NOT NULL,
                    stage INTEGER NOT NULL,
                    question TEXT NOT NULL,
                    question_type TEXT,
                    difficulty TEXT,
                    hint TEXT,
                    answer TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (material_id) REFERENCES materials(id)
                )
            ''')

            # 插入测验
            for i, q in enumerate(quiz_data):
                conn.execute('''
                    INSERT INTO quizzes (material_id, stage, question, question_type, difficulty, hint)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (material_id, i, q['question'], q['type'], q['difficulty'], q.get('hint', '')))

            conn.commit()
            return True
    except Exception as e:
        print(f"保存测验失败: {e}")
        return False
