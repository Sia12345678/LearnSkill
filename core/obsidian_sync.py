"""
Obsidian同步模块 - Obsidian作为主数据源，SQLite作为运行时缓存
"""
import sys
import re
from pathlib import Path
from datetime import date, datetime
from typing import List, Dict, Optional, Tuple

# Obsidian库路径（用户可以配置）
DEFAULT_OBSIDIAN_DIR = Path.home() / "Documents" / "Obsidian Vault" / "学习助手"

# 领域标签映射
DOMAIN_TAGS = {
    'work-ai': 'work-ai',
    'dsml': 'dsml',
    'quant': 'quant',
    'philosophy': 'philosophy',
    'literature': 'literature',
    'physics': 'physics'
}

DOMAIN_NAMES = {
    'work-ai': '工作-AI开发',
    'dsml': '兴趣-DS/ML',
    'quant': '兴趣-Quant',
    'philosophy': '阅读-哲学',
    'literature': '阅读-文学',
    'physics': '阅读-物理'
}


def get_obsidian_dir() -> Path:
    """获取Obsidian库目录"""
    if not DEFAULT_OBSIDIAN_DIR.exists():
        try:
            DEFAULT_OBSIDIAN_DIR.mkdir(parents=True, exist_ok=True)
            print(f"✓ 创建Obsidian目录: {DEFAULT_OBSIDIAN_DIR}")
        except Exception as e:
            print(f"⚠️ 创建目录失败: {e}")
            return None
    return DEFAULT_OBSIDIAN_DIR


def get_note_path() -> Path:
    """获取学习资料库笔记路径"""
    obsidian_dir = get_obsidian_dir()
    if not obsidian_dir:
        return None
    return obsidian_dir / "学习资料库.md"


def parse_obsidian_content(content: str) -> List[Dict]:
    """
    解析Obsidian笔记内容，提取学习资料

    支持的格式：
    - [ ] [标题](URL)
      - 预估: 10.0h | 优先级: 9.2 | 进度: 0%
    - [x] 《书名》
      - 预估: 10.0h | 进度: 100%

    以及旧格式：
    - [ ] [标题](URL) #标签 ⏱️预估小时 📊进度% ⏲️已用小时
    """
    materials = []

    # 按行解析
    lines = content.split('\n')
    current_material = None

    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # 优先匹配新格式：主行 + 详情行
        # 主行：- [ ] [标题](URL) 或 - [x] 《书名》
        main_match = re.match(
            r'^- \[([ x])\]\s+(.+)$',
            line_stripped
        )

        if main_match:
            # 保存之前的资料
            if current_material:
                materials.append(current_material)

            checked = main_match.group(1)
            title_part = main_match.group(2).strip()

            # 解析标题和URL
            url_match = re.match(r'\[(.*?)\]\((.*?)\)', title_part)
            if url_match:
                title = url_match.group(1)
                url = url_match.group(2)
            else:
                # 可能是书名《...》
                title = title_part.strip()
                if title.startswith('《') and title.endswith('》'):
                    title = title[1:-1]
                url = None

            current_material = {
                'title': title,
                'url': url,
                'domain': None,  # 稍后从上下文确定
                'estimated_hours': 2.0,
                'actual_hours': 0.0,
                'progress': 0,
                'status': 'completed' if checked == 'x' else 'pending',
                'line_number': i,
                'priority': 0
            }

        # 匹配详情行：- 预估: 10.0h | 优先级: 9.2 | 进度: 0%
        elif current_material and line_stripped.startswith('- 预估:'):
            # 解析详情行
            detail = line_stripped[2:].strip()  # 去掉 "- "

            # 提取预估时间
            est_match = re.search(r'预估:\s*([\d.]+)h?', detail)
            if est_match:
                current_material['estimated_hours'] = float(est_match.group(1))

            # 提取进度
            prog_match = re.search(r'进度:\s*(\d+)%?', detail)
            if prog_match:
                current_material['progress'] = int(prog_match.group(1))
                if current_material['progress'] > 0:
                    current_material['status'] = 'in_progress'

            # 提取优先级
            pri_match = re.search(r'优先级:\s*([\d.]+)', detail)
            if pri_match:
                current_material['priority'] = float(pri_match.group(1))

            # 提取实际时间
            actual_match = re.search(r'已用:\s*([\d.]+)h?', detail)
            if actual_match:
                current_material['actual_hours'] = float(actual_match.group(1))

        # 匹配旧格式：- [ ] 内容 #标签 ⏱️预估小时 📊进度%
        elif current_material is None:
            old_match = re.match(
                r'^- \[([ x])\]\s+(.*?)(?:\s+#(\w+))?(?:\s+⏱️(\d+(?:\.\d+)?)h?)?(?:\s+📊(\d+)%?)?(?:\s+⏲️(\d+(?:\.\d+)?)h?)?$',
                line_stripped
            )
            if old_match:
                checked, title_part, tag, estimated, progress, actual = old_match.groups()

                # 解析标题和URL
                url_match = re.match(r'\[(.*?)\]\((.*?)\)', title_part)
                if url_match:
                    title = url_match.group(1)
                    url = url_match.group(2)
                else:
                    title = title_part.strip()
                    if title.startswith('《') and title.endswith('》'):
                        title = title[1:-1]
                    url = None

                domain = tag if tag in DOMAIN_TAGS else 'work-ai'

                materials.append({
                    'title': title,
                    'url': url,
                    'domain': domain,
                    'estimated_hours': float(estimated) if estimated else 2.0,
                    'actual_hours': float(actual) if actual else 0.0,
                    'progress': int(progress) if progress else 0,
                    'status': 'completed' if checked == 'x' else ('in_progress' if (progress and int(progress) > 0) else 'pending'),
                    'line_number': i,
                    'priority': 0
                })

    # 添加最后一个资料
    if current_material:
        materials.append(current_material)

    # 根据领域标题确定每个资料的领域
    current_domain = None
    for m in materials:
        if m['domain'] is None and current_domain:
            m['domain'] = current_domain
        # 检查是否是领域标题行（如 "### 工作-AI开发"）
        # 这需要在外部处理，这里先默认使用 work-ai

    return materials


