---
name: learn
description: |
  学习助手 - 管理学习资料、智能优先级排序、生成学习计划、追踪进度。
  当用户想要学习新东西、管理学习计划、查看学习进度时触发此skill。
  关键词包括：学习、计划、资料、进度、优先级、复习、打卡。
---

# 学习助手 Skill

## 激活条件

当用户输入以下任一内容时激活：
- `/learn` 或 `学习助手`
- "我要学习", "添加学习资料", "生成学习计划"
- "查看进度", "标记完成", "学习打卡"
- "推荐学习资源", "学习计划"

## 使用方式

### 1. 添加学习资料
```
用户: 我想学这个 https://example.com/tutorial
或: 添加书籍《深度学习》
```
执行: `python3 ~/.claude/skills/learn/main.py add_material <url或书名>`

### 2. 生成学习计划
```
用户: 生成本周计划 / 学习计划 / 这周学什么
```
执行: `python3 ~/.claude/skills/learn/main.py generate_plan`

### 3. 查看状态
```
用户: 学习进度 / 学得怎么样 / 统计
```
执行: `python3 ~/.claude/skills/learn/main.py show_status`

### 4. 清除计划
```
用户: 清除本周计划 / 清理计划
```
执行: `python3 ~/.claude/skills/learn/main.py clear_plan`

清除所有未来计划:
```
用户: 清除所有计划
```
执行: `python3 ~/.claude/skills/learn/main.py clear_plan --all`

### 5. 打开可视化面板
```
用户: 打开学习面板 / dashboard
```
执行: `open ~/Documents/self_learning/learning-assistant/dashboard/index.html`

### 5. 标记任务完成
```
用户: 我学完了 / 完成任务
```
执行: `complete_task` (支持记录实际开始时间、结束时间、学习时长、质量评分)

### 6. 更新学习进度
```
用户: 更新进度 / 修改进度
```
执行: `update_progress` (更新资料进度百分比和已用时长)

### 7. 立即扫描资源
```
用户: 扫描新资源 / 找学习资料 / 搜索推荐
```
执行: `scan_recommendations` (立即扫描arXiv/GitHub/Kaggle/豆瓣)

### 8. 查看资料详情（含阶段和测验）
```
用户: 查看资料详情 / 学习阶段 / 测验
```
执行: `python3 ~/.claude/skills/learn/main.py material_detail <资料ID>`

### 9. 同步到 Obsidian
```
用户: 同步到 Obsidian / 更新笔记
```
执行: `python3 ~/.claude/skills/learn/main.py sync_obsidian`

### 10. 从 Obsidian 导入
```
用户: 从 Obsidian 导入 / 导入笔记
```
执行: `python3 ~/.claude/skills/learn/main.py import_obsidian`

## 核心功能

### 学习阶段与测验

添加资料时会自动生成：

**学习阶段**（3阶段模型）:
- **入门** (0-30%): 了解基础概念，能说出这是什么
- **进阶** (30-70%): 掌握核心内容，能完成基础任务
- **精通** (70-100%): 独立应用，能独立解决问题

不同阶段类型有不同任务设计：
- **视频**: 概念理解 → 动手实践 → 综合应用
- **书籍**: 通读理解 → 深入思考 → 融会贯通
- **文档**: 概览 → Quick Start → 核心功能

**测验生成**（按领域定制）:
- **技术类** (work-ai/dsml/quant): 概念题 + 代码实践 + 应用场景 + 进阶项目
- **哲学** (philosophy): 核心论点理解 + 论证分析 + 批判性思考 + 现实意义
- **文学** (literature): 不出题，专注阅读体验

### 优先级算法（6维度）
1. **技能树匹配度** (25%) - 熟练度越低优先级越高
2. **投入产出比** (20%) - 适中时长(2-10小时)最优
3. **时效性** (15%) - 新资料优先
4. **用户偏好** (15%) - 基于历史成功率
5. **领域轮换** (15%) - 避免单一领域过载
6. **周末适配度** (10%) - 技术类周末，阅读类周内

### 时间规划策略
- **周末(六日)**: 2-3小时/段，适合技术类（AI开发、DS/ML、Quant、物理）
- **周内(一至五)**: 1小时/晚，适合阅读类（哲学、文学）

### 学习评估维度
- **效率**: 预估vs实际时间、按时完成率
- **结果**: 测验得分、项目完成质量
- **适配度**: 时间段适配、领域切换流畅度

## 数据存储

- **数据库**: `~/Documents/self_learning/learning-assistant/data/learning.db`
- **面板**: `~/Documents/self_learning/learning-assistant/dashboard/index.html`
- **Obsidian**: `~/Documents/Obsidian Vault/学习助手/学习资料库.md`
- **GitHub**: 定期同步 `Sia12345678/LearnSkill`

## 用户画像（初始）

| 领域 | 熟练度 |
|-----|--------|
| 工作-AI开发 | 4/10 |
| 兴趣-DS/ML | 3/10 |
| 兴趣-Quant | 3/10 |
| 阅读-哲学 | 2/10 |
| 阅读-文学 | 7/10 |
| 阅读-物理 | 4/10 |

## 已初始化资料

1. Anthropic Skill (B站教程) - 即将完成 (95%)
2. Claude Certified Architect - 未开始
3. Columbia FinTech - 未开始
4. 《疯癫与文明》- 未开始
5. 《深度学习》(花书) - 未开始
6. 《投资常识》- 未开始
7. 《芯片简史》- 未开始

## 自动定时任务

- **每晚21:00**: 检查当日学习任务完成情况
- **每周六上午10:00**: 扫描arXiv/GitHub/Kaggle/豆瓣等新资源，生成推荐列表

## 注意事项

1. 首次使用需运行 `python3 ~/.claude/skills/learn/setup.py` 初始化
2. Calendar同步需要系统授权
3. GitHub同步需要 `GITHUB_TOKEN` 环境变量
