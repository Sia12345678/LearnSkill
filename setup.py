#!/usr/bin/env python3
"""
学习助手初始化脚本
"""
import os
import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from config import DATA_DIR, DB_PATH
from core.db import init_db


def main():
    print("=" * 60)
    print("📚 学习助手初始化")
    print("=" * 60)
    print()

    # 1. 检查数据目录
    print(f"1. 检查数据目录...")
    if not DATA_DIR.exists():
        print(f"   ✗ 数据目录不存在: {DATA_DIR}")
        print("   请确保已克隆GitHub仓库到正确位置")
        return 1
    print(f"   ✓ 数据目录存在: {DATA_DIR}")

    # 2. 初始化数据库
    print(f"\n2. 初始化数据库...")
    init_db()
    if DB_PATH.exists():
        print(f"   ✓ 数据库创建成功: {DB_PATH}")
    else:
        print(f"   ✗ 数据库创建失败")
        return 1

    # 3. 添加初始资料
    print(f"\n3. 添加初始学习资料...")
    from core.db import add_material
    from core.priority import update_priority_scores
    import sqlite3

    initial_materials = [
        ("Anthropic Skill (B站教程)", "https://www.bilibili.com/video/BV1qv6eBZErD", "video", "work-ai", 1, 95),
        ("Claude Certified Architect", "https://anthropic.skilljar.com/", "course", "work-ai", 10, 0),
        ("Columbia FinTech", "https://courseworks2.columbia.edu/courses/231236/modules", "course", "quant", 50, 0),
        ("《疯癫与文明》", None, "book", "philosophy", 18, 0),
        ("《深度学习》(花书)", None, "book", "dsml", 70, 0),
        ("《投资常识》", None, "book", "quant", 10, 0),
        ("《芯片简史》", None, "book", "physics", 12, 0),
    ]

    added = 0
    for title, url, source_type, domain, hours, progress in initial_materials:
        try:
            add_material(title, url, source_type, domain, hours)
            added += 1
        except Exception as e:
            print(f"   ⚠ 添加失败: {title} - {e}")

    print(f"   ✓ 添加了 {added} 个资料")

    # 4. 计算优先级
    print(f"\n4. 计算优先级...")
    update_priority_scores()
    print(f"   ✓ 优先级计算完成")

    # 5. 生成本周计划
    print(f"\n5. 生成本周计划...")
    from core.planner import generate_weekly_plan
    from datetime import date, timedelta

    week_start = date.today() - timedelta(days=date.today().weekday())
    plans = generate_weekly_plan(week_start)
    print(f"   ✓ 生成了 {len(plans)} 个任务")

    # 6. 同步到Apple Calendar
    print(f"\n6. 同步到Apple Calendar...")
    try:
        from core.calendar_sync import sync_week_to_calendar
        if sync_week_to_calendar(week_start):
            print(f"   ✓ 已同步到Apple Calendar")
        else:
            print(f"   ⚠ Calendar同步需要授权，请检查系统设置")
    except Exception as e:
        print(f"   ⚠ Calendar同步失败: {e}")

    print("\n" + "=" * 60)
    print("✓ 初始化完成！")
    print("=" * 60)
    print()
    print("使用方法:")
    print("  /learn              - 显示主菜单")
    print("  /learn-add <url>   - 添加学习资料")
    print("  /learn-plan         - 生成/查看计划")
    print("  /learn-status       - 查看学习状态")
    print("  /learn-dashboard    - 打开可视化面板")
    print("  /learn-check        - 检查今日任务")
    print()
    print(f"数据目录: {DATA_DIR}")
    print(f"数据库: {DB_PATH}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