def parse_obsidian_content_with_domain(content: str) -> List[Dict]:
    """
    解析Obsidian笔记内容，提取学习资料（带领域检测）

    会根据 ### 领域标题 自动识别每个资料的领域
    """
    materials = []
    current_domain = 'work-ai'  # 默认领域

    # 领域标题映射
    domain_map = {
        '工作-AI开发': 'work-ai',
        '兴趣-DS/ML': 'dsml',
        '兴趣-DS/ML（数据科学/机器学习）': 'dsml',
        '兴趣-Quant': 'quant',
        '阅读-哲学': 'philosophy',
        '阅读-文学': 'literature',
        '阅读-物理': 'physics'
    }

    lines = content.split('\n')
    current_material = None

    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # 检测领域标题 ### 工作-AI开发
        if line_stripped.startswith('### '):
            domain_name = line_stripped[4:].strip()
            current_domain = domain_map.get(domain_name, 'work-ai')
            continue

        # 主行：- [ ] [标题](URL) 或 - [x] 《书名》
        main_match = re.match(
            r'^- \[([ x])\]\s+(.+)$',
            line_stripped
        )

        if main_match:
            if current_material:
                current_material['domain'] = current_domain
                materials.append(current_material)

            checked = main_match.group(1)
            title_part = main_match.group(2).strip()

            # 解析标题和URL
            url_match = re.match(r'\[(.*?)\]\((.*?)\)', title_part)
            if url_match:
                title = url_match.group(1)
                url = url_match.group(2)
            else:
                title = title_part.strip()
                if title.startswith('《') and title.endswith('》'):
                    title = title[1:-1]
                url = None

            current_material = {
                'title': title,
                'url': url,
                'domain': current_domain,
                'estimated_hours': 2.0,
                'actual_hours': 0.0,
                'progress': 0,
                'status': 'completed' if checked == 'x' else 'pending',
                'line_number': i,
                'priority': 0
            }

        # 详情行
        elif current_material and line_stripped.startswith('- 预估:'):
            detail = line_stripped[2:].strip()

            est_match = re.search(r'预估:\s*([\d.]+)h?', detail)
            if est_match:
                current_material['estimated_hours'] = float(est_match.group(1))

            prog_match = re.search(r'进度:\s*(\d+)%?', detail)
            if prog_match:
                current_material['progress'] = int(prog_match.group(1))
                if current_material['progress'] > 0:
                    current_material['status'] = 'in_progress'

            pri_match = re.search(r'优先级:\s*([\d.]+)', detail)
            if pri_match:
                current_material['priority'] = float(pri_match.group(1))

            actual_match = re.search(r'已用:\s*([\d.]+)h?', detail)
            if actual_match:
                current_material['actual_hours'] = float(actual_match.group(1))

    if current_material:
        current_material['domain'] = current_domain
        materials.append(current_material)

    # 去重：按 title + domain 合并，保留第一个
    seen = {}
    unique_materials = []
    for m in materials:
        key = f"{m['title']}|{m.get('domain', 'work-ai')}"
        if key not in seen:
            seen[key] = m
            unique_materials.append(m)
        else:
            # 如果之前的存在且有进度，保留之前的
            existing = seen[key]
            if m.get('progress', 0) > existing.get('progress', 0):
                seen[key] = m

    return list(seen.values())


