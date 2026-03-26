"""
学习助手配置
"""
import os
from pathlib import Path

# 数据目录（Git仓库）
DATA_DIR = Path.home() / "Documents" / "self_learning" / "learning-assistant"
DB_PATH = DATA_DIR / "data" / "learning.db"
DASHBOARD_PATH = DATA_DIR / "dashboard" / "index.html"

# GitHub配置
GITHUB_REPO = "Sia12345678/LearnSkill"
GITHUB_TOKEN_ENV = "GITHUB_TOKEN"  # 从环境变量读取

# 用户领域熟练度初始值
DEFAULT_PROFICIENCY = {
    "work-ai": 4,
    "dsml": 3,
    "quant": 3,
    "philosophy": 2,
    "literature": 7,
    "physics": 4
}

# 领域显示名称
DOMAIN_NAMES = {
    "work-ai": "工作-AI开发",
    "dsml": "兴趣-DS/ML",
    "quant": "兴趣-Quant",
    "philosophy": "阅读-哲学",
    "literature": "阅读-文学",
    "physics": "阅读-物理"
}

# 优先级权重
PRIORITY_WEIGHTS = {
    "skill_match": 0.25,      # 技能树匹配度
    "cost_benefit": 0.20,     # 投入产出比
    "timeliness": 0.15,       # 时效性
    "preference": 0.15,       # 用户偏好
    "rotation": 0.15,         # 领域轮换平衡
    "weekend_fit": 0.10       # 周末适配度
}

# 时间规划规则
TIME_RULES = {
    "weekend": {
        "slots": [("09:00", "12:00"), ("14:00", "17:00")],
        "domains": ["work-ai", "dsml", "quant", "physics"],
        "session_hours": 2.5
    },
    "weekday": {
        "slots": [("21:00", "22:00")],
        "domains": ["philosophy", "literature"],
        "session_hours": 1.0
    }
}

# 推荐源
RECOMMENDATION_SOURCES = {
    "work-ai": [
        "https://github.com/trending/python",
        "https://arxiv.org/rss/cs.AI",
        "https://news.ycombinator.com"
    ],
    "dsml": [
        "https://arxiv.org/rss/cs.LG",
        "https://arxiv.org/rss/stat.ML",
        "https://www.kaggle.com/competitions"
    ],
    "quant": [
        "https://arxiv.org/rss/q-fin",
        "https://github.com/trending/julia"  # Quant常用
    ]
}
