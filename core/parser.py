"""
内容解析模块 - 自动识别资料类型和提取信息
"""
import re
import json
import sys
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse
from pathlib import Path
import subprocess

# 处理相对导入
try:
    from ..config import DOMAIN_NAMES
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import DOMAIN_NAMES


def parse_input(text: str) -> Dict:
    """
    解析用户输入的资料
    支持格式:
    - URL: https://...
    - 实体书: 《书名》或 "书名"
    - 简单描述: 名字 + 链接
    """
    text = text.strip()

    # 提取URL
    url_match = re.search(r'https?://[^\s<>"\']+', text)
    url = url_match.group(0) if url_match else None

    # 去除URL后的剩余文本作为标题
    title = re.sub(r'https?://[^\s<>"\']+', '', text).strip()

    # 去除命令行选项（如 --domain work-ai）- 必须在去除分隔符之前
    title = re.sub(r'--\w+\s+\S+', '', title).strip()

    # 去除分隔符
    title = re.sub(r'^[-–—|]+', '', title).strip()

    if url and not title:
        # 只有URL，需要从网页获取标题
        title = _fetch_web_title(url)

    if not url and title:
        # 只有标题，认为是实体书
        return {
            'title': title,
            'url': None,
            'source_type': 'book',
            'domain': _infer_domain(title),
            'estimated_hours': _estimate_book_hours(title)
        }

    if url:
        # 有URL，识别类型
        source_type = _detect_source_type(url, title)
        domain = _infer_domain(title + " " + url)
        estimated_hours = _estimate_hours(url, source_type, title)

        return {
            'title': title or "未命名资料",
            'url': url,
            'source_type': source_type,
            'domain': domain,
            'estimated_hours': estimated_hours
        }

    raise ValueError("无法解析输入，请提供URL或书名")


def _fetch_web_title(url: str) -> str:
    """从网页获取标题"""
    try:
        # 使用curl获取页面标题
        result = subprocess.run(
            ['curl', '-s', '-L', '--max-time', '5', url],
            capture_output=True,
            text=True
        )
        html = result.stdout

        # 提取<title>
        match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # 提取og:title
        match = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)', html, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    except Exception:
        pass

    # 失败时返回域名
    parsed = urlparse(url)
    return f"{parsed.netloc} 上的资料"


def _detect_source_type(url: str, title: str) -> str:
    """识别资料类型"""
    url_lower = url.lower()
    title_lower = title.lower()

    # GitHub仓库
    if 'github.com' in url_lower:
        return 'github'

    # 视频平台
    if any(x in url_lower for x in ['bilibili', 'youtube', 'vimeo', ' coursera']):
        return 'video'

    # 在线课程
    if any(x in url_lower for x in ['course', 'tutorial', 'skilljar', 'coursera', 'udemy']):
        return 'course'

    # 论文
    if any(x in url_lower for x in ['arxiv', 'pdf', 'paper']):
        return 'paper'

    # 文章/博客
    return 'article'


def _infer_domain(text: str) -> str:
    """根据文本推断领域"""
    text_lower = text.lower()

    # AI开发关键词
    ai_keywords = ['claude', 'anthropic', 'openai', 'llm', 'langchain', 'agent',
                   'gpt', 'api', 'skill', 'ai开发', '大模型']
    if any(k in text_lower for k in ai_keywords):
        return 'work-ai'

    # DS/ML关键词
    ml_keywords = ['machine learning', 'deep learning', 'pytorch', 'tensorflow',
                   'neural network', '数据分析', '深度学习', '神经网络', 'kaggle']
    if any(k in text_lower for k in ml_keywords):
        return 'dsml'

    # Quant关键词
    quant_keywords = ['quant', 'finance', 'trading', 'fintech', 'investment',
                      '金融', '量化', '投资', '哥伦比亚']
    if any(k in text_lower for k in quant_keywords):
        return 'quant'

    # 哲学关键词
    phil_keywords = ['哲学', 'philosophy', '福柯', '海德格尔', '疯癫与文明',
                     '存在与时间', '康德', '黑格尔']
    if any(k in text_lower for k in phil_keywords):
        return 'philosophy'

    # 物理关键词
    physics_keywords = ['physics', 'quantum', '芯片', '半导体', '物理']
    if any(k in text_lower for k in physics_keywords):
        return 'physics'

    # 文学关键词
    lit_keywords = ['文学', '小说', 'novel', 'literature']
    if any(k in text_lower for k in lit_keywords):
        return 'literature'

    # 默认根据上下文推断
    return 'work-ai'  # 默认工作相关


def _estimate_book_hours(title: str) -> float:
    """估算书籍阅读时间"""
    # 技术类书籍通常需要更多时间
    tech_keywords = ['深度学习', 'machine learning', 'python', 'programming']
    if any(k in title.lower() for k in tech_keywords):
        return 60  # 技术书籍平均60小时

    # 哲学类
    phil_keywords = ['哲学', 'philosophy', '疯癫', '文明']
    if any(k in title.lower() for k in phil_keywords):
        return 20  # 哲学书籍20小时

    # 投资/金融
    finance_keywords = ['投资', '金融', 'quant']
    if any(k in title.lower() for k in finance_keywords):
        return 15

    # 通识类
    return 12


def _estimate_hours(url: str, source_type: str, title: str) -> float:
    """估算学习所需时间"""
    if source_type == 'video':
        # 尝试获取视频时长
        duration = _fetch_video_duration(url)
        if duration:
            # 视频学习时间是观看时间的1.5倍（暂停思考练习）
            return round(duration / 60 * 1.5, 1)
        return 3  # 默认3小时

    if source_type == 'course':
        return 20  # 课程平均20小时

    if source_type == 'github':
        return 8  # 代码学习8小时

    if source_type == 'paper':
        return 5  # 论文精读5小时

    # 文章默认1-2小时
    return 1.5


def _fetch_video_duration(url: str) -> Optional[int]:
    """获取视频时长（分钟）"""
    # 这里可以实现B站/YouTube API调用
    # 暂时返回None，使用默认值
    return None


def parse_obsidian_note(content: str) -> list:
    """
    解析Obsidian笔记格式
    格式:
    - [ ] [标题](URL) #标签1 #标签2
    - [ ] 《书名》 #标签
    """
    materials = []

    for line in content.split('\n'):
        line = line.strip()
        if not line.startswith('- [ ]'):
            continue

        # 提取链接
        url_match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', line)
        if url_match:
            title = url_match.group(1)
            url = url_match.group(2)
        else:
            # 尝试匹配书名《》
            book_match = re.search(r'《([^》]+)》', line)
            if book_match:
                title = f"《{book_match.group(1)}》"
                url = None
            else:
                continue

        # 提取标签
        tags = re.findall(r'#(\w+)', line)

        try:
            parsed = parse_input(f"{title} {url}" if url else title)
            parsed['tags'] = tags
            materials.append(parsed)
        except ValueError:
            continue

    return materials