def generate_table_content(materials: List[Dict]) -> str:
    """
    生成 MD 表格格式的笔记内容
    """
    lines = [
        "# 学习资料库",
        "",
        f"> 最后更新: {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "## 学习资源",
        "",
        "| 标题 | 领域 | 预估(h) | 进度(%) | 已用(h) | 链接 |",
        "|------|------|----------|----------|----------|------|"
    ]

    for m in materials:
        title = m.get('title', '')
        domain = m.get('domain', 'work-ai')
        estimated = m.get('estimated_hours', 0)
        progress = m.get('progress', 0)
        actual = m.get('actual_hours', 0)
        url = m.get('url', '')

        # 格式化链接
        if url:
            link = f"[链接]({url})"
        else:
            link = ""

        lines.append(f"| {title} | {domain} | {estimated} | {progress} | {actual} | {link} |")

    lines.extend([
        "",
        "## 说明",
        "",
        "- 直接编辑表格即可添加/修改/删除资源",
        "- 领域可选：work-ai, dsml, quant, philosophy, literature, physics",
        "- 保存后刷新 Dashboard 即可同步"
    ])

    return "\n".join(lines)


def generate_obsidian_content(materials: List[Dict]) -> str:
    """
    生成Obsidian格式的笔记内容

    格式：
    - [ ] [标题](URL) #标签 ⏱️预估 📊进度 ⏲️已用
    """
    lines = [
        "# 学习资料库",
        "",
        f"> 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "> 来源: 学习助手",
        "",
        "## 📋 待学习资料",
        "",
    ]

    # 按领域分组
    domains = {}
    for m in materials:
        domain = m.get('domain', 'work-ai')
        if domain not in domains:
            domains[domain] = []
        domains[domain].append(m)

    # 按优先级排序（可扩展）
    for domain in ['work-ai', 'dsml', 'quant', 'philosophy', 'literature', 'physics']:
        if domain not in domains:
            continue

        items = domains[domain]
        domain_name = DOMAIN_NAMES.get(domain, domain)
        lines.append(f"### {domain_name}")
        lines.append("")

        for m in items:
            title = m['title']
            url = m.get('url', '')
            hours = m.get('estimated_hours', 2)
            actual = m.get('actual_hours', 0)
            progress = m.get('progress', 0)
            status = m.get('status', 'pending')

            # 复选框
            checkbox = "[x]" if status == 'completed' or progress >= 100 else "[ ]"

            # 标题格式
            if url:
                title_part = f"[{title}]({url})"
            else:
                title_part = f"《{title}》"

            # 构建行
            parts = [f"- {checkbox} {title_part}", f"#{domain}"]

            if hours:
                parts.append(f"⏱️{hours}h")
            if progress > 0:
                parts.append(f"📊{progress}%")
            if actual > 0:
                parts.append(f"⏲️{actual}h")

            lines.append(" ".join(parts))
            lines.append("")

    # 添加说明
    lines.extend([
        "---",
        "",
        "## 📝 使用说明",
        "",
        "### 格式规范",
        "```",
        "- [ ] [标题](URL) #领域 ⏱️预估小时 📊进度% ⏲️已用小时",
        "- [x] 《书名》 #philosophy ⏱️10h 📊100% ⏲️12h",
        "```",
        "",
        "### 领域标签",
        "- `#work-ai` - 工作-AI开发",
        "- `#dsml` - 兴趣-DS/ML",
        "- `#quant` - 兴趣-Quant",
        "- `#philosophy` - 阅读-哲学",
        "- `#literature` - 阅读-文学",
        "- `#physics` - 阅读-物理",
        "",
        "### 快捷操作",
        "- 勾选 `[x]` 标记完成",
        "- 修改 `📊数字%` 更新进度",
        "- 修改 `⏲️数字h` 更新实际用时",
        "",
        "## 📊 统计",
        "",
        f"- 总资料数: {len(materials)}",
        f"- 已完成: {sum(1 for m in materials if m.get('status') == 'completed' or m.get('progress', 0) >= 100)}",
        f"- 更新日期: {date.today().isoformat()}",
    ])

    return "\n".join(lines)


def add_material_to_obsidian(title: str, url: Optional[str], domain: str,
                             estimated_hours: float = 2.0) -> bool:
    """
    将新资料添加到Obsidian笔记（表格格式）
    """
    note_path = get_note_path()
    if not note_path:
        print("❌ 无法获取Obsidian笔记路径")
        return False

    try:
        # 读取现有内容
        if note_path.exists():
            content = note_path.read_text(encoding='utf-8')
        else:
            content = ""

        # 解析现有资料（支持表格和旧格式）
        if '| 标题 |' in content:
            materials = parse_table_content(content)
        else:
            materials = parse_obsidian_content(content)

        # 检查是否已存在（避免重复）
        for m in materials:
            if m['title'] == title:
                print(f"⚠️ 资料 '{title}' 已存在于Obsidian中")
                return True

        # 添加新资料
        new_material = {
            'title': title,
            'url': url,
            'domain': domain,
            'estimated_hours': estimated_hours,
            'actual_hours': 0,
            'progress': 0,
            'status': 'pending'
        }
        materials.append(new_material)

        # 生成新内容并写入（使用表格格式）
        if '| 标题 |' in content:
            new_content = generate_table_content(materials)
        else:
            new_content = generate_table_content(materials)
        note_path.write_text(new_content, encoding='utf-8')

        print(f"✓ 已添加 '{title}' 到Obsidian")
        return True

    except Exception as e:
        print(f"❌ 添加到Obsidian失败: {e}")
        return False


def sync_progress_to_obsidian(title: str, progress: int, actual_hours: float) -> bool:
    """
    同步学习进度到Obsidian笔记（表格格式）
    """
    note_path = get_note_path()
    if not note_path or not note_path.exists():
        return False

    try:
        content = note_path.read_text(encoding='utf-8')

        # 优先使用表格解析
        if '| 标题 |' in content:
            materials = parse_table_content(content)
        else:
            materials = parse_obsidian_content(content)

        # 查找并更新
        updated = False
        for m in materials:
            if m['title'] == title:
                m['progress'] = progress
                m['actual_hours'] = actual_hours
                if progress >= 100:
                    m['status'] = 'completed'
                elif progress > 0:
                    m['status'] = 'in_progress'
                updated = True
                break

        if not updated:
            print(f"⚠️ 未在Obsidian中找到 '{title}'")
            return False

        # 写回（使用表格格式）
        if '| 标题 |' in content:
            new_content = generate_table_content(materials)
        else:
            new_content = generate_obsidian_content(materials)
        note_path.write_text(new_content, encoding='utf-8')

        print(f"✓ 已同步 '{title}' 进度到Obsidian: {progress}%")
        return True

    except Exception as e:
        print(f"❌ 同步进度失败: {e}")
        return False


def parse_table_content(content: str) -> List[Dict]:
    """
    解析 MD 表格格式的学习资料

    表格格式：
    | 标题 | 领域 | 预估(h) | 进度(%) | 已用(h) | 链接 |
    |------|------|----------|----------|----------|------|
    """
    materials = []
    lines = content.split('\n')
    in_table = False
    header_indices = {}

    for line in lines:
        line = line.strip()

        # 检测表格开始
        if line.startswith('| 标题 |'):
            in_table = True
            # 解析表头索引
            headers = [h.strip() for h in line.split('|')[1:-1]]
            for i, h in enumerate(headers):
                header_indices[h] = i
            continue

        # 检测表格结束（遇到空行或非表格行）
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
                actual = cells[header_indices.get('已用(h)', 4)]
                link = cells[header_indices.get('链接', 5)]

                # 解析链接 [链接](url) 或 url
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
                    'status': 'completed' if (progress and int(progress) >= 100) else ('in_progress' if (progress and int(progress) > 0) else 'pending')
                })
            except (ValueError, IndexError) as e:
                # 跳过解析错误的行
                continue

    return materials


def import_from_obsidian() -> List[Dict]:
    """
    从Obsidian导入学习资料（主数据源）

    支持两种格式：
    1. MD 表格格式（优先）
    2. 旧的列表格式（兼容）
    """
    note_path = get_note_path()
    if not note_path:
        print("❌ 无法获取Obsidian笔记路径")
        return []

    if not note_path.exists():
        print(f"📄 Obsidian笔记不存在，创建空文件: {note_path}")
        # 创建空文件
        note_path.write_text(generate_table_content([]), encoding='utf-8')
        return []

    try:
        content = note_path.read_text(encoding='utf-8')

        # 优先尝试解析表格格式
        if '| 标题 |' in content:
            materials = parse_table_content(content)
            if materials:
                print(f"✓ 从Obsidian表格导入 {len(materials)} 个资料")
                return materials

        # 兼容旧的列表格式
        materials = parse_obsidian_content_with_domain(content)
        print(f"✓ 从Obsidian列表导入 {len(materials)} 个资料")
        return materials

    except Exception as e:
        print(f"❌ 从Obsidian导入失败: {e}")
        return []


def sync_to_obsidian(material_id: int = None) -> bool:
    """
    将数据库中的资料同步到Obsidian（保留用于批量同步）

    注意：单向同步，Obsidian是主存储，通常不需要调用这个
    """
    from .db import get_connection

    note_path = get_note_path()
    if not note_path:
        return False

    try:
        with get_connection() as conn:
            if material_id:
                cursor = conn.execute(
                    'SELECT * FROM materials WHERE id = ?', (material_id,)
                )
            else:
                cursor = conn.execute('SELECT * FROM materials ORDER BY id')

            rows = cursor.fetchall()
            cols = [c[0] for c in cursor.description]

        materials = [dict(zip(cols, row)) for row in rows]
        content = generate_obsidian_content(materials)
        note_path.write_text(content, encoding='utf-8')

        print(f"✓ 已同步 {len(materials)} 个资料到Obsidian")
        return True

    except Exception as e:
        print(f"❌ 同步失败: {e}")
        return False


def delete_resource_from_obsidian(title: str, domain: str = None) -> bool:
    """
    从Obsidian笔记中删除指定资源（表格格式）
    """
    note_path = get_note_path()
    if not note_path or not note_path.exists():
        return False

    try:
        content = note_path.read_text(encoding='utf-8')

        # 优先使用表格解析
        if '| 标题 |' in content:
            materials = parse_table_content(content)
            # 过滤掉要删除的资源
            materials = [m for m in materials if m['title'] != title]
            # 写回（表格格式）
            new_content = generate_table_content(materials)
        else:
            # 旧格式兼容
            lines = content.split('\n')
            new_lines = []
            skip_next = False
            for i, line in enumerate(lines):
                if skip_next:
                    if line.strip().startswith('- 预估:') or line.strip().startswith('- 优先级:') or line.strip().startswith('- 进度:'):
                        continue
                    else:
                        skip_next = False
                match = re.match(r'^- \[([ x])\]\s+\[?' + re.escape(title) + r'\]?', line.strip())
                if match or (domain and f'《{title}》' in line):
                    skip_next = True
                    continue
                new_lines.append(line)
            new_content = '\n'.join(new_lines)

        note_path.write_text(new_content, encoding='utf-8')
        print(f"✓ 已从Obsidian删除: {title}")
        return True

    except Exception as e:
        print(f"❌ 删除失败: {e}")
        return False


def bidirectional_sync() -> Tuple[List[Dict], List[Dict]]:
    """
    双向同步：Obsidian <-> SQLite

    Returns:
        (新增到SQLite的资料列表, 从SQLite更新的资料列表)
    """
    from .db import get_connection, add_material, update_material_progress

    obsidian_materials = import_from_obsidian()
    if not obsidian_materials:
        return [], []

    new_materials = []
    updated_materials = []

    with get_connection() as conn:
        for m in obsidian_materials:
            # 检查是否已存在
            existing = conn.execute(
                'SELECT id, progress, actual_hours FROM materials WHERE title = ?',
                (m['title'],)
            ).fetchone()

            if existing:
                # 已存在，检查是否有更新
                existing_id, existing_progress, existing_hours = existing
                if (m['progress'] != existing_progress or
                    m.get('actual_hours', 0) != existing_hours):
                    # Obsidian更新，同步到SQLite
                    update_material_progress(existing_id, m['progress'], m.get('actual_hours'))
                    updated_materials.append(m)
            else:
                # 新增
                add_material(
                    title=m['title'],
                    url=m.get('url'),
                    source_type='unknown',
                    domain=m.get('domain', 'work-ai'),
                    estimated_hours=m.get('estimated_hours', 2.0)
                )
                new_materials.append(m)

    print(f"✓ 双向同步完成: {len(new_materials)} 新增, {len(updated_materials)} 更新")
    return new_materials, updated_materials
